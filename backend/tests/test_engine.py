from __future__ import annotations

import random
from datetime import date

import pytest

from app.api_schemas import ValidadoresConfig
from app.quant_analytics import parse_data_br, parse_valor_br, precificar, proximo_dia_util
from app.rule_engine import ErroArquivoLote, cnpj_valido, cpf_valido, validar_config
from app.stock_index import gerar_hash_titulo

from .conftest import (
    CABECALHO,
    SACADO_BAIXADO,
    SACADO_CONCENTRADO,
    SACADO_LIVRE,
    SACADO_MESMA_RAIZ,
    SACADO_OTIMIZADOR,
    TITULO_ANTECIPE,
    TITULO_OUTRO_FUNDO,
    config_com,
    linha_csv,
    montar_csv,
)


def codigos(item) -> list[str]:
    return [e.codigo for e in item.erros]


# ---------------------------------------------------------------------------
# Parse, documentos e precificação
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("1500,50", 1500.50),
        ("1.500,50", 1500.50),
        ("R$ 1.500,50", 1500.50),
        ("1500.50", 1500.50),
        ("1,500.50", 1500.50),
        ("1.500", 1500.0),
        ("2278,08", 2278.08),
        ("319,3", 319.3),
        ("1.234.567,89", 1234567.89),
    ],
)
def test_parse_valor_br(texto, esperado):
    assert parse_valor_br(texto) == pytest.approx(esperado)


@pytest.mark.parametrize("texto", ["", "abc", "R$", "--"])
def test_parse_valor_br_invalido(texto):
    with pytest.raises(ValueError):
        parse_valor_br(texto)


def test_parse_data_br():
    assert parse_data_br("22/10/2026") == date(2026, 10, 22)
    assert parse_data_br("2/1/2026") == date(2026, 1, 2)
    assert parse_data_br("2026-10-22") == date(2026, 10, 22)
    with pytest.raises(ValueError):
        parse_data_br("31/02/2026")


def test_documentos():
    assert cnpj_valido("92234400000180")
    assert not cnpj_valido("12345678000100")
    assert not cnpj_valido("11111111111111")
    assert cnpj_valido("12ABC34501DE35")  # CNPJ alfanumérico (exemplo oficial da Receita)
    assert cpf_valido("52998224725")
    assert not cpf_valido("52998224724")


def test_precificacao_desconto_simples():
    preco = precificar(10000.0, 30, 0.025)
    assert (preco.desagio_reais, preco.valor_liquido) == (250.0, 9750.0)
    assert precificar(10000.0, -5, 0.025).desagio_reais == 0.0
    composto = precificar(10000.0, 60, 0.02, "DESCONTO_COMPOSTO")
    assert composto.valor_liquido == pytest.approx(10000 / 1.02**2, abs=0.01)


def test_data_base_d_mais_1_util():
    assert proximo_dia_util(date(2026, 10, 21)) == date(2026, 10, 22)  # quarta -> quinta
    assert proximo_dia_util(date(2026, 10, 23)) == date(2026, 10, 26)  # sexta -> segunda


def test_hash_ignora_formatacao_e_zeros_do_excel():
    a = gerar_hash_titulo("10.062.050/0001-57", "22.144.961/0001-02", "000725714", 2278.08, "07/10/2026")
    b = gerar_hash_titulo("10062050000157", "22144961000102", " 725714 ", 2278.080, date(2026, 10, 7))
    assert a == b
    assert a != gerar_hash_titulo("10062050000157", "22144961000102", "725714", 2278.09, "07/10/2026")


# ---------------------------------------------------------------------------
# Índice do estoque
# ---------------------------------------------------------------------------

def test_estoque_indexado(engine):
    index = engine.index
    assert index.total_linhas == 4
    assert index.linhas_antecipe == 3
    assert index.patrimonio_antecipe == 1_000_000.0
    assert len(index.fundos) == 2
    assert index.data_aquisicao_max == date(2026, 10, 21)
    assert index.data_base_padrao == date(2026, 10, 22)
    assert index.exposicao_sacado_raiz[SACADO_CONCENTRADO[:8]] == 90_000.0


# ---------------------------------------------------------------------------
# Motor de regras
# ---------------------------------------------------------------------------

def test_lote_aprovado_precificado_pela_taxa_do_json(engine):
    r = engine.validar_lote(montar_csv(linha_csv(SACADO_LIVRE, "A1", "10.000,00", "21/11/2026")))
    item = r.itens[0]
    assert item.status == "APROVADA" and item.severidade == "OK"
    assert item.linha_csv == 2  # cabeçalho é a linha 1
    assert item.prazo_dias == 30
    assert r.meta.taxa_mensal_aplicada == 0.02  # 2,0% do validadores_antecipe.json
    assert (item.desagio_reais, item.valor_liquido) == (200.0, 9800.0)
    assert r.resumo.valor_liquido_receber == 9800.0


def test_taxa_da_requisicao_tem_prioridade(engine):
    r = engine.validar_lote(montar_csv(linha_csv(SACADO_LIVRE, "A1", "10000,00", "21/11/2026")), taxa_mensal=0.025)
    assert r.itens[0].desagio_reais == 250.0


def test_shadow_ledger_intra_lote(engine):
    """90k de exposição em 1M de carteira, teto 10%: cabem ~11,1k; a 3ª nota de 5k estoura."""
    lote = montar_csv(*(linha_csv(SACADO_CONCENTRADO, f"C{i}", "5000,00", "21/11/2026") for i in range(3)))
    r = engine.validar_lote(lote, otimizar_lote=False)
    assert [i.status for i in r.itens] == ["APROVADA", "APROVADA", "RECUSADA"]
    erro = r.itens[2].erros[0]
    assert erro.codigo == "CONCENTRACAO_MAXIMA_SACADO"
    assert "R$ 105.000,00" in erro.mensagem_empresa
    assert "Espaço ainda disponível: R$ 1.111,11" in erro.mensagem_empresa


def test_agrupamento_raiz_cnpj(engine):
    """Filial nova do mesmo grupo herda a exposição da raiz; com agrupamento CNPJ, não."""
    lote = montar_csv(linha_csv(SACADO_MESMA_RAIZ, "F1", "15000,00", "21/11/2026"))
    assert engine.validar_lote(lote).itens[0].status == "RECUSADA"
    cfg = config_com(engine, "CONCENTRACAO_MAXIMA_SACADO", agrupamento="CNPJ")
    assert engine.validar_lote(lote, config=cfg).itens[0].status == "APROVADA"


def test_concentracao_valor_absoluto(engine):
    cfg = config_com(engine, "CONCENTRACAO_MAXIMA_SACADO", percentual_maximo=None, valor_maximo=7000.0)
    lote = montar_csv(linha_csv(SACADO_LIVRE, "V1", "5000,00", "21/11/2026"), linha_csv(SACADO_LIVRE, "V2", "5000,00", "22/11/2026"))
    r = engine.validar_lote(lote, config=cfg, otimizar_lote=False)
    assert [i.status for i in r.itens] == ["APROVADA", "RECUSADA"]
    assert "acima do limite máximo de R$ 7.000,00" in r.itens[1].erros[0].mensagem_empresa


def test_triplo_radar_duplicidade(engine):
    sac_a, nu_a, valor_a, venc_a = TITULO_ANTECIPE
    sac_o, nu_o, valor_o, venc_o = TITULO_OUTRO_FUNDO
    lote = montar_csv(
        linha_csv(SACADO_LIVRE, "D1", "1000,00", "21/11/2026"),
        linha_csv(SACADO_LIVRE, "D1", "1.000,00", "21/11/2026"),  # mesma nota, outra formatação
        linha_csv(sac_a, nu_a.lstrip("0"), valor_a, venc_a),  # Excel cortou os zeros
        linha_csv(sac_o, nu_o, valor_o, venc_o),
    )
    r = engine.validar_lote(lote)
    dup_lote, dup_fundo, fraude = r.itens[1], r.itens[2], r.itens[3]
    assert r.itens[0].status == "APROVADA"
    assert codigos(dup_lote) == ["DUPLICIDADE_LOTE"] and dup_lote.severidade == "DUPLICIDADE"
    assert "linha 2" in dup_lote.erros[0].mensagem_empresa
    assert "DUPLICIDADE_FUNDO" in codigos(dup_fundo) and dup_fundo.severidade == "DUPLICIDADE"
    assert "15/09/2026" in dup_fundo.erros[0].mensagem_empresa
    assert codigos(fraude) == ["FRAUDE_OUTRO_FUNDO"] and fraude.severidade == "FRAUDE"
    assert "MARÉ ALTA DUPLICATAS FIDC" in fraude.erros[0].mensagem_empresa
    assert r.resumo.qtd_alertas_fraude == 1


def test_avaliacao_sem_short_circuit(engine):
    lote = montar_csv(linha_csv("12.345.678/0001-00", "X1", "45,00", "15/09/2027", tipo="Cheque"))
    item = engine.validar_lote(lote).itens[0]
    assert set(codigos(item)) == {"CNPJ_SACADO_VALIDO", "TIPO_RECEBIVEL", "VALOR_MINIMO", "PRAZO_MAXIMO"}
    assert all(e.mensagem_empresa and e.acao_recomendada and e.titulo_amigavel for e in item.erros)


def test_regras_de_prazo_e_situacao(engine):
    lote = montar_csv(
        linha_csv(SACADO_LIVRE, "P1", "1000,00", "15/10/2026"),
        linha_csv(SACADO_LIVRE, "P2", "1000,00", "30/06/2027"),
        linha_csv(SACADO_BAIXADO, "P3", "1000,00", "21/11/2026"),
    )
    vencida, longa, baixada = engine.validar_lote(lote).itens
    assert codigos(vencida) == ["NAO_VENCIDA"]
    assert codigos(longa) == ["PRAZO_MAXIMO"]
    assert "a partir de 01/01/2027" in longa.erros[0].acao_recomendada
    assert codigos(baixada) == ["SITUACAO_CADASTRAL_SACADO"]


def test_regra_desativada_e_ignorada(engine):
    lote = montar_csv(linha_csv(SACADO_LIVRE, "M1", "50,00", "21/11/2026"))
    assert engine.validar_lote(lote).itens[0].status == "RECUSADA"
    cfg = config_com(engine, "VALOR_MINIMO", ativo=False)
    assert engine.validar_lote(lote, config=cfg).itens[0].status == "APROVADA"


def test_regra_inativa_ativada_no_what_if(engine):
    lote = montar_csv(linha_csv(SACADO_LIVRE, "Q1", "1000,00", "01/11/2026"))
    assert engine.validar_lote(lote).itens[0].status == "APROVADA"
    cfg = config_com(engine, "PRAZO_MINIMO", ativo=True)
    item = engine.validar_lote(lote, config=cfg).itens[0]
    assert codigos(item) == ["PRAZO_MINIMO"]


def test_linha_mal_formatada_nao_derruba_lote(engine):
    lote = montar_csv(
        linha_csv(SACADO_LIVRE, "OK1", "1000,00", "21/11/2026"),
        linha_csv(SACADO_LIVRE, "BAD", "abc", "31/02/2026"),
    )
    ok, ruim = engine.validar_lote(lote).itens
    assert ok.status == "APROVADA"
    assert ruim.status == "RECUSADA" and codigos(ruim)[0] == "FORMATO_INVALIDO"
    assert "\"abc\"" in ruim.erros[0].mensagem_empresa and "31/02/2026" in ruim.erros[0].mensagem_empresa


def test_csv_excel_cp1252_tab_e_bom(engine):
    linha = linha_csv(SACADO_LIVRE, "E1", "1.000,00", "21/11/2026", nome_sacado="AÇÚCAR & CIA")
    tab = ("\n".join([CABECALHO, linha]).replace(";", "\t")).encode("cp1252")
    bom = "﻿".encode("utf-8") + montar_csv(linha)
    for conteudo in (tab, bom):
        item = engine.validar_lote(conteudo).itens[0]
        assert item.status == "APROVADA" and item.nome_sacado == "AÇÚCAR & CIA"


def test_csv_sem_colunas_obrigatorias(engine):
    with pytest.raises(ErroArquivoLote, match="VALOR_NOMINAL"):
        engine.validar_lote(b"NOME_FUNDO;DOC_SACADO\nX;Y\n")
    with pytest.raises(ErroArquivoLote):
        engine.validar_lote(b"   \n")


# ---------------------------------------------------------------------------
# Smart Batch Optimizer
# ---------------------------------------------------------------------------

def test_otimizador_salva_notas(engine):
    """Teto de R$ 6.000 no cliente: a ordem original gasta o limite com a nota de 5k (60 dias)."""
    cfg = config_com(engine, "CONCENTRACAO_MAXIMA_SACADO", percentual_maximo=None, valor_maximo=6000.0)
    lote = montar_csv(
        linha_csv(SACADO_OTIMIZADOR, "O1", "5000,00", "21/12/2026"),
        linha_csv(SACADO_OTIMIZADOR, "O2", "3000,00", "01/11/2026"),
        linha_csv(SACADO_OTIMIZADOR, "O3", "3000,00", "03/11/2026"),
    )
    sem = engine.validar_lote(lote, config=cfg, otimizar_lote=False)
    com = engine.validar_lote(lote, config=cfg, otimizar_lote=True)
    assert [i.status for i in sem.itens] == ["APROVADA", "RECUSADA", "RECUSADA"]
    assert [i.status for i in com.itens] == ["RECUSADA", "APROVADA", "APROVADA"]
    assert [i.salva_pelo_otimizador for i in com.itens] == [False, True, True]
    assert com.meta.valor_liquido_sem_otimizador == sem.resumo.valor_liquido_receber
    assert com.meta.ganho_otimizador_reais == pytest.approx(
        com.resumo.valor_liquido_receber - sem.resumo.valor_liquido_receber
    )
    assert com.meta.ganho_otimizador_reais > 0
    assert com.meta.qtd_notas_salvas_otimizador == 2
    assert [i.linha_csv for i in com.itens] == [2, 3, 4]  # resposta sempre na ordem do CSV
    assert sorted(i.ordem_avaliacao for i in com.itens) == [1, 2, 3]


@pytest.mark.parametrize("semente", range(5))
def test_otimizador_nunca_piora(engine, semente):
    rnd = random.Random(semente)
    cfg = config_com(engine, "CONCENTRACAO_MAXIMA_SACADO", percentual_maximo=None, valor_maximo=20000.0)
    sacados = [SACADO_LIVRE, SACADO_OTIMIZADOR, SACADO_CONCENTRADO]
    lote = montar_csv(*(
        linha_csv(rnd.choice(sacados), f"R{i}", f"{rnd.randint(500, 12000)},00", f"{rnd.randint(1, 28):02d}/{rnd.choice([11, 12])}/2026")
        for i in range(40)
    ))
    r = engine.validar_lote(lote, config=cfg)
    assert r.meta.ganho_otimizador_reais >= 0
    assert r.resumo.valor_liquido_receber == pytest.approx(r.meta.valor_liquido_sem_otimizador + r.meta.ganho_otimizador_reais)


def test_duplicata_no_lote_continua_na_primeira_linha_apos_otimizar(engine):
    lote = montar_csv(
        linha_csv(SACADO_LIVRE, "Z1", "9000,00", "21/12/2026"),
        linha_csv(SACADO_LIVRE, "Z2", "100,00", "01/11/2026"),
        linha_csv(SACADO_LIVRE, "Z1", "9000,00", "21/12/2026"),
    )
    r = engine.validar_lote(lote)
    assert r.itens[0].status == "APROVADA"
    assert codigos(r.itens[2]) == ["DUPLICIDADE_LOTE"]


# ---------------------------------------------------------------------------
# Validação de configuração (PUT /validators)
# ---------------------------------------------------------------------------

def test_validar_config_rejeita_erros(engine):
    dados = engine.config.para_json()
    dados["validadores"].append({"codigo": "REGRA_INVENTADA", "ativo": True, "parametros": {}})
    dados["validadores"].append({"codigo": "VALOR_MINIMO", "ativo": True, "parametros": {"valor_minimo": 1}})
    dados["validadores"][6]["parametros"]["percentual_maximo"] = 150
    dados["precificacao"]["metodo"] = "PRICE"
    erros = validar_config(ValidadoresConfig.model_validate(dados))
    texto = " | ".join(erros)
    assert "REGRA_INVENTADA" in texto
    assert "duplicado" in texto
    assert "percentual_maximo" in texto
    assert "PRICE" in texto


def test_validar_config_original_ok(engine):
    assert validar_config(engine.config) == []
    assert engine.regras_ativas_count() == 7
