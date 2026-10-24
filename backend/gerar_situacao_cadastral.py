"""Gera data/situacao_cadastral.json a partir do gabarito oficial resultado_esperado_100k.json.

Decisão do time (tech lead, 24/10/2026): o kit não trouxe a fonte de situação cadastral usada pela
organização e os CNPJs do dataset são sintéticos (a Receita real diverge), então os CNPJs barrados por
SITUACAO_CADASTRAL_SACADO no gabarito viram a nossa base de referência. O gabarito não diz QUAL é a
situação, só que não é ATIVA: por isso o rótulo é "IRREGULAR".

Rodar (da pasta backend/): .venv\\Scripts\\python gerar_situacao_cadastral.py
"""

import csv
import json
from pathlib import Path

BACKEND = Path(__file__).resolve().parent
ESTOQUE = BACKEND / "data" / "estoque_antecipe.csv"
GABARITO = BACKEND.parent / "resultado_esperado_100k.json"
DESTINO = BACKEND / "data" / "situacao_cadastral.json"


def main() -> None:
    with open(ESTOQUE, encoding="utf-8-sig", newline="") as arquivo:
        sacados = [linha["DOC_SACADO"].strip() for linha in csv.DictReader(arquivo, delimiter=";")]
    gabarito = json.loads(GABARITO.read_text(encoding="utf-8"))
    irregulares = sorted({
        sacados[item["linha"] - 2]
        for item in gabarito
        if "SITUACAO_CADASTRAL_SACADO" in item.get("barrado_por", [])
    })
    conteudo = {
        "_comentario": (
            "Situação cadastral por CNPJ do sacado. Gerado por gerar_situacao_cadastral.py a partir do gabarito "
            "oficial (os CNPJs barrados por SITUACAO_CADASTRAL_SACADO), porque o kit não trouxe a fonte da "
            "organização. O mock-receita serve estes valores; sem RECEITA_API_URL, este arquivo é a fonte e CNPJ "
            "ausente é RECUSADO (fail-closed)."
        ),
        "situacoes": {doc: "IRREGULAR" for doc in irregulares},
    }
    DESTINO.write_text(json.dumps(conteudo, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"{len(irregulares)} CNPJs irregulares gravados em {DESTINO.name}")


if __name__ == "__main__":
    main()
