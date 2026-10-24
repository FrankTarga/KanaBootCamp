"""Mock da consulta de CNPJ da Receita Federal, no formato da BrasilAPI.

GET /api/cnpj/v1/{cnpj} -> 200 {"cnpj", "razao_social", "descricao_situacao_cadastral"} | 404

Regra (a mesma do gabarito oficial): todo CNPJ com dígito verificador válido existe e está ATIVA, exceto os
listados em backend/data/situacao_cadastral.json (os irregulares). CNPJ com DV inválido = 404 (não existe).
Os sacados do estoque trazem a razão social. Em produção, aponte RECEITA_API_URL para a BrasilAPI real.

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


_PESOS = ((5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2), (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2))


def cnpj_valido(doc: str) -> bool:
    """DV do CNPJ (numérico ou alfanumérico); cópia pequena da regra do back-end, porque o mock roda isolado."""
    if len(doc) != 14 or not doc[12:].isdigit() or not doc[:12].isalnum() or len(set(doc)) == 1:
        return False
    base = doc[:12]
    for pesos in _PESOS:
        resto = sum((ord(c) - 48) * p for c, p in zip(base, pesos)) % 11
        base += "0" if resto < 2 else str(11 - resto)
    return base[12:] == doc[12:]


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
    doc = _limpar(cnpj)
    registro = BASE.get(doc)
    if registro is None:
        if not cnpj_valido(doc):
            raise HTTPException(404, "CNPJ não encontrado")
        registro = {"cnpj": doc, "razao_social": "", "descricao_situacao_cadastral": "ATIVA"}
    return registro
