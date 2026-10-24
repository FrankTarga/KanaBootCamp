"""Histórico persistente (SQLite da biblioteca padrão): lotes validados e mudanças de regras.

Os 100k títulos do estoque continuam em RAM (StockIndex); aqui fica só o registro de auditoria.
Não guarda o payload da resposta (uma carteira de 100k dá ~65 MB), só os números e a chave completa.
Uma conexão por operação: seguro com as threads do FastAPI e sem estado compartilhado.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SCHEMA = """
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
CREATE TABLE IF NOT EXISTS mudancas_regras (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    criado_em     TEXT    NOT NULL,
    request_id    TEXT    NOT NULL,
    versao_config INTEGER NOT NULL,
    regras_ativas INTEGER NOT NULL,
    config_json   TEXT    NOT NULL
);
"""


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Historico:
    def __init__(self, caminho: Path):
        self.caminho = Path(caminho)
        with closing(self._conectar()) as conn, conn:
            conn.executescript(_SCHEMA)

    def _conectar(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.caminho, timeout=5)
        conn.row_factory = sqlite3.Row
        return conn

    def registrar_lote(self, **campos: Any) -> None:
        campos = {"criado_em": _agora(), **campos}
        colunas = ", ".join(campos)
        marcadores = ", ".join("?" for _ in campos)
        with closing(self._conectar()) as conn, conn:
            conn.execute(f"INSERT INTO lotes ({colunas}) VALUES ({marcadores})", list(campos.values()))

    def registrar_mudanca_regras(self, request_id: str, versao_config: int, regras_ativas: int, config: dict) -> None:
        with closing(self._conectar()) as conn, conn:
            conn.execute(
                "INSERT INTO mudancas_regras (criado_em, request_id, versao_config, regras_ativas, config_json) "
                "VALUES (?, ?, ?, ?, ?)",
                (_agora(), request_id, versao_config, regras_ativas, json.dumps(config, ensure_ascii=False)),
            )

    def _pagina(self, tabela: str, limite: int, offset: int) -> tuple[list[dict[str, Any]], int]:
        # tabela vem só de listar_* (nunca do usuário); limite e offset vão como parâmetros
        with closing(self._conectar()) as conn:
            total = conn.execute(f"SELECT COUNT(*) FROM {tabela}").fetchone()[0]
            linhas = conn.execute(f"SELECT * FROM {tabela} ORDER BY id DESC LIMIT ? OFFSET ?", (limite, offset)).fetchall()
        return [dict(linha) for linha in linhas], total

    def listar_lotes(self, limite: int, offset: int) -> tuple[list[dict[str, Any]], int]:
        itens, total = self._pagina("lotes", limite, offset)
        for item in itens:
            for campo in ("otimizar_lote", "what_if", "replay"):
                item[campo] = bool(item[campo])
        return itens, total

    def listar_mudancas_regras(self, limite: int, offset: int) -> tuple[list[dict[str, Any]], int]:
        itens, total = self._pagina("mudancas_regras", limite, offset)
        for item in itens:
            item["config"] = json.loads(item.pop("config_json"))
        return itens, total
