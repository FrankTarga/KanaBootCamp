"""Histórico persistente (SQLite da biblioteca padrão): lotes validados, suas notas e mudanças de regras.

Os 100k títulos do estoque continuam em RAM (StockIndex); aqui fica só o registro de auditoria.
- lotes: o resumo de toda validação (inclusive repetições servidas pelo cache e o modo carteira);
- notas_lote + erros_nota: o detalhe nota a nota, só do modo lote (uma carteira de 100k notas daria
  dezenas de MB por envio e é o próprio estoque, que já está em disco);
- mudancas_regras: cada PUT /validators aceito;
- usuarios: login do portal, senha só como hash scrypt com salt.
Uma conexão por operação: seguro com as threads do FastAPI e sem estado compartilhado.

Esquema versionado em PRAGMA user_version: cada item de _MIGRACOES roda uma vez, em ordem e numa transação.
Para mudar o esquema, acrescente um passo no fim (nunca edite um passo já aplicado em algum banco).
Modo WAL: leituras do histórico não esperam a gravação de um lote grande.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .stock_index import normalizar_nu_documento

_SCHEMA_INICIAL = """
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
CREATE TABLE IF NOT EXISTS usuarios (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    email      TEXT    NOT NULL UNIQUE,  -- sempre minúsculo e sem espaços
    senha_hash TEXT    NOT NULL,         -- scrypt$<salt hex>$<hash hex>
    nome       TEXT    NOT NULL,
    cargo      TEXT    NOT NULL,
    role       TEXT    NOT NULL CHECK (role IN ('CEDENTE', 'GESTOR')),
    criado_em  TEXT    NOT NULL
);
"""

_MIGRACOES = (
    # 1: tabelas base. IF NOT EXISTS: bancos criados antes do versionamento (user_version 0) passam direto
    _SCHEMA_INICIAL,
    # 2: quem enviou cada lote e quem mudou cada regra (NULL = chamada sem login, ex.: Swagger/curl)
    """
    ALTER TABLE lotes ADD COLUMN usuario_id INTEGER REFERENCES usuarios (id);
    ALTER TABLE mudancas_regras ADD COLUMN usuario_id INTEGER REFERENCES usuarios (id);
    CREATE INDEX IF NOT EXISTS ix_lotes_usuario ON lotes (usuario_id, id);
    """,
)
VERSAO_ESQUEMA = len(_MIGRACOES)


def migrar(conn: sqlite3.Connection) -> int:
    """Aplica os passos que faltam; devolve a versão final. DDL do SQLite é transacional: ou o passo entra inteiro ou não."""
    versao = conn.execute("PRAGMA user_version").fetchone()[0]
    for numero in range(versao + 1, VERSAO_ESQUEMA + 1):
        conn.executescript(f"BEGIN;\n{_MIGRACOES[numero - 1]}\nPRAGMA user_version = {numero};\nCOMMIT;")
    return conn.execute("PRAGMA user_version").fetchone()[0]

_COLUNAS_NOTA = (
    "linha_csv", "nu_documento", "nome_cedente", "doc_cedente", "nome_sacado", "doc_sacado", "tipo_recebivel",
    "valor_nominal", "data_vencimento", "prazo_dias", "desagio_reais", "valor_liquido", "status", "severidade",
    "salva_pelo_otimizador",
)
_BOOLEANOS_LOTE = ("otimizar_lote", "what_if", "replay")


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def hash_senha(senha: str, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    digest = hashlib.scrypt(senha.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt${salt.hex()}${digest.hex()}"


def senha_confere(senha: str, guardado: str) -> bool:
    _, salt_hex, _ = guardado.split("$")
    return hmac.compare_digest(hash_senha(senha, bytes.fromhex(salt_hex)), guardado)


# e-mail inexistente também paga o custo do scrypt: o tempo de resposta não entrega quais e-mails existem
_HASH_FALSO = hash_senha("usuario-inexistente")


def _lote(linha: sqlite3.Row) -> dict[str, Any]:
    item = dict(linha)
    for campo in _BOOLEANOS_LOTE:
        item[campo] = bool(item[campo])
    return item


class Historico:
    def __init__(self, caminho: Path):
        self.caminho = Path(caminho)
        with closing(self._conectar()) as conn:
            conn.execute("PRAGMA journal_mode = WAL")  # fica gravado no arquivo: vale para as próximas conexões
            migrar(conn)

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
                sql_nota = (
                    f"INSERT INTO notas_lote (lote_id, nu_documento_busca, {', '.join(_COLUNAS_NOTA)}) "
                    f"VALUES (?, ?, {', '.join('?' for _ in _COLUNAS_NOTA)})"
                )
                erros = []
                for item in itens:
                    nota_id = conn.execute(
                        sql_nota,
                        (lote_id, normalizar_nu_documento(item.nu_documento), *(getattr(item, c) for c in _COLUNAS_NOTA)),
                    ).lastrowid
                    erros += [
                        (nota_id, ordem, e.codigo, e.titulo_amigavel, e.mensagem_empresa, e.acao_recomendada)
                        for ordem, e in enumerate(item.erros)
                    ]
                conn.executemany(
                    "INSERT INTO erros_nota (nota_id, ordem, codigo, titulo_amigavel, mensagem_empresa, acao_recomendada) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    erros,
                )
        return lote_id

    def registrar_mudanca_regras(
        self, request_id: str, versao_config: int, regras_ativas: int, config: dict, usuario_id: int | None = None
    ) -> None:
        with closing(self._conectar()) as conn, conn:
            conn.execute(
                "INSERT INTO mudancas_regras (criado_em, request_id, versao_config, regras_ativas, config_json, usuario_id) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (_agora(), request_id, versao_config, regras_ativas, json.dumps(config, ensure_ascii=False), usuario_id),
            )

    def salvar_usuario(self, email: str, senha: str, nome: str, cargo: str, role: str) -> None:
        """Cria o usuário ou, se o e-mail já existe, troca senha e dados (o seed do startup roda toda vez)."""
        with closing(self._conectar()) as conn, conn:
            conn.execute(
                "INSERT INTO usuarios (email, senha_hash, nome, cargo, role, criado_em) VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT (email) DO UPDATE SET senha_hash = excluded.senha_hash, nome = excluded.nome, "
                "cargo = excluded.cargo, role = excluded.role",
                (email.strip().lower(), hash_senha(senha), nome, cargo, role, _agora()),
            )

    def autenticar(self, email: str, senha: str) -> dict[str, Any] | None:
        with closing(self._conectar()) as conn:
            linha = conn.execute(
                "SELECT id, email, senha_hash, nome, cargo, role FROM usuarios WHERE email = ?", (email.strip().lower(),)
            ).fetchone()
        if not senha_confere(senha, linha["senha_hash"] if linha else _HASH_FALSO) or linha is None:
            return None
        usuario = dict(linha)
        usuario.pop("senha_hash")
        return usuario

    # ----------------------------------------------------------------- leitura

    def _pagina(
        self, tabela: str, limite: int, offset: int, usuario_id: int | None = None
    ) -> tuple[list[sqlite3.Row], int]:
        # tabela vem só de listar_* (nunca do usuário); filtro, limite e offset vão como parâmetros
        onde, filtro = ("WHERE usuario_id = ?", (usuario_id,)) if usuario_id is not None else ("", ())
        with closing(self._conectar()) as conn:
            total = conn.execute(f"SELECT COUNT(*) FROM {tabela} {onde}", filtro).fetchone()[0]
            linhas = conn.execute(
                f"SELECT * FROM {tabela} {onde} ORDER BY id DESC LIMIT ? OFFSET ?", (*filtro, limite, offset)
            ).fetchall()
        return linhas, total

    def listar_lotes(self, limite: int, offset: int, usuario_id: int | None = None) -> tuple[list[dict[str, Any]], int]:
        """usuario_id = só os lotes desse usuário (cedente); None = todos (gestor)."""
        linhas, total = self._pagina("lotes", limite, offset, usuario_id)
        return [_lote(l) for l in linhas], total

    def listar_mudancas_regras(self, limite: int, offset: int) -> tuple[list[dict[str, Any]], int]:
        linhas, total = self._pagina("mudancas_regras", limite, offset)
        itens = []
        for linha in linhas:
            item = dict(linha)
            item["config"] = json.loads(item.pop("config_json"))
            itens.append(item)
        return itens, total

    def obter_lote(self, lote_id: int, limite: int, offset: int, usuario_id: int | None = None) -> dict[str, Any] | None:
        """Resumo + notas (com erros) de um lote. Repetição do cache mostra as notas do envio original.
        Com usuario_id, lote de outro usuário é tratado como inexistente (não revela que existe)."""
        with closing(self._conectar()) as conn:
            linha = conn.execute("SELECT * FROM lotes WHERE id = ?", (lote_id,)).fetchone()
            if linha is None or (usuario_id is not None and linha["usuario_id"] != usuario_id):
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

    def buscar_nota(
        self, nu_documento: str, limite: int, offset: int, usuario_id: int | None = None
    ) -> tuple[list[dict[str, Any]], int]:
        """Em quais lotes um número de nota apareceu (mesma normalização da chave canônica)."""
        busca = normalizar_nu_documento(nu_documento)
        onde = "n.nu_documento_busca = ?" + (" AND l.usuario_id = ?" if usuario_id is not None else "")
        filtro = (busca, usuario_id) if usuario_id is not None else (busca,)
        with closing(self._conectar()) as conn:
            total = conn.execute(
                f"SELECT COUNT(*) FROM notas_lote n JOIN lotes l ON l.id = n.lote_id WHERE {onde}", filtro
            ).fetchone()[0]
            linhas = conn.execute(
                f"""SELECT n.*, l.criado_em, l.modo, l.what_if, l.batch_hash,
                           (SELECT GROUP_CONCAT(codigo, ',') FROM erros_nota e WHERE e.nota_id = n.id) AS codigos
                    FROM notas_lote n JOIN lotes l ON l.id = n.lote_id
                    WHERE {onde} ORDER BY n.id DESC LIMIT ? OFFSET ?""",
                (*filtro, limite, offset),
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
