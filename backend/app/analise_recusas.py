"""Análise descritiva das notas recusadas de um lote (Estatístico).

Entrada: a lista `itens` da resposta de POST /batches/validate (dicts com status, valor_nominal,
valor_liquido e erros[{codigo, titulo_amigavel}]).

Saídas:
- `grupos`: cada nota recusada entra em exatamente um grupo, então os percentuais somam 100%.
  Um grupo por problema para as notas com um único problema, e um grupo "mais de um problema"
  que se abre por quantidade de problemas (2, 3, ...) e por combinação.
- `motivos`: a visão por motivo, em que uma nota com vários erros conta em cada um (soma > 100%).
  Traz quanto dinheiro líquido corrigir só aquele erro libera: corrigir um erro que sempre vem
  acompanhado de outro não libera nada.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from typing import Any

# Fraude e duplicidade não se "corrigem": a nota não pode ser vendida de novo.
NAO_CORRIGIVEIS = frozenset({"DUPLICIDADE_LOTE", "DUPLICIDADE_FUNDO", "FRAUDE_OUTRO_FUNDO"})
# Corrigir uma nota vencida é emitir outra com novo vencimento: o preço dela não existe ainda,
# então "quanto libera" fica None (sem estimativa) em vez do valor cheio, que exageraria o ganho.
SEM_ESTIMATIVA = frozenset({"NAO_VENCIDA"})


def percentuais(qtds: list[int], total: int) -> list[float]:
    """Percentuais com 1 casa que somam exatamente 100,0 (maiores restos), para os cards fecharem."""
    if not total:
        return [0.0] * len(qtds)
    brutos = [q * 1000 / total for q in qtds]  # em décimos de ponto percentual
    inteiros = [int(b) for b in brutos]
    sobra = round(sum(brutos)) - sum(inteiros)
    for i in sorted(range(len(qtds)), key=lambda i: brutos[i] - inteiros[i], reverse=True)[:sobra]:
        inteiros[i] += 1
    return [i / 10 for i in inteiros]


def _bloco(notas: list[Mapping[str, Any]]) -> dict[str, Any]:
    return {"qtd": len(notas), "valor": round(sum(n["valor_nominal"] for n in notas), 2)}


def analisar_recusas(itens: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    itens = list(itens)
    recusadas = [i for i in itens if i["status"] == "RECUSADA"]
    titulos: dict[str, str] = {}
    motivos: dict[str, dict[str, Any]] = {}
    sozinho: dict[str, list] = defaultdict(list)          # código -> notas com só esse problema
    por_combinacao: dict[tuple[str, ...], list] = defaultdict(list)

    for nota in recusadas:
        codigos = list(dict.fromkeys(e["codigo"] for e in nota["erros"]))  # sem repetir, na ordem
        for erro in nota["erros"]:
            titulos.setdefault(erro["codigo"], erro["titulo_amigavel"])
        for codigo in codigos:
            m = motivos.setdefault(codigo, {
                "codigo": codigo,
                "titulo_amigavel": titulos[codigo],
                "corrigivel": codigo not in NAO_CORRIGIVEIS,
                "qtd_notas": 0,
                "valor_impactado": 0.0,
                "qtd_so_este_erro": 0,
                "liquido_liberado": None if codigo in SEM_ESTIMATIVA else 0.0,
            })
            m["qtd_notas"] += 1
            m["valor_impactado"] += nota["valor_nominal"]
        if len(codigos) == 1:
            m = motivos[codigos[0]]
            m["qtd_so_este_erro"] += 1
            if m["corrigivel"] and m["liquido_liberado"] is not None:
                m["liquido_liberado"] += nota["valor_liquido"]
            sozinho[codigos[0]].append(nota)
        else:
            por_combinacao[tuple(sorted(codigos))].append(nota)

    total = len(recusadas)
    for m in motivos.values():
        m["pct_das_recusadas"] = round(m["qtd_notas"] / total * 100, 1)
        m["valor_impactado"] = round(m["valor_impactado"], 2)
        if m["liquido_liberado"] is not None:
            m["liquido_liberado"] = round(m["liquido_liberado"], 2)

    # Partição: um grupo por problema único + o grupo "mais de um problema" (soma = 100%).
    um = sorted(sozinho.items(), key=lambda kv: -len(kv[1]))
    multiplas = [n for notas in por_combinacao.values() for n in notas]
    pct_topo = percentuais([len(n) for _, n in um] + [len(multiplas)], total)

    por_qtd: dict[int, list] = defaultdict(list)
    for combo, notas in por_combinacao.items():
        por_qtd[len(combo)].append((combo, notas))
    qtds = sorted(por_qtd)
    pct_qtd = percentuais([sum(len(n) for _, n in por_qtd[k]) for k in qtds], len(multiplas))
    subgrupos = []
    for k, pct in zip(qtds, pct_qtd):
        combos = sorted(por_qtd[k], key=lambda cn: -len(cn[1]))
        notas_k = [n for _, ns in combos for n in ns]
        pct_combo = percentuais([len(ns) for _, ns in combos], len(multiplas))
        subgrupos.append({
            "qtd_problemas": k,
            **_bloco(notas_k),
            "pct_do_grupo": pct,
            "combinacoes": [
                {"codigos": list(c), "titulos": [titulos[x] for x in c], **_bloco(ns), "pct_do_grupo": p}
                for (c, ns), p in zip(combos, pct_combo)
            ],
        })

    return {
        "qtd_notas": len(itens),
        "qtd_recusadas": total,
        "pct_recusadas": percentuais([total, len(itens) - total], len(itens))[0],
        "valor_recusado": round(sum(n["valor_nominal"] for n in recusadas), 2),
        "qtd_com_mais_de_um_erro": len(multiplas),
        "pct_com_mais_de_um_erro": pct_topo[-1],
        "grupos": {
            "um_problema": [
                {"codigo": c, "titulo_amigavel": titulos[c], "corrigivel": c not in NAO_CORRIGIVEIS,
                 **_bloco(ns), "pct_das_recusadas": p,
                 "liquido_liberado": motivos[c]["liquido_liberado"]}
                for (c, ns), p in zip(um, pct_topo)
            ],
            "mais_de_um_problema": {**_bloco(multiplas), "pct_das_recusadas": pct_topo[-1], "subgrupos": subgrupos},
        },
        # o que mais destrava dinheiro primeiro; empate pelo valor impactado
        "motivos": sorted(motivos.values(), key=lambda m: (-(m["liquido_liberado"] or 0), -m["valor_impactado"])),
    }
