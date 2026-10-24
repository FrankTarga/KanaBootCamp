"""Análise descritiva das recusas nas 100.554 linhas do estoque, usando o gabarito oficial.

Uso: python scripts/analise_recusas_estoque.py
Preço de cada nota calculado como no modo carteira (data de referência = DATA_AQUISICAO).
"""

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "backend"))

from app.analise_recusas import analisar_recusas  # noqa: E402
from app.api_schemas import PrecificacaoConfig  # noqa: E402
from app.br_utils import formatar_brl, parse_data_br  # noqa: E402
from app.rule_engine import REGRAS, RuleEngine, carregar_config, ler_lote_csv, montar_linha  # noqa: E402

DADOS = RAIZ / "backend" / "data"
config = carregar_config(DADOS / "validadores_antecipe.json")
taxa = RuleEngine.taxa_configurada(config)
precificacao = config.precificacao or PrecificacaoConfig()
gabarito = json.loads((RAIZ / "resultado_esperado_100k.json").read_text(encoding="utf-8"))
registros = ler_lote_csv((DADOS / "estoque_antecipe.csv").read_bytes())
assert len(registros) == len(gabarito)

itens = []
for (numero, registro), g in zip(registros, gabarito):
    linha = montar_linha(numero, registro, parse_data_br(registro["DATA_AQUISICAO"]), taxa, precificacao)
    codigos = g.get("barrado_por", [])
    itens.append({
        "status": "RECUSADA" if codigos else "APROVADA",
        "valor_nominal": linha.valor_nominal,
        "valor_liquido": linha.valor_liquido,
        "erros": [{"codigo": c, "titulo_amigavel": REGRAS[c].titulo_amigavel} for c in codigos],
    })

r = analisar_recusas(itens)
def n(x: int) -> str:
    return f"{x:,}".replace(",", ".")


def pct(x: float) -> str:
    return f"{x:.1f}%".replace(".", ",")


print(f"{n(r['qtd_recusadas'])} notas recusadas, {formatar_brl(r['valor_recusado'])} em valor nominal")
print(f"{n(r['qtd_com_mais_de_um_erro'])} delas ({pct(r['pct_com_mais_de_um_erro'])}) têm mais de um erro\n")
print(f"{'motivo':48s} {'notas':>7s} {'% recus.':>8s} {'R$ impactado':>20s} {'só este':>8s} {'R$ líquido liberado':>20s}")
for m in r["motivos"]:
    liberado = ("não corrigível" if not m["corrigivel"]
                else "sem estimativa" if m["liquido_liberado"] is None else formatar_brl(m["liquido_liberado"]))
    print(f"{m['titulo_amigavel']:48s} {n(m['qtd_notas']):>7s} {pct(m['pct_das_recusadas']):>8s} "
          f"{formatar_brl(m['valor_impactado']):>20s} {n(m['qtd_so_este_erro']):>8s} {liberado:>20s}")
