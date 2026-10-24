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
    assert (r["qtd_notas"], r["qtd_recusadas"], r["pct_recusadas"], r["motivos"]) == (1, 0, 0.0, [])
    assert r["grupos"] == {"um_problema": [],
                           "mais_de_um_problema": {"qtd": 0, "valor": 0.0, "pct_das_recusadas": 0.0, "subgrupos": []}}


def test_grupos_somam_100_e_abrem_por_quantidade_e_combinacao():
    itens = [nota("APROVADA", 1.0, 1.0)] + [
        nota("RECUSADA", 10.0, 9.0, "TIPO_RECEBIVEL"),
        nota("RECUSADA", 10.0, 9.0, "TIPO_RECEBIVEL"),
        nota("RECUSADA", 10.0, 9.0, "FRAUDE_OUTRO_FUNDO"),
        nota("RECUSADA", 10.0, 9.0, "PRAZO_MAXIMO", "TIPO_RECEBIVEL"),
        nota("RECUSADA", 10.0, 9.0, "TIPO_RECEBIVEL", "PRAZO_MAXIMO"),  # mesma combinação, outra ordem
        nota("RECUSADA", 10.0, 9.0, "VALOR_MINIMO", "TIPO_RECEBIVEL"),
        nota("RECUSADA", 10.0, 9.0, "SITUACAO_CADASTRAL_SACADO", "TIPO_RECEBIVEL", "PRAZO_MAXIMO"),
    ]
    r = analisar_recusas(itens)
    g = r["grupos"]
    assert r["pct_recusadas"] == 87.5
    assert [(c["codigo"], c["qtd"], c["pct_das_recusadas"]) for c in g["um_problema"]] == [
        ("TIPO_RECEBIVEL", 2, 28.6), ("FRAUDE_OUTRO_FUNDO", 1, 14.3)]
    multi = g["mais_de_um_problema"]
    assert (multi["qtd"], multi["pct_das_recusadas"]) == (4, 57.1)
    assert round(sum(c["pct_das_recusadas"] for c in g["um_problema"]) + multi["pct_das_recusadas"], 1) == 100.0

    dois, tres = multi["subgrupos"]
    assert (dois["qtd_problemas"], dois["qtd"], dois["pct_do_grupo"]) == (2, 3, 75.0)
    assert (tres["qtd_problemas"], tres["qtd"], tres["pct_do_grupo"]) == (3, 1, 25.0)
    assert [(c["codigos"], c["qtd"], c["pct_do_grupo"]) for c in dois["combinacoes"]] == [
        (["PRAZO_MAXIMO", "TIPO_RECEBIVEL"], 2, 50.0), (["TIPO_RECEBIVEL", "VALOR_MINIMO"], 1, 25.0)]
    todas = [c["pct_do_grupo"] for s in multi["subgrupos"] for c in s["combinacoes"]]
    assert round(sum(todas), 1) == 100.0  # combinações somam 100% dentro do grupo de múltiplos


def test_percentuais_fecham_em_100_com_arredondamento():
    from app.analise_recusas import percentuais
    assert percentuais([1, 1, 1], 3) == [33.4, 33.3, 33.3]
    assert round(sum(percentuais([7, 5, 3, 2, 1, 1, 1], 20)), 1) == 100.0


def test_nota_vencida_nao_tem_estimativa_de_quanto_libera():
    r = analisar_recusas([nota("RECUSADA", 3120.0, 3120.0, "NAO_VENCIDA"), nota("RECUSADA", 100.0, 98.0, "TIPO_RECEBIVEL")])
    vencida = next(m for m in r["motivos"] if m["codigo"] == "NAO_VENCIDA")
    assert (vencida["corrigivel"], vencida["liquido_liberado"]) == (True, None)
    assert next(g for g in r["grupos"]["um_problema"] if g["codigo"] == "NAO_VENCIDA")["liquido_liberado"] is None
    assert r["motivos"][0]["codigo"] == "TIPO_RECEBIVEL"
