"""Histórico persistente (SQLite da biblioteca padrão): lotes validados, suas notas e mudanças de regras.

Os 100k títulos do estoque continuam em RAM (StockIndex); aqui fica só o registro de auditoria.
- lotes: o resumo de toda validação (inclusive repetições servidas pelo cache e o modo carteira);
- notas_lote + erros_nota: o detalhe nota a nota, só do modo lote (uma carteira de 100k notas daria
  dezenas de MB por envio e é o próprio estoque, que já está em disco);
- mudancas_regras: cada PUT /validators aceito.
Uma conexão por operação: seguro com as threads do FastAPI e sem estado compartilhado.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .stock_index import normalizar_nu_documento

_SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS lotes (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    criado_em             TEXT    NOT NULL,
    request_id            TEXT    NOT NULL,
    chave_idempotencia    TEXT    NOT NULL,  -- sha256 da chave completa: arquivo + parâmetros + versão das regras
    batch_hash            TEXT    NOT NULL,  -- sha256 só do arquivo
    modo                  TEXT    NOT NULL,
    data_base             TEXT    NOT NULL,
    taxa_mensal           REAL    NOT NULL,
    otimizar_lote         INTEGER NOT NULL,
    versao_config         INTEGER NOT NULL,
    what_if               INTEGER NOT NULL,  -- 1 = validadores_override (simulação do gestor)
    replay                INTEGER NOT NULL,  -- 1 = resposta veio do cache de idempotência
    total_notas           INTEGER NOT NULL,
    qtd_aprovadas         INTEGER NOT NULL,
    qtd_recusadas         INTEGER NOT NULL,
    qtd_alertas_fraude    INTEGER NOT NULL,
    valor_bruto_total     REAL    NOT NULL,
    valor_liquido_receber REAL    NOT NULL,
    tempo_processamento_ms REAL   NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_lotes_batch_hash ON lotes (batch_hash);
CREATE INDEX IF NOT EXISTS ix_lotes_chave ON lotes (chave_idempotencia);
CREATE TABLE IF NOT EXISTS notas_lote (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    lote_id               INTEGER NOT NULL REFERENCES lotes (id),
    linha_csv             INTEGER NOT NULL,
    nu_documento          TEXT    NOT NULL,
    nu_documento_busca    TEXT    NOT NULL,  -- normalizado como na chave canônica (zeros à esquerda fora)
    nome_cedente          TEXT    NOT NULL,
    doc_cedente           TEXT    NOT NULL,
    nome_sacado           TEXT    NOT NULL,
    doc_sacado            TEXT    NOT NULL,
    tipo_recebivel        TEXT    NOT NULL,
    valor_nominal         REAL    NOT NULL,
    data_vencimento       TEXT    NOT NULL,
    prazo_dias            INTEGER NOT NULL,
    desagio_reais         REAL    NOT NULL,
    valor_liquido         REAL    NOT NULL,
    status                TEXT    NOT NULL,
    severidade            TEXT    NOT NULL,
    salva_pelo_otimizador INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_notas_lote ON notas_lote (lote_id, linha_csv);
CREATE INDEX IF NOT EXISTS ix_notas_busca ON notas_lote (nu_documento_busca);
CREATE TABLE IF NOT EXISTS erros_nota (
    nota_id          INTEGER NOT NULL REFERENCES notas_lote (id),
    ordem            INTEGER NOT NULL,
    codigo           TEXT    NOT NULL,
    titulo_amigavel  TEXT    NOT NULL,
    mensagem_empresa TEXT    NOT NULL,
    acao_recomendada TEXT    NOT NULL,
    PRIMARY KEY (nota_id, ordem)
);
CREATE TABLE IF NOT EXISTS mudancas_regras (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    criado_em     TEXT    NOT NULL,
    request_id    TEXT    NOT NULL,
    versao_config INTEGER NOT NULL,
    regras_ativas INTEGER NOT NULL,
    config_json   TEXT    NOT NULL
);
"""

_COLUNAS_NOTA = (
    "linha_csv", "nu_documento", "nome_cedente", "doc_cedente", "nome_sacado", "doc_sacado", "tipo_recebivel",
    "valor_nominal", "data_vencimento", "prazo_dias", "desagio_reais", "valor_liquido", "status", "severidade",
    "salva_pelo_otimizador",
)
_BOOLEANOS_LOTE = ("otimizar_lote", "what_if", "replay")


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _lote(linha: sqlite3.Row) -> dict[str, Any]:
    item = dict(linha)
    for campo in _BOOLEANOS_LOTE:
        item[campo] = bool(item[campo])
    return item


class Historico:
    def __init__(self, caminho: Path):
        self.caminho = Path(caminho)
        with closing(self._conectar()) as conn, conn:
            conn.executescript(_SCHEMA)

    def _conectar(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.caminho, timeout=5)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    # ----------------------------------------------------------------- escrita

    def registrar_lote(self, itens: list[Any] | None = None, **campos: Any) -> int:
        """Grava o resumo e, se vierem `itens` (ItemLote), as notas e os erros, tudo numa transação."""
        campos = {"criado_em": _agora(), **campos}
        colunas = ", ".join(campos)
        marcadores = ", ".join("?" for _ in campos)
        with closing(self._conectar()) as conn, conn:
            lote_id = int(conn.execute(f"INSERT INTO lotes ({colunas}) VALUES ({marcadores})", list(campos.values())).lastrowid or 0)
            if itens:
                # o INSERT acima já tem o lock de escrita desta transação: ninguém mais grava notas até o commit
                primeiro = conn.execute("SELECT COALESCE(MAX(id), 0) FROM notas_lote").fetchone()[0] + 1
                conn.executemany(
                    f"INSERT INTO notas_lote (id, lote_id, nu_documento_busca, {', '.join(_COLUNAS_NOTA)}) "
                    f"VALUES (?, ?, ?, {', '.join('?' for _ in _COLUNAS_NOTA)})",
                    [
                        (primeiro + i, lote_id, normalizar_nu_documento(item.nu_documento),
                         *(getattr(item, c) for c in _COLUNAS_NOTA))
                        for i, item in enumerate(itens)
                    ],
                )
                conn.executemany(
                    "INSERT INTO erros_nota (nota_id, ordem, codigo, titulo_amigavel, mensagem_empresa, acao_recomendada) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    [
                        (primeiro + i, ordem, e.codigo, e.titulo_amigavel, e.mensagem_empresa, e.acao_recomendada)
                        for i, item in enumerate(itens)
                        for ordem, e in enumerate(item.erros)
                    ],
                )
        return lote_id

    def registrar_mudanca_regras(self, request_id: str, versao_config: int, regras_ativas: int, config: dict) -> None:
        with closing(self._conectar()) as conn, conn:
            conn.execute(
                "INSERT INTO mudancas_regras (criado_em, request_id, versao_config, regras_ativas, config_json) "
                "VALUES (?, ?, ?, ?, ?)",
                (_agora(), request_id, versao_config, regras_ativas, json.dumps(config, ensure_ascii=False)),
            )

    # ----------------------------------------------------------------- leitura

    def _pagina(self, tabela: str, limite: int, offset: int) -> tuple[list[sqlite3.Row], int]:
        # tabela vem só de listar_* (nunca do usuário); limite e offset vão como parâmetros
        with closing(self._conectar()) as conn:
            total = conn.execute(f"SELECT COUNT(*) FROM {tabela}").fetchone()[0]
            linhas = conn.execute(f"SELECT * FROM {tabela} ORDER BY id DESC LIMIT ? OFFSET ?", (limite, offset)).fetchall()
        return linhas, total

    def listar_lotes(self, limite: int, offset: int) -> tuple[list[dict[str, Any]], int]:
        linhas, total = self._pagina("lotes", limite, offset)
        return [_lote(l) for l in linhas], total

    def listar_mudancas_regras(self, limite: int, offset: int) -> tuple[list[dict[str, Any]], int]:
        linhas, total = self._pagina("mudancas_regras", limite, offset)
        itens = []
        for linha in linhas:
            item = dict(linha)
            item["config"] = json.loads(item.pop("config_json"))
            itens.append(item)
        return itens, total

    def obter_lote(self, lote_id: int, limite: int, offset: int) -> dict[str, Any] | None:
        """Resumo + notas (com erros) de um lote. Repetição do cache mostra as notas do envio original."""
        with closing(self._conectar()) as conn:
            linha = conn.execute("SELECT * FROM lotes WHERE id = ?", (lote_id,)).fetchone()
            if linha is None:
                return None
            lote = _lote(linha)
            origem = lote_id
            if lote["replay"]:
                original = conn.execute(
                    "SELECT id FROM lotes WHERE chave_idempotencia = ? AND replay = 0 AND id < ? ORDER BY id DESC LIMIT 1",
                    (lote["chave_idempotencia"], lote_id),
                ).fetchone()
                origem = original["id"] if original else lote_id
            total = conn.execute("SELECT COUNT(*) FROM notas_lote WHERE lote_id = ?", (origem,)).fetchone()[0]
            notas = [dict(n) for n in conn.execute(
                "SELECT * FROM notas_lote WHERE lote_id = ? ORDER BY linha_csv LIMIT ? OFFSET ?", (origem, limite, offset)
            )]
            erros: dict[int, list[dict[str, Any]]] = {}
            if notas:
                ids = [n["id"] for n in notas]
                for e in conn.execute(
                    f"SELECT * FROM erros_nota WHERE nota_id IN ({', '.join('?' for _ in ids)}) ORDER BY nota_id, ordem", ids
                ):
                    erros.setdefault(e["nota_id"], []).append(
                        {k: e[k] for k in ("codigo", "titulo_amigavel", "mensagem_empresa", "acao_recomendada")}
                    )
        for nota in notas:
            nota["salva_pelo_otimizador"] = bool(nota["salva_pelo_otimizador"])
            nota["erros"] = erros.get(nota["id"], [])
            for campo in ("id", "lote_id", "nu_documento_busca"):
                nota.pop(campo)
        return {
            "lote": lote,
            "notas_de_lote_id": origem,
            "notas_guardadas": total > 0,
            "total_notas_guardadas": total,
            "limite": limite,
            "offset": offset,
            "notas": notas,
        }

    def buscar_nota(self, nu_documento: str, limite: int, offset: int) -> tuple[list[dict[str, Any]], int]:
        """Em quais lotes um número de nota apareceu (mesma normalização da chave canônica)."""
        busca = normalizar_nu_documento(nu_documento)
        with closing(self._conectar()) as conn:
            total = conn.execute("SELECT COUNT(*) FROM notas_lote WHERE nu_documento_busca = ?", (busca,)).fetchone()[0]
            linhas = conn.execute(
                """SELECT n.*, l.criado_em, l.modo, l.what_if, l.batch_hash,
                          (SELECT GROUP_CONCAT(codigo, ',') FROM erros_nota e WHERE e.nota_id = n.id) AS codigos
                   FROM notas_lote n JOIN lotes l ON l.id = n.lote_id
                   WHERE n.nu_documento_busca = ? ORDER BY n.id DESC LIMIT ? OFFSET ?""",
                (busca, limite, offset),
            ).fetchall()
        itens = []
        for linha in linhas:
            item = dict(linha)
            item["what_if"] = bool(item["what_if"])
            item["salva_pelo_otimizador"] = bool(item["salva_pelo_otimizador"])
            item["codigos_erro"] = item.pop("codigos").split(",") if item["codigos"] else []
            item.pop("id")
            item.pop("nu_documento_busca")
            itens.append(item)
        return itens, total
