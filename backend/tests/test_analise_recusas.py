from app.analise_recusas import analisar_recusas


def nota(status, valor, liquido, *codigos):
    return {
        "status": status,
        "valor_nominal": valor,
        "valor_liquido": liquido,
        "erros": [{"codigo": c, "titulo_amigavel": c.lower()} for c in codigos],
    }


def test_multiplos_erros_e_dinheiro_liberado():
    itens = [
        nota("APROVADA", 999.0, 990.0),
        nota("RECUSADA", 100.0, 98.0, "TIPO_RECEBIVEL"),
        nota("RECUSADA", 200.0, 196.0, "TIPO_RECEBIVEL", "PRAZO_MAXIMO"),
        nota("RECUSADA", 300.0, 294.0, "TIPO_RECEBIVEL", "PRAZO_MAXIMO"),
        nota("RECUSADA", 400.0, 392.0, "FRAUDE_OUTRO_FUNDO"),
    ]
    r = analisar_recusas(itens)
    assert (r["qtd_recusadas"], r["valor_recusado"]) == (4, 1000.0)
    assert (r["qtd_com_mais_de_um_erro"], r["pct_com_mais_de_um_erro"]) == (2, 50.0)

    m = {x["codigo"]: x for x in r["motivos"]}
    assert m["TIPO_RECEBIVEL"] == {
        "codigo": "TIPO_RECEBIVEL", "titulo_amigavel": "tipo_recebivel", "corrigivel": True,
        "qtd_notas": 3, "valor_impactado": 600.0, "pct_das_recusadas": 75.0,
        "qtd_so_este_erro": 1, "liquido_liberado": 98.0,
    }
    # prazo nunca aparece sozinho: impacta R$ 500, mas corrigir só ele não libera nada
    assert (m["PRAZO_MAXIMO"]["valor_impactado"], m["PRAZO_MAXIMO"]["liquido_liberado"]) == (500.0, 0.0)
    # fraude aparece sozinha, mas não é corrigível
    assert (m["FRAUDE_OUTRO_FUNDO"]["qtd_so_este_erro"], m["FRAUDE_OUTRO_FUNDO"]["liquido_liberado"]) == (1, 0.0)
    assert r["motivos"][0]["codigo"] == "TIPO_RECEBIVEL"  # o que mais libera vem primeiro


def test_erro_repetido_na_mesma_nota_conta_uma_vez():
    r = analisar_recusas([nota("RECUSADA", 50.0, 49.0, "VALOR_MINIMO", "VALOR_MINIMO")])
    m = r["motivos"][0]
    assert (m["qtd_notas"], m["qtd_so_este_erro"], m["liquido_liberado"]) == (1, 1, 49.0)


def test_lote_sem_recusas():
    r = analisar_recusas([nota("APROVADA", 10.0, 9.9)])
    assert r == {"qtd_recusadas": 0, "valor_recusado": 0.0, "qtd_com_mais_de_um_erro": 0,
                 "pct_com_mais_de_um_erro": 0.0, "motivos": []}
