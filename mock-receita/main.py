"""Mock da consulta de CNPJ da Receita Federal, no formato da BrasilAPI.

GET /api/cnpj/v1/{cnpj} -> 200 {"cnpj", "razao_social", "descricao_situacao_cadastral"} | 404

Base: todo sacado do estoque como ATIVA, sobrescrito por backend/data/situacao_cadastral.json
(BAIXADA, INAPTA... para a demo). Em produção, aponte RECEITA_API_URL do back-end para a BrasilAPI real.

Rodar: backend/.venv/Scripts/python -m uvicorn main:app --app-dir mock-receita --port 8001
"""

import csv
import json
import os
import re
from pathlib import Path

from fastapi import FastAPI, HTTPException

DATA_DIR = Path(os.getenv("DATA_DIR", Path(__file__).resolve().parent.parent / "backend" / "data"))


def _limpar(doc: str) -> str:
    return re.sub(r"[^0-9A-Za-z]", "", doc).upper()


def carregar_base() -> dict[str, dict[str, str]]:
    base: dict[str, dict[str, str]] = {}
    with open(DATA_DIR / "estoque_antecipe.csv", encoding="utf-8-sig", newline="") as arquivo:
        for linha in csv.DictReader(arquivo, delimiter=";"):
            doc = _limpar(linha["DOC_SACADO"])
            base.setdefault(doc, {"cnpj": doc, "razao_social": linha["NOME_SACADO"].strip(), "descricao_situacao_cadastral": "ATIVA"})
    sobrescritas = DATA_DIR / "situacao_cadastral.json"
    if sobrescritas.exists():
        for doc, situacao in json.loads(sobrescritas.read_text(encoding="utf-8-sig")).get("situacoes", {}).items():
            doc = _limpar(doc)
            base.setdefault(doc, {"cnpj": doc, "razao_social": ""})["descricao_situacao_cadastral"] = str(situacao).upper()
    return base


BASE = carregar_base()
app = FastAPI(title="Mock Receita Federal (CNPJ)")


@app.get("/api/cnpj/v1/{cnpj}")
def consultar(cnpj: str) -> dict[str, str]:
    registro = BASE.get(_limpar(cnpj))
    if registro is None:
        raise HTTPException(404, "CNPJ não encontrado")
    return registro
