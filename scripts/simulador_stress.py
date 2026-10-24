"""Simulador de stress do motor de regras (Estatístico/Quant).

Gera lotes sintéticos de tamanhos crescentes com clientes reais do estoque e mede, no próprio
motor (sem HTTP), quanto tempo cada lote leva, quantas notas por segundo e a taxa de aprovação.
No fim, valida a carteira inteira (100.554 notas) no modo carteira.

Uso (na raiz do repositório):
    python scripts/simulador_stress.py                 # 1.000, 5.000 e 10.000 notas + carteira
    python scripts/simulador_stress.py --tamanhos 500 2000 --sem-carteira

Situação cadastral: os 87 CNPJs irregulares de backend/data/situacao_cadastral.json; os demais
sacados do estoque contam como ATIVA (como no mock da Receita). Nada é gravado no repositório.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import statistics
import sys
import tempfile
import time
from datetime import timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BACKEND = RAIZ / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.br_utils import formatar_data_br  # noqa: E402
from app.rule_engine import CadastroSituacao, RuleEngine, carregar_config  # noqa: E402
from app.stock_index import carregar_estoque  # noqa: E402

DADOS = BACKEND / "data"
CABECALHO = ("NOME_FUNDO;DOC_FUNDO;NOME_CEDENTE;DOC_CEDENTE;NOME_SACADO;DOC_SACADO;NU_DOCUMENTO;"
             "TIPO_RECEBIVEL;VALOR_NOMINAL;DATA_VENCIMENTO_ORIGINAL;DATA_AQUISICAO")
TIPOS = ["Duplicata"] * 7 + ["Duplicata de Serviço"] * 2 + ["CCB", "Cheque"]


def pt(texto: str) -> str:
    """1,234.5 -> 1.234,5 (formato brasileiro)."""
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def brl(v: float) -> str:
    return pt(f"{v:,.2f}")


def montar_motor(pasta_tmp: Path) -> tuple[RuleEngine, list[dict[str, str]]]:
    config = carregar_config(DADOS / "validadores_antecipe.json")
    t0 = time.perf_counter()
    index = carregar_estoque(DADOS / "estoque_antecipe.csv", config.fundo.nome, config.fundo.cnpj)
    print(pt(f"Estoque carregado: {index.total_linhas:,} linhas em {time.perf_counter() - t0:.2f} s"))

    with open(DADOS / "estoque_antecipe.csv", encoding="utf-8-sig", newline="") as f:
        linhas = list(csv.DictReader(f, delimiter=";"))
    irregulares = json.loads((DADOS / "situacao_cadastral.json").read_text(encoding="utf-8"))["situacoes"]
    situacoes = {"".join(c for c in l["DOC_SACADO"] if c.isdigit()): "ATIVA" for l in linhas}
    situacoes.update(irregulares)
    (pasta_tmp / "situacao.json").write_text(json.dumps({"situacoes": situacoes}), encoding="utf-8")
    # cópia do JSON de regras: o motor nunca grava no arquivo do repositório
    (pasta_tmp / "validadores.json").write_bytes((DADOS / "validadores_antecipe.json").read_bytes())
    motor = RuleEngine(index, config, pasta_tmp / "validadores.json", CadastroSituacao(pasta_tmp / "situacao.json"),
                       max_linhas_lote=1_000_000)
    return motor, linhas


def gerar_lote(n: int, linhas: list[dict[str, str]], motor: RuleEngine, rnd: random.Random) -> bytes:
    base = motor.index.data_base_padrao
    saida = [CABECALHO]
    for i in range(n):
        modelo = rnd.choice(linhas)  # cliente e empresa reais do estoque
        prazo = rnd.choice([rnd.randint(5, 60), rnd.randint(30, 150), rnd.randint(150, 240)])
        valor = round(rnd.lognormvariate(8.6, 1.0), 2)  # mediana ~R$ 5,4 mil, cauda longa
        saida.append(";".join([
            "ANTECIPE FIDC", "92.234.400/0001-80", modelo["NOME_CEDENTE"], modelo["DOC_CEDENTE"],
            modelo["NOME_SACADO"], modelo["DOC_SACADO"], f"STRESS-{n}-{i:07d}", rnd.choice(TIPOS),
            brl(valor), formatar_data_br(base + timedelta(days=prazo)), formatar_data_br(base),
        ]))
    return ("\n".join(saida) + "\n").encode("utf-8")


def medir(nome: str, funcao, repeticoes: int) -> tuple[float, object]:
    tempos, resultado = [], None
    for _ in range(repeticoes):
        t0 = time.perf_counter()
        resultado = funcao()
        tempos.append(time.perf_counter() - t0)
    return statistics.median(tempos), resultado


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tamanhos", type=int, nargs="+", default=[1_000, 5_000, 10_000])
    ap.add_argument("--repeticoes", type=int, default=3, help="mediana de N execuções por tamanho")
    ap.add_argument("--sem-carteira", action="store_true", help="não roda a carteira de 100k")
    ap.add_argument("--semente", type=int, default=42)
    args = ap.parse_args()

    rnd = random.Random(args.semente)
    with tempfile.TemporaryDirectory() as tmp:
        motor, linhas = montar_motor(Path(tmp))
        print(f"\n{'notas':>8} | {'tempo (mediana)':>15} | {'notas/s':>9} | {'aprovadas':>9} | {'ganho otimizador':>16}")
        print("-" * 70)
        for n in args.tamanhos:
            lote = gerar_lote(n, linhas, motor, rnd)
            seg, r = medir(f"lote {n}", lambda: motor.validar_lote(lote), args.repeticoes)
            pct = 100 * r.resumo.qtd_aprovadas / r.resumo.total_notas
            print(pt(f"{n:>8,} | {seg:>13.2f} s | {n / seg:>9,.0f} | {pct:>8.1f}%") + f" | R$ {brl(r.meta.ganho_otimizador_reais):>13}")

        if not args.sem_carteira:
            conteudo = (DADOS / "estoque_antecipe.csv").read_bytes()
            seg, regs = medir("carteira", lambda: motor.validar_carteira(conteudo), 1)
            print(pt(f"\nCarteira inteira (modo carteira): {len(regs):,} notas em {seg:.2f} s ({len(regs) / seg:,.0f} notas/s)"))


if __name__ == "__main__":
    main()
