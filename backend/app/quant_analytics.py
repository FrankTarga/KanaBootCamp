"""Módulo quantitativo do ANTECIPE PRO: precificação e Smart Batch Optimizer.

Interface estável consumida pelo back-end (o Estatístico pode trocar a implementação
mantendo estas assinaturas):

- precificar(valor_nominal, prazo_dias, taxa_mensal, metodo, base_dias) -> ResultadoPrecificacao
- gerar_ordens_candidatas(itens, restricoes) -> list[list[int]]
- ordenar_lote_otimizado(itens, restricoes) -> list[int]

Parse/formatação BR ficam em app/br_utils.py (infra do back-end).
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field

METODOS_PRECIFICACAO = ("DESCONTO_SIMPLES", "DESCONTO_COMPOSTO")


# ---------------------------------------------------------------------------
# Precificação
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ResultadoPrecificacao:
    desagio_reais: float
    valor_liquido: float


def precificar(
    valor_nominal: float,
    prazo_dias: int,
    taxa_mensal: float,
    metodo: str = "DESCONTO_SIMPLES",
    base_dias: int = 30,
) -> ResultadoPrecificacao:
    """Preço de compra do título: valor nominal menos o deságio.

    DESCONTO_SIMPLES (comercial): deságio = VN * i * n / base_dias
    DESCONTO_COMPOSTO:            líquido = VN / (1 + i) ** (n / base_dias)
    """
    if valor_nominal <= 0:
        return ResultadoPrecificacao(0.0, round(valor_nominal, 2))
    n = max(prazo_dias, 0)
    if metodo == "DESCONTO_SIMPLES":
        desagio = valor_nominal * taxa_mensal * n / base_dias
    elif metodo == "DESCONTO_COMPOSTO":
        desagio = valor_nominal - valor_nominal / (1 + taxa_mensal) ** (n / base_dias)
    else:
        raise ValueError(f"método de precificação não suportado: {metodo}")
    desagio = round(min(max(desagio, 0.0), valor_nominal), 2)
    return ResultadoPrecificacao(desagio, round(valor_nominal - desagio, 2))


# ---------------------------------------------------------------------------
# Smart Batch Optimizer
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ItemOtimizacao:
    idx: int  # posição da nota no lote (ordem do CSV, base 0)
    valor_nominal: float
    prazo_dias: int
    valor_liquido: float
    grupo_sacado: str
    grupo_cedente: str
    elegivel: bool  # passou em todas as regras que não dependem da ordem


@dataclass(frozen=True)
class RestricaoConcentracao:
    dimensao: str  # "sacado" | "cedente"
    percentual_maximo: float | None  # em % (10.0 = 10%)
    valor_maximo: float | None
    patrimonio_inicial: float
    exposicao_inicial: dict[str, float] = field(default_factory=dict)

    def grupo(self, item: ItemOtimizacao) -> str:
        return item.grupo_sacado if self.dimensao == "sacado" else item.grupo_cedente

    def folga(self, grupo: str, patrimonio: float) -> float:
        """Quanto ainda cabe no grupo, dado o patrimônio do fundo SEM as notas do próprio grupo.

        Para o teto percentual p: (E + S) / (P + S) <= p  =>  S <= (p * P - E) / (1 - p)
        """
        exposicao = self.exposicao_inicial.get(grupo, 0.0)
        folgas = []
        if self.percentual_maximo is not None:
            p = self.percentual_maximo / 100.0
            folgas.append(math.inf if p >= 1 else (p * patrimonio - exposicao) / (1 - p))
        if self.valor_maximo is not None:
            folgas.append(self.valor_maximo - exposicao)
        return max(0.0, min(folgas)) if folgas else math.inf


def _mochila(itens: list[ItemOtimizacao], capacidade: float) -> set[int]:
    """Mochila 0/1 (maximiza Σ valor líquido com Σ valor nominal <= capacidade).

    Pesos discretizados para cima, então a seleção sempre cabe na capacidade real.
    """
    if capacidade <= 0 or not itens:
        return set()
    if sum(it.valor_nominal for it in itens) <= capacidade:
        return {it.idx for it in itens}
    resolucao = max(200, min(2000, 200_000 // len(itens)))
    escala = capacidade / resolucao
    pesos = [math.ceil(it.valor_nominal / escala - 1e-9) for it in itens]
    melhor = [0.0] * (resolucao + 1)
    escolhas = [bytearray(resolucao + 1) for _ in itens]
    for i, item in enumerate(itens):
        peso = pesos[i]
        if peso > resolucao:
            continue
        linha = escolhas[i]
        valor = item.valor_liquido
        for c in range(resolucao, peso - 1, -1):
            candidato = melhor[c - peso] + valor
            if candidato > melhor[c] + 1e-9:
                melhor[c] = candidato
                linha[c] = 1
    selecionados: set[int] = set()
    c = resolucao
    for i in range(len(itens) - 1, -1, -1):
        if escolhas[i][c]:
            selecionados.add(itens[i].idx)
            c -= pesos[i]
    return selecionados


def ordenar_lote_otimizado(
    itens: list[ItemOtimizacao], restricoes: list[RestricaoConcentracao]
) -> list[int]:
    """Ordem "quant" de avaliação do lote.

    1. Notas de grupos sem pressão de concentração primeiro, por menor prazo: entram todas
       e aumentam o patrimônio do fundo, abrindo espaço para os grupos pressionados.
    2. Em cada grupo pressionado, mochila 0/1 sobre a folga projetada escolhe o subconjunto
       que maximiza o valor líquido; escolhidas entram antes, por menor prazo.
    3. Sobras por menor valor (podem caber no resto da folga). Inelegíveis por último.
    """
    elegiveis = [it for it in itens if it.elegivel]
    inelegiveis = [it for it in itens if not it.elegivel]

    pressionados: dict[str, set[str]] = defaultdict(set)
    for restricao in restricoes:
        demanda: dict[str, float] = defaultdict(float)
        for item in elegiveis:
            demanda[restricao.grupo(item)] += item.valor_nominal
        for grupo, total in demanda.items():
            if total > restricao.folga(grupo, restricao.patrimonio_inicial) + 1e-6:
                pressionados[restricao.dimensao].add(grupo)

    def pressionado(item: ItemOtimizacao) -> bool:
        return any(r.grupo(item) in pressionados[r.dimensao] for r in restricoes)

    por_prazo = lambda it: (it.prazo_dias, -it.valor_nominal)  # noqa: E731
    livres = sorted((it for it in elegiveis if not pressionado(it)), key=por_prazo)
    disputados = [it for it in elegiveis if pressionado(it)]

    escolhidos = {it.idx for it in disputados}
    if restricoes:
        patrimonio_estimado = restricoes[0].patrimonio_inicial + sum(it.valor_nominal for it in livres)
        for restricao in restricoes:
            grupos: dict[str, list[ItemOtimizacao]] = defaultdict(list)
            for item in disputados:
                if item.idx in escolhidos and restricao.grupo(item) in pressionados[restricao.dimensao]:
                    grupos[restricao.grupo(item)].append(item)
            for grupo, membros in grupos.items():
                selecao = _mochila(membros, restricao.folga(grupo, patrimonio_estimado))
                escolhidos -= {it.idx for it in membros if it.idx not in selecao}

    selecionados = sorted((it for it in disputados if it.idx in escolhidos), key=por_prazo)
    sobras = sorted((it for it in disputados if it.idx not in escolhidos), key=lambda it: it.valor_nominal)
    return [it.idx for it in livres + selecionados + sobras + inelegiveis]


def gerar_ordens_candidatas(
    itens: list[ItemOtimizacao], restricoes: list[RestricaoConcentracao]
) -> list[list[int]]:
    """Permutações candidatas; o motor simula todas e fica com a de maior Σ valor líquido.

    A primeira é sempre a ordem original do CSV, o que garante ganho >= 0.
    Os sorts são estáveis: notas idênticas mantêm a ordem do CSV entre si.
    """
    ordens = [
        [it.idx for it in itens],
        ordenar_lote_otimizado(itens, restricoes),
        [it.idx for it in sorted(itens, key=lambda it: (not it.elegivel, it.prazo_dias, -it.valor_nominal))],
        [it.idx for it in sorted(itens, key=lambda it: (not it.elegivel, -it.valor_nominal))],
        [it.idx for it in sorted(itens, key=lambda it: (not it.elegivel, it.valor_nominal))],
    ]
    unicas: list[list[int]] = []
    vistas: set[tuple[int, ...]] = set()
    for ordem in ordens:
        chave = tuple(ordem)
        if chave not in vistas:
            vistas.add(chave)
            unicas.append(ordem)
    return unicas
