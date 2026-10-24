"""Indexação O(1) em RAM do estoque histórico (~100k linhas) carregado no startup."""

from __future__ import annotations

import csv
import hashlib
import io
import re
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from .br_utils import formatar_data_br, parse_data_br, parse_valor_br, proximo_dia_util

DATA_BASE_FALLBACK = date(2026, 10, 22)

AGRUPAMENTO_RAIZ = "RAIZ_CNPJ"
AGRUPAMENTO_DOCUMENTO = "CNPJ"

_RE_DOC = re.compile(r"[^0-9A-Za-z]")

COLUNAS_ESTOQUE = (
    "NOME_FUNDO",
    "DOC_FUNDO",
    "DOC_CEDENTE",
    "DOC_SACADO",
    "NU_DOCUMENTO",
    "VALOR_NOMINAL",
    "DATA_VENCIMENTO_ORIGINAL",
    "DATA_AQUISICAO",
)


def normalizar_documento(doc: str | None) -> str:
    """Remove pontos, barras, traços e espaços (mantém letras do CNPJ alfanumérico)."""
    return _RE_DOC.sub("", str(doc or "")).upper()


def agrupar_documento(doc_limpo: str, agrupamento: str) -> str:
    """Chave de agrupamento: raiz (8 primeiros caracteres) para CNPJ, documento inteiro para CPF."""
    if agrupamento == AGRUPAMENTO_RAIZ and len(doc_limpo) == 14:
        return doc_limpo[:8]
    return doc_limpo


def normalizar_nu_documento(nu_documento: str | None) -> str:
    """strip().upper() da spec + zeros à esquerda removidos em números puros.

    O Excel transforma "000351156" em "351156"; sem isso, um CSV salvo pelo Excel
    escaparia do radar de duplicidade/fraude (16 mil títulos do estoque têm zeros à esquerda).
    """
    nu = str(nu_documento or "").strip().upper()
    return (nu.lstrip("0") or "0") if nu.isdigit() else nu


def normalizar_data_texto(data: str | date) -> str:
    if isinstance(data, date):
        return formatar_data_br(data)
    s = str(data).strip()
    if len(s) == 10 and s[2] == "/" and s[5] == "/":
        return s
    return formatar_data_br(parse_data_br(s))


def chave_canonica(doc_cedente: str, doc_sacado: str, nu_documento: str, valor_nominal: float, data_vencimento: str | date) -> str:
    try:
        vencimento = normalizar_data_texto(data_vencimento)
    except ValueError:
        vencimento = str(data_vencimento).strip()
    return (
        f"{normalizar_documento(doc_cedente)}|{normalizar_documento(doc_sacado)}|"
        f"{normalizar_nu_documento(nu_documento)}|{float(valor_nominal):.2f}|{vencimento}"
    )


def gerar_hash_titulo(doc_cedente: str, doc_sacado: str, nu_documento: str, valor_nominal: float, data_vencimento: str | date) -> str:
    chave = chave_canonica(doc_cedente, doc_sacado, nu_documento, valor_nominal, data_vencimento)
    return hashlib.sha256(chave.encode("utf-8")).hexdigest()


def decodificar_csv(conteudo: bytes) -> str:
    """UTF-8 (com ou sem BOM); se falhar, cp1252 (CSV salvo pelo Excel em português)."""
    try:
        return conteudo.decode("utf-8-sig")
    except UnicodeDecodeError:
        return conteudo.decode("cp1252", errors="replace")


def detectar_delimitador(linha_cabecalho: str) -> str:
    contagens = {d: linha_cabecalho.count(d) for d in (";", "\t", ",")}
    melhor = max(contagens, key=lambda d: contagens[d])
    return melhor if contagens[melhor] > 0 else ";"


def iterar_linhas_csv(texto: str, delimitador: str):
    """Sem aspas no arquivo, split puro é ~2,5x mais rápido que o módulo csv."""
    if '"' not in texto:
        return (linha.split(delimitador) for linha in texto.splitlines())
    return csv.reader(io.StringIO(texto, newline=""), delimiter=delimitador)


def _valor_rapido(texto: str) -> float:
    if "." not in texto and "R" not in texto:
        return float(texto.replace(",", "."))
    return parse_valor_br(texto)


def _max_data(datas: set[str]) -> date | None:
    validas = []
    for texto in datas:
        try:
            validas.append(parse_data_br(texto))
        except ValueError:
            continue
    return max(validas) if validas else None


@dataclass
class StockIndex:
    nome_fundo: str
    hashes_antecipe: dict[str, str] = field(default_factory=dict)  # hash -> data de aquisição
    hashes_outros_fundos: dict[str, str] = field(default_factory=dict)  # hash -> nome do fundo
    exposicao_sacado: dict[str, float] = field(default_factory=dict)
    exposicao_sacado_raiz: dict[str, float] = field(default_factory=dict)
    exposicao_cedente: dict[str, float] = field(default_factory=dict)
    exposicao_cedente_raiz: dict[str, float] = field(default_factory=dict)
    patrimonio_antecipe: float = 0.0
    total_linhas: int = 0
    linhas_antecipe: int = 0
    linhas_invalidas: int = 0
    fundos: set[str] = field(default_factory=set)
    data_aquisicao_max: date | None = None
    data_base_padrao: date = DATA_BASE_FALLBACK
    tempo_carga_ms: float = 0.0

    def mapa_exposicao(self, dimensao: str, agrupamento: str) -> dict[str, float]:
        if dimensao == "sacado":
            return self.exposicao_sacado_raiz if agrupamento == AGRUPAMENTO_RAIZ else self.exposicao_sacado
        return self.exposicao_cedente_raiz if agrupamento == AGRUPAMENTO_RAIZ else self.exposicao_cedente


def carregar_estoque(
    caminho: Path,
    nome_fundo: str,
    cnpj_fundo: str | None,
    data_base_override: date | None = None,
) -> StockIndex:
    """Lê o estoque uma única vez e monta os HashMaps/HashSets de consulta O(1)."""
    inicio = time.perf_counter()
    texto = decodificar_csv(Path(caminho).read_bytes())
    primeira_linha = texto.split("\n", 1)[0]
    leitor = iter(iterar_linhas_csv(texto, detectar_delimitador(primeira_linha)))

    cabecalho = [c.strip().upper() for c in next(leitor, [])]
    faltando = [c for c in COLUNAS_ESTOQUE if c not in cabecalho]
    if faltando:
        raise ValueError(f"estoque sem as colunas obrigatórias: {', '.join(faltando)}")
    pos = {nome: cabecalho.index(nome) for nome in COLUNAS_ESTOQUE}
    i_nome, i_doc_fundo = pos["NOME_FUNDO"], pos["DOC_FUNDO"]
    i_ced, i_sac, i_nu = pos["DOC_CEDENTE"], pos["DOC_SACADO"], pos["NU_DOCUMENTO"]
    i_valor, i_venc, i_aq = pos["VALOR_NOMINAL"], pos["DATA_VENCIMENTO_ORIGINAL"], pos["DATA_AQUISICAO"]
    largura = max(pos.values()) + 1

    alvo_cnpj = normalizar_documento(cnpj_fundo)
    alvo_nome = (nome_fundo or "").strip().upper()

    idx = StockIndex(nome_fundo=nome_fundo)
    hashes_antecipe, hashes_outros = idx.hashes_antecipe, idx.hashes_outros_fundos
    exp_sac, exp_sac_raiz = idx.exposicao_sacado, idx.exposicao_sacado_raiz
    exp_ced, exp_ced_raiz = idx.exposicao_cedente, idx.exposicao_cedente_raiz
    fundos = idx.fundos
    sha256 = hashlib.sha256
    patrimonio = 0.0
    total = antecipe = invalidas = 0
    datas_aquisicao: set[str] = set()
    docs: dict[str, str] = {}  # memo: poucos milhares de documentos distintos em 100k linhas
    eh_antecipe_por_fundo: dict[tuple[str, str], bool] = {}

    for linha in leitor:
        if len(linha) < largura:
            if any(campo.strip() for campo in linha):
                invalidas += 1
            continue
        try:
            valor = _valor_rapido(linha[i_valor].strip())
            venc = linha[i_venc].strip()
            # shortcut: dd/mm/aaaa só é conferido no formato (31/02 passa), porque o estoque vem do sistema do fundo
            # (0 datas ruins nas 100k linhas); validar o calendário aqui se o estoque passar a vir de terceiros
            if not (len(venc) == 10 and venc[2] == "/" and venc[5] == "/"):
                venc = normalizar_data_texto(venc)
        except ValueError:
            invalidas += 1
            continue
        total += 1

        bruto_ced, bruto_sac = linha[i_ced], linha[i_sac]
        ced = docs.get(bruto_ced)
        if ced is None:
            ced = docs[bruto_ced] = normalizar_documento(bruto_ced)
        sac = docs.get(bruto_sac)
        if sac is None:
            sac = docs[bruto_sac] = normalizar_documento(bruto_sac)
        chave = f"{ced}|{sac}|{normalizar_nu_documento(linha[i_nu])}|{valor:.2f}|{venc}"
        hash_titulo = sha256(chave.encode("utf-8")).hexdigest()

        aquisicao = linha[i_aq].strip()
        datas_aquisicao.add(aquisicao)

        nome = linha[i_nome]
        chave_fundo = (nome, linha[i_doc_fundo])
        eh_antecipe = eh_antecipe_por_fundo.get(chave_fundo)
        if eh_antecipe is None:
            nome_upper = nome.strip().upper()
            fundos.add(nome_upper)
            if alvo_cnpj or alvo_nome:
                doc_fundo = normalizar_documento(chave_fundo[1])
                eh_antecipe = bool((alvo_cnpj and doc_fundo == alvo_cnpj) or (alvo_nome and nome_upper == alvo_nome))
            else:
                eh_antecipe = "ANTECIPE" in nome_upper
            eh_antecipe_por_fundo[chave_fundo] = eh_antecipe

        if eh_antecipe:
            antecipe += 1
            hashes_antecipe[hash_titulo] = aquisicao
            patrimonio += valor
            exp_sac[sac] = exp_sac.get(sac, 0.0) + valor
            exp_ced[ced] = exp_ced.get(ced, 0.0) + valor
            raiz_sac = sac[:8] if len(sac) == 14 else sac
            raiz_ced = ced[:8] if len(ced) == 14 else ced
            exp_sac_raiz[raiz_sac] = exp_sac_raiz.get(raiz_sac, 0.0) + valor
            exp_ced_raiz[raiz_ced] = exp_ced_raiz.get(raiz_ced, 0.0) + valor
        else:
            hashes_outros.setdefault(hash_titulo, nome.strip())

    idx.patrimonio_antecipe = round(patrimonio, 2)
    idx.total_linhas = total
    idx.linhas_antecipe = antecipe
    idx.linhas_invalidas = invalidas
    idx.data_aquisicao_max = _max_data(datas_aquisicao)
    if data_base_override:
        idx.data_base_padrao = data_base_override
    elif idx.data_aquisicao_max:
        idx.data_base_padrao = proximo_dia_util(idx.data_aquisicao_max)
    idx.tempo_carga_ms = round((time.perf_counter() - inicio) * 1000, 1)
    return idx
