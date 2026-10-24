"""Análise descritiva das notas recusadas de um lote (Estatístico).

Entrada: a lista `itens` da resposta de POST /batches/validate (dicts com status, valor_nominal,
valor_liquido e erros[{codigo, titulo_amigavel}]). Saída: uma linha por motivo de recusa.

Uma nota pode ter vários erros, então somar "notas por motivo" passa de 100% das recusadas.
Por isso cada motivo traz também quantas notas têm SÓ aquele erro e quanto dinheiro líquido
elas liberariam se ele fosse corrigido: corrigir um erro que sempre vem acompanhado de outro
não libera nada.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

# Fraude e duplicidade não se "corrigem": a nota não pode ser vendida de novo.
NAO_CORRIGIVEIS = frozenset({"DUPLICIDADE_LOTE", "DUPLICIDADE_FUNDO", "FRAUDE_OUTRO_FUNDO"})


def analisar_recusas(itens: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    recusadas = [i for i in itens if i["status"] == "RECUSADA"]
    motivos: dict[str, dict[str, Any]] = {}
    multiplos = 0

    for nota in recusadas:
        codigos = list(dict.fromkeys(e["codigo"] for e in nota["erros"]))  # sem repetir, na ordem
        multiplos += len(codigos) > 1
        for erro in nota["erros"]:
            motivos.setdefault(erro["codigo"], {
                "codigo": erro["codigo"],
                "titulo_amigavel": erro["titulo_amigavel"],
                "corrigivel": erro["codigo"] not in NAO_CORRIGIVEIS,
                "qtd_notas": 0,
                "valor_impactado": 0.0,
                "qtd_so_este_erro": 0,
                "liquido_liberado": 0.0,
            })
        for codigo in codigos:
            m = motivos[codigo]
            m["qtd_notas"] += 1
            m["valor_impactado"] += nota["valor_nominal"]
            if len(codigos) == 1:
                m["qtd_so_este_erro"] += 1
                if m["corrigivel"]:
                    m["liquido_liberado"] += nota["valor_liquido"]

    total = len(recusadas)
    for m in motivos.values():
        m["pct_das_recusadas"] = round(m["qtd_notas"] / total * 100, 1)
        m["valor_impactado"] = round(m["valor_impactado"], 2)
        m["liquido_liberado"] = round(m["liquido_liberado"], 2)

    return {
        "qtd_recusadas": total,
        "valor_recusado": round(sum(n["valor_nominal"] for n in recusadas), 2),
        "qtd_com_mais_de_um_erro": multiplos,
        "pct_com_mais_de_um_erro": round(multiplos / total * 100, 1) if total else 0.0,
        # o que mais destrava dinheiro primeiro; empate pelo valor impactado
        "motivos": sorted(motivos.values(), key=lambda m: (-m["liquido_liberado"], -m["valor_impactado"])),
    }
