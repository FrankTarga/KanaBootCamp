"""
scripts/raio_x_e_gerador_samples.py
Projeto ANTECIPE PRO — Raio-X Quant do Estoque + Fábrica de Amostras Cirúrgicas
(MEMBRO 3 / Estatístico-Quant)

Reaproveita deliberadamente a indexação e os parsers já construídos pelo Dev 1 em
backend/app/stock_index.py e backend/app/quant_analytics.py — a mesma função que
carrega o estoque na API (carregar_estoque) é usada aqui, então os números deste
relatório são garantidamente os mesmos que a API vai calcular no /health, e as
amostras usam os mesmos critérios de validação (RAIZ_CNPJ, normalização de
documento, zeros à esquerda do NU_DOCUMENTO etc.) do motor real.

Uso:
    python3 scripts/raio_x_e_gerador_samples.py
    python3 scripts/raio_x_e_gerador_samples.py --estoque outro.csv --validadores outro.json
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.br_utils import formatar_brl, formatar_data_br, formatar_percentual, parse_data_br  # noqa: E402
from app.stock_index import (  # noqa: E402
    AGRUPAMENTO_RAIZ,
    StockIndex,
    agrupar_documento,
    carregar_estoque,
    decodificar_csv,
    detectar_delimitador,
    iterar_linhas_csv,
    normalizar_documento,
)

COLUNAS = (
    "NOME_FUNDO", "DOC_FUNDO", "NOME_CEDENTE", "DOC_CEDENTE", "NOME_SACADO",
    "DOC_SACADO", "NU_DOCUMENTO", "TIPO_RECEBIVEL", "VALOR_NOMINAL",
    "DATA_VENCIMENTO_ORIGINAL", "DATA_AQUISICAO",
)


# ---------------------------------------------------------------------------
# Busca de nomes/linhas reais no CSV (StockIndex não guarda nomes, só docs)
# ---------------------------------------------------------------------------

def _ler_registros(caminho: Path) -> list[dict[str, str]]:
    texto = decodificar_csv(caminho.read_bytes())
    linhas = texto.splitlines()
    delim = detectar_delimitador(linhas[0])
    leitor = iter(iterar_linhas_csv(texto, delim))
    cabecalho = [c.strip().upper() for c in next(leitor)]
    idx = {nome: cabecalho.index(nome) for nome in COLUNAS if nome in cabecalho}
    registros = []
    for linha in leitor:
        if len(linha) < len(cabecalho) or not any(c.strip() for c in linha):
            continue
        registros.append({nome: linha[i] for nome, i in idx.items()})
    return registros


def eh_antecipe(nome_fundo: str, cnpj_fundo: str, alvo_cnpj: str, alvo_nome: str) -> bool:
    if alvo_cnpj or alvo_nome:
        return (alvo_cnpj and normalizar_documento(cnpj_fundo) == alvo_cnpj) or (
            alvo_nome and nome_fundo.strip().upper() == alvo_nome
        )
    return "ANTECIPE" in nome_fundo.strip().upper()


def mapear_nomes_e_achar_linhas(
    registros: list[dict[str, str]],
    raizes_sacado: set[str],
    raizes_cedente: set[str],
    alvo_cnpj: str,
    alvo_nome: str,
) -> dict:
    nomes_sacado: dict[str, tuple[str, str]] = {}   # raiz -> (nome, doc_original)
    nomes_cedente: dict[str, tuple[str, str]] = {}
    linha_antecipe_completa: dict[str, str] | None = None
    linha_outro_fundo: dict[str, str] | None = None

    for reg in registros:
        fundo_antecipe = eh_antecipe(reg.get("NOME_FUNDO", ""), reg.get("DOC_FUNDO", ""), alvo_cnpj, alvo_nome)

        if fundo_antecipe:
            if linha_antecipe_completa is None and all(reg.get(c, "").strip() for c in COLUNAS):
                linha_antecipe_completa = reg

            doc_sac = normalizar_documento(reg.get("DOC_SACADO", ""))
            raiz_sac = agrupar_documento(doc_sac, AGRUPAMENTO_RAIZ)
            if raiz_sac in raizes_sacado and raiz_sac not in nomes_sacado:
                nomes_sacado[raiz_sac] = (reg.get("NOME_SACADO", "").strip(), reg.get("DOC_SACADO", "").strip())

            doc_ced = normalizar_documento(reg.get("DOC_CEDENTE", ""))
            raiz_ced = agrupar_documento(doc_ced, AGRUPAMENTO_RAIZ)
            if raiz_ced in raizes_cedente and raiz_ced not in nomes_cedente:
                nomes_cedente[raiz_ced] = (reg.get("NOME_CEDENTE", "").strip(), reg.get("DOC_CEDENTE", "").strip())
        elif linha_outro_fundo is None and all(reg.get(c, "").strip() for c in COLUNAS):
            linha_outro_fundo = reg

    return {
        "nomes_sacado": nomes_sacado,
        "nomes_cedente": nomes_cedente,
        "linha_antecipe_completa": linha_antecipe_completa,
        "linha_outro_fundo": linha_outro_fundo,
    }


def pegar_validador(validadores_json: dict, codigo: str) -> dict | None:
    for v in validadores_json.get("validadores", []):
        if v.get("codigo") == codigo:
            return v
    return None


# ---------------------------------------------------------------------------
# PARTE A: Raio-X
# ---------------------------------------------------------------------------

def imprimir_raio_x(idx: StockIndex, registros: list[dict[str, str]], validadores_json: dict, alvo_cnpj: str, alvo_nome: str) -> dict:
    print("=" * 82)
    print("RAIO-X QUANT DO ESTOQUE — ANTECIPE FIDC")
    print("=" * 82)
    print(f"Total de linhas no estoque..............: {idx.total_linhas:,}".replace(",", "."))
    print(f"Linhas inválidas (ignoradas).............: {idx.linhas_invalidas:,}".replace(",", "."))
    print(f"Linhas do ANTECIPE FIDC..................: {idx.linhas_antecipe:,}".replace(",", "."))
    print(f"Fundos distintos encontrados no estoque..: {len(idx.fundos)}")
    print(f"Maior DATA_AQUISICAO (quinta-feira oficial): {formatar_data_br(idx.data_aquisicao_max) if idx.data_aquisicao_max else '(não encontrada)'}")
    print(f"Data-base padrão (próximo dia útil)......: {formatar_data_br(idx.data_base_padrao)}")
    print(f"Patrimônio total ANTECIPE FIDC...........: {formatar_brl(idx.patrimonio_antecipe)}")
    print(f"Tempo de carga do estoque.................: {idx.tempo_carga_ms} ms")

    top5_sacado = sorted(idx.exposicao_sacado_raiz.items(), key=lambda kv: kv[1], reverse=True)[:5]
    top5_cedente = sorted(idx.exposicao_cedente_raiz.items(), key=lambda kv: kv[1], reverse=True)[:5]

    mapa = mapear_nomes_e_achar_linhas(
        registros,
        {k for k, _ in top5_sacado},
        {k for k, _ in top5_cedente},
        alvo_cnpj, alvo_nome,
    )

    val_sacado = pegar_validador(validadores_json, "CONCENTRACAO_MAXIMA_SACADO")
    val_cedente = pegar_validador(validadores_json, "CONCENTRACAO_MAXIMA_CEDENTE")

    def imprimir_top5(titulo: str, top5: list[tuple[str, float]], nomes: dict, validador: dict | None):
        print()
        print(f"--- {titulo} ---")
        if not top5:
            print("(nenhum dado encontrado)")
            return
        status = "ATIVA" if validador and validador.get("ativo") else "INATIVA (não bloqueia hoje)"
        pct = (validador or {}).get("parametros", {}).get("percentual_maximo")
        for i, (raiz, acumulado) in enumerate(top5, start=1):
            nome, doc = nomes.get(raiz, ("(não encontrado no estoque)", raiz))
            if pct is not None:
                limite_reais = idx.patrimonio_antecipe * (float(pct) / 100.0)
                falta = max(0.0, limite_reais - acumulado)
                detalhe = f"limite {pct}% = {formatar_brl(limite_reais)} | falta {formatar_brl(falta)} | regra {status}"
            else:
                detalhe = f"sem limite percentual configurado | regra {status}"
            print(f"{i}. {nome} ({doc}) — acumulado {formatar_brl(acumulado)} | {detalhe}")

    imprimir_top5("TOP 5 SACADOS (maior exposição no ANTECIPE FIDC, por raiz de CNPJ)", top5_sacado, mapa["nomes_sacado"], val_sacado)
    imprimir_top5("TOP 5 CEDENTES (maior exposição no ANTECIPE FIDC, por raiz de CNPJ)", top5_cedente, mapa["nomes_cedente"], val_cedente)
    print()
    print("=" * 82)

    return {
        "top5_sacado": [(raiz, acumulado, *mapa["nomes_sacado"].get(raiz, ("Sacado Demo", raiz))) for raiz, acumulado in top5_sacado],
        "top5_cedente": [(raiz, acumulado, *mapa["nomes_cedente"].get(raiz, ("Cedente Demo", raiz))) for raiz, acumulado in top5_cedente],
        "linha_antecipe_completa": mapa["linha_antecipe_completa"],
        "linha_outro_fundo": mapa["linha_outro_fundo"],
    }


# ---------------------------------------------------------------------------
# PARTE B: Amostras
# ---------------------------------------------------------------------------

def fmt_valor(v: float) -> str:
    return f"{v:.2f}".replace(".", ",")


def fmt_data(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def linha(nome_fundo, doc_fundo, nome_cedente, doc_cedente, nome_sacado, doc_sacado,
          nu_documento, tipo, valor, venc: date, aquisicao: date) -> list[str]:
    return [nome_fundo, doc_fundo, nome_cedente, doc_cedente, nome_sacado, doc_sacado,
            nu_documento, tipo, fmt_valor(valor), fmt_data(venc), fmt_data(aquisicao)]


def escrever(caminho: Path, linhas: list[list[str]]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(COLUNAS)
        w.writerows(linhas)
    print(f"[OK] {caminho}  ({len(linhas)} linhas de dados)")


def gerar_01(caminho: Path, doc_fundo: str, nome_cedente: str, doc_cedente: str, validadores_json: dict, data_base: date):
    nome_fundo = "ANTECIPE FIDC"
    linhas = []
    for i in range(1, 19):
        venc = data_base + timedelta(days=15 + (i % 6) * 8)
        linhas.append(linha(nome_fundo, doc_fundo, nome_cedente, doc_cedente,
                             f"Cliente Demo {i:02d} LTDA", f"{10000000000000 + i * 111:014d}",
                             f"NF-{1000 + i}", "Duplicata", round(800 + i * 450.37, 2), venc, data_base))

    valor_minimo = (pegar_validador(validadores_json, "VALOR_MINIMO") or {}).get("parametros", {}).get("valor_minimo", 100.0)
    prazo_maximo = (pegar_validador(validadores_json, "PRAZO_MAXIMO") or {}).get("parametros", {}).get("prazo_maximo_dias", 180)
    tipos_aceitos = (pegar_validador(validadores_json, "TIPO_RECEBIVEL") or {}).get("parametros", {}).get("tipos_aceitos", ["Duplicata"])
    tipo_bloqueado = "Cheque" if "Cheque" not in tipos_aceitos else "CCB"

    linhas.append(linha(nome_fundo, doc_fundo, nome_cedente, doc_cedente,
                         "Sacado CNPJ Invalido LTDA", "11.111.111/1111-11", "NF-9001", "Duplicata",
                         2000.0, data_base + timedelta(days=30), data_base))
    linhas.append(linha(nome_fundo, doc_fundo, nome_cedente, doc_cedente,
                         "Sacado Situacao Baixada LTDA [cadastrar em situacao_cadastral.json]",
                         "22.222.222/0001-22", "NF-9002", "Duplicata", 1500.0,
                         data_base + timedelta(days=25), data_base))
    linhas.append(linha(nome_fundo, doc_fundo, nome_cedente, doc_cedente,
                         "Sacado Tipo Invalido LTDA", "33.333.333/0001-33", "NF-9003", tipo_bloqueado,
                         1800.0, data_base + timedelta(days=20), data_base))
    linhas.append(linha(nome_fundo, doc_fundo, nome_cedente, doc_cedente,
                         "Sacado Valor Baixo LTDA", "44.444.444/0001-44", "NF-9004", "Duplicata",
                         max(0.01, float(valor_minimo) - 1), data_base + timedelta(days=20), data_base))
    linhas.append(linha(nome_fundo, doc_fundo, nome_cedente, doc_cedente,
                         "Sacado Ja Vencido LTDA", "55.555.555/0001-55", "NF-9005", "Duplicata",
                         2200.0, data_base - timedelta(days=5), data_base))
    linhas.append(linha(nome_fundo, doc_fundo, nome_cedente, doc_cedente,
                         "Sacado Prazo Longo LTDA", "66.666.666/0001-66", "NF-9006", "Duplicata",
                         3000.0, data_base + timedelta(days=int(prazo_maximo) + 15), data_base))
    # dupla falha: VALOR_MINIMO + PRAZO_MAXIMO ao mesmo tempo (sem short-circuit)
    linhas.append(linha(nome_fundo, doc_fundo, nome_cedente, doc_cedente,
                         "Sacado Dupla Falha LTDA", "77.777.777/0001-77", "NF-9007", "Duplicata",
                         max(0.01, float(valor_minimo) - 1), data_base + timedelta(days=int(prazo_maximo) + 30), data_base))

    escrever(caminho, linhas)


def gerar_02(caminho: Path, doc_fundo: str, nome_cedente: str, doc_cedente: str, top5_sacado: list, data_base: date):
    nome_fundo = "ANTECIPE FIDC"
    if top5_sacado:
        _, _, nome_sacado, doc_sacado = top5_sacado[0]
    else:
        nome_sacado, doc_sacado = "Sacado Demo LTDA", "98.765.432/0001-88"
    prazos = [85, 75, 65, 55, 45, 35, 25, 20, 15, 10]
    linhas = [
        linha(nome_fundo, doc_fundo, nome_cedente, doc_cedente, nome_sacado, doc_sacado,
              f"NF-OTIM-{i:02d}", "Duplicata", 40000.0, data_base + timedelta(days=p), data_base)
        for i, p in enumerate(prazos, start=1)
    ]
    escrever(caminho, linhas)


def gerar_03(caminho: Path, doc_fundo: str, nome_cedente: str, doc_cedente: str,
             linha_antecipe: dict | None, linha_outro_fundo: dict | None, data_base: date):
    nome_fundo = "ANTECIPE FIDC"
    linhas = []
    for i in range(1, 6):
        venc = data_base + timedelta(days=20 + i * 5)
        linhas.append(linha(nome_fundo, doc_fundo, nome_cedente, doc_cedente,
                             f"Sacado Fraude Demo {i} LTDA", f"{20000000000000 + i * 222:014d}",
                             f"NF-FRAUDE-{i:02d}", "Duplicata", round(1500.0 + i * 300, 2), venc, data_base))
    linhas.append(list(linhas[0]))  # DUPLICIDADE_LOTE

    if linha_antecipe:
        linhas.append([linha_antecipe[c] for c in COLUNAS])  # DUPLICIDADE_FUNDO
    else:
        print("[AVISO] Não achei no estoque uma linha completa do ANTECIPE FIDC para DUPLICIDADE_FUNDO.", file=sys.stderr)
        linhas.append(list(linhas[0]))

    if linha_outro_fundo:
        linhas.append([linha_outro_fundo[c] for c in COLUNAS])  # FRAUDE_OUTRO_FUNDO
        print(f"[INFO] FRAUDE_OUTRO_FUNDO copiada de '{linha_outro_fundo.get('NOME_FUNDO')}'.")
    else:
        print("[AVISO] Não achei no estoque uma linha completa de outro fundo para FRAUDE_OUTRO_FUNDO.", file=sys.stderr)
        linhas.append(list(linhas[1]))

    escrever(caminho, linhas)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--estoque", type=Path, default=PROJECT_ROOT / "backend" / "data" / "estoque_antecipe.csv")
    parser.add_argument("--validadores", type=Path, default=PROJECT_ROOT / "backend" / "data" / "validadores_antecipe.json")
    parser.add_argument("--samples-dir", type=Path, default=PROJECT_ROOT / "samples")
    args = parser.parse_args()

    if not args.estoque.exists():
        print(f"[ERRO] estoque não encontrado: {args.estoque}", file=sys.stderr)
        sys.exit(1)
    if not args.validadores.exists():
        print(f"[ERRO] validadores não encontrado: {args.validadores}", file=sys.stderr)
        sys.exit(1)

    validadores_json = json.loads(args.validadores.read_text(encoding="utf-8-sig"))
    nome_fundo = validadores_json.get("fundo", {}).get("nome", "ANTECIPE FIDC")
    cnpj_fundo = validadores_json.get("fundo", {}).get("cnpj", "")

    idx = carregar_estoque(args.estoque, nome_fundo, cnpj_fundo)
    registros = _ler_registros(args.estoque)

    relatorio = imprimir_raio_x(idx, registros, validadores_json, normalizar_documento(cnpj_fundo), nome_fundo.strip().upper())

    linha_antecipe = relatorio["linha_antecipe_completa"]
    doc_fundo = (linha_antecipe or {}).get("DOC_FUNDO") or cnpj_fundo
    nome_cedente_base = (linha_antecipe or {}).get("NOME_CEDENTE") or "Empresa Demo Hackathon LTDA"
    doc_cedente_base = (linha_antecipe or {}).get("DOC_CEDENTE") or "99.999.999/0001-99"

    args.samples_dir.mkdir(parents=True, exist_ok=True)
    gerar_01(args.samples_dir / "01_lote_empresarial_padrao.csv", doc_fundo, nome_cedente_base, doc_cedente_base,
             validadores_json, idx.data_base_padrao)
    gerar_02(args.samples_dir / "02_demo_otimizador_concentracao.csv", doc_fundo, nome_cedente_base, doc_cedente_base,
             relatorio["top5_sacado"], idx.data_base_padrao)
    gerar_03(args.samples_dir / "03_demo_radar_antifraude.csv", doc_fundo, nome_cedente_base, doc_cedente_base,
             linha_antecipe, relatorio["linha_outro_fundo"], idx.data_base_padrao)

    print()
    print("Pronto. As 3 amostras em samples/ foram (re)geradas com dados reais do estoque.")


if __name__ == "__main__":
    main()
