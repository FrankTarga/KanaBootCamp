"""Mock da consulta de CNPJ da Receita Federal, no formato da BrasilAPI.

GET /api/cnpj/v1/{cnpj} -> 200 {"cnpj", "razao_social", "descricao_situacao_cadastral"} | 404

Regra: todo CNPJ com dígito verificador válido existe e está ATIVA, exceto os que a fonte escolhida em
SITUACAO_FONTE marca como não-ATIVA. CNPJ com DV inválido = 404 (não existe). As fontes se contradizem entre si,
por isso são escolhíveis:
- gabarito (padrão): backend/data/situacao_cadastral.json, os 87 irregulares do resultado_esperado_100k.json;
- kanastra: backend/data/cnpj_situacao_mock.csv, publicado pela organização (DOC;SITUACAO_CADASTRAL);
  CNPJ ausente do arquivo = ATIVA (decisão do time);
- formato: nenhuma restrição, só a checagem do CNPJ (a regra vira "CNPJ válido de 14 dígitos").
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
FONTES = {"gabarito": "situacao_cadastral.json", "kanastra": "cnpj_situacao_mock.csv", "formato": None}
FONTE = os.getenv("SITUACAO_FONTE", "gabarito").strip().lower()


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


def carregar_sobrescritas(fonte: str) -> dict[str, str]:
    """CNPJ -> situação da fonte escolhida. Falha no boot se a fonte for inválida ou o arquivo faltar."""
    if fonte not in FONTES:
        raise ValueError(f"SITUACAO_FONTE '{fonte}' inválida; use {', '.join(FONTES)}")
    if FONTES[fonte] is None:
        return {}
    caminho = DATA_DIR / FONTES[fonte]
    if fonte == "kanastra":
        with open(caminho, encoding="utf-8-sig", newline="") as arquivo:
            pares = [(l["DOC"], l["SITUACAO_CADASTRAL"]) for l in csv.DictReader(arquivo, delimiter=";")]
    else:
        pares = list(json.loads(caminho.read_text(encoding="utf-8-sig")).get("situacoes", {}).items())
    return {_limpar(doc): str(situacao).strip().upper() for doc, situacao in pares if _limpar(doc)}


def carregar_base(fonte: str = FONTE) -> dict[str, dict[str, str]]:
    base: dict[str, dict[str, str]] = {}
    with open(DATA_DIR / "estoque_antecipe.csv", encoding="utf-8-sig", newline="") as arquivo:
        for linha in csv.DictReader(arquivo, delimiter=";"):
            doc = _limpar(linha["DOC_SACADO"])
            base.setdefault(doc, {"cnpj": doc, "razao_social": linha["NOME_SACADO"].strip(), "descricao_situacao_cadastral": "ATIVA"})
    for doc, situacao in carregar_sobrescritas(fonte).items():
        base.setdefault(doc, {"cnpj": doc, "razao_social": ""})["descricao_situacao_cadastral"] = situacao
    return base


BASE = carregar_base()
app = FastAPI(title="Mock Receita Federal (CNPJ)")


@app.get("/health")
def health() -> dict:
    nao_ativos = sum(1 for r in BASE.values() if r["descricao_situacao_cadastral"] != "ATIVA")
    return {"status": "ready", "fonte": FONTE, "cnpjs_nao_ativos": nao_ativos}


@app.get("/api/cnpj/v1/{cnpj}")
def consultar(cnpj: str) -> dict[str, str]:
    doc = _limpar(cnpj)
    registro = BASE.get(doc)
    if registro is None:
        if not cnpj_valido(doc):
            raise HTTPException(404, "CNPJ não encontrado")
        registro = {"cnpj": doc, "razao_social": "", "descricao_situacao_cadastral": "ATIVA"}
    return registro
