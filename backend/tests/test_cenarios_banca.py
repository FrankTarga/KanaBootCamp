"""Cinco cenários de negócio que a banca costuma conferir, um teste por cenário.

Rodar só estes:  cd backend && python -m pytest tests/test_cenarios_banca.py -v
Usam o mesmo estoque sintético do conftest.py: patrimônio do ANTECIPE = R$ 1.000.000,00,
maior aquisição na quarta 21/10/2026 e taxa de 2% a.m. do validadores_antecipe.json.
"""

from __future__ import annotations

import json
from datetime import date

import pytest

from app.br_utils import proximo_dia_util

from .conftest import (
    SACADO_CONCENTRADO,
    SACADO_LIVRE,
    SACADO_OTIMIZADOR,
    TITULO_OUTRO_FUNDO,
    config_com,
    linha_csv,
    montar_csv,
)


def test_calculo_desagio_data_base_quinta_feira(engine):
    """Data-base = D+1 útil da maior aquisição (quarta 21/10) = quinta 22/10/2026.
    Nota de R$ 10.000 vencendo em 21/11/2026: 30 dias x 2% a.m. / 30 = 2% de deságio."""
    assert engine.index.data_aquisicao_max == date(2026, 10, 21)
    assert engine.index.data_base_padrao == date(2026, 10, 22)
    assert engine.index.data_base_padrao.weekday() == 3  # quinta-feira
    assert proximo_dia_util(date(2026, 10, 23)) == date(2026, 10, 26)  # sexta pula o fim de semana

    r = engine.validar_lote(montar_csv(linha_csv(SACADO_LIVRE, "Q1", "10.000,00", "21/11/2026")))
    item = r.itens[0]
    assert r.meta.data_base_utilizada == "22/10/2026"
    assert item.prazo_dias == 30
    assert item.desagio_reais == pytest.approx(10_000 * 0.02 * 30 / 30)  # R$ 200,00
    assert item.valor_liquido == pytest.approx(9_800.00)


def test_concentracao_acumulativa_intra_lote(engine):
    """O teto de 10% vale para o estoque MAIS o que já foi aprovado no próprio lote (Shadow Ledger).
    O cliente já tem R$ 90.000 (9%): cabem ~R$ 11.111; duas notas de R$ 5.000 passam, a terceira estoura."""
    lote = montar_csv(*(linha_csv(SACADO_CONCENTRADO, f"C{i}", "5000,00", "21/11/2026") for i in range(3)))
    r = engine.validar_lote(lote, otimizar_lote=False)

    assert [i.status for i in r.itens] == ["APROVADA", "APROVADA", "RECUSADA"]
    assert r.itens[2].erros[0].codigo == "CONCENTRACAO_MAXIMA_SACADO"
    # cada nota sozinha caberia: quem recusa é a soma dentro do lote
    sozinha = engine.validar_lote(montar_csv(linha_csv(SACADO_CONCENTRADO, "C9", "5000,00", "21/11/2026")))
    assert sozinha.itens[0].status == "APROVADA"
    # o lote não altera o estoque em memória: rodar de novo dá o mesmo resultado
    assert [i.status for i in engine.validar_lote(lote, otimizar_lote=False).itens] == ["APROVADA", "APROVADA", "RECUSADA"]
    assert engine.index.exposicao_sacado_raiz[SACADO_CONCENTRADO[:8]] == 90_000.0


def test_radar_antifraude_outro_fundo(engine):
    """Título idêntico a um que já está na carteira de OUTRO fundo = dupla cessão (fraude),
    mesmo com o valor escrito de outro jeito."""
    sacado, nu, _valor, venc = TITULO_OUTRO_FUNDO
    lote = montar_csv(
        linha_csv(sacado, nu, "2.500,00", venc),  # mesmo título, valor com separador de milhar
        linha_csv(SACADO_LIVRE, "LIMPA-1", "2500,00", venc),  # nota limpa no mesmo lote
    )
    r = engine.validar_lote(lote)
    fraude, limpa = r.itens

    assert fraude.status == "RECUSADA" and fraude.severidade == "FRAUDE"
    assert "FRAUDE_OUTRO_FUNDO" in [e.codigo for e in fraude.erros]
    assert limpa.status == "APROVADA"
    # a nota fraudada não entra no dinheiro do lote: só a limpa é paga
    assert r.resumo.valor_liquido_receber == pytest.approx(limpa.valor_liquido)
    assert r.resumo.qtd_alertas_fraude == 1


def test_otimizador_lote_aumenta_valor_liquido(engine):
    """Limite de R$ 6.000 no cliente. Na ordem do arquivo, a nota longa de R$ 5.000 ocupa o limite;
    o otimizador aprova as duas curtas de R$ 3.000 e o líquido do lote sobe."""
    cfg = config_com(engine, "CONCENTRACAO_MAXIMA_SACADO", percentual_maximo=None, valor_maximo=6000.0)
    lote = montar_csv(
        linha_csv(SACADO_OTIMIZADOR, "O1", "5000,00", "21/12/2026"),  # 60 dias
        linha_csv(SACADO_OTIMIZADOR, "O2", "3000,00", "01/11/2026"),  # 10 dias
        linha_csv(SACADO_OTIMIZADOR, "O3", "3000,00", "03/11/2026"),  # 12 dias
    )
    sem = engine.validar_lote(lote, config=cfg, otimizar_lote=False)
    com = engine.validar_lote(lote, config=cfg, otimizar_lote=True)

    assert sem.resumo.qtd_aprovadas == 1 and com.resumo.qtd_aprovadas == 2
    assert com.resumo.valor_liquido_receber > sem.resumo.valor_liquido_receber
    assert com.meta.ganho_otimizador_reais == pytest.approx(com.resumo.valor_liquido_receber - sem.resumo.valor_liquido_receber)
    assert com.meta.qtd_notas_salvas_otimizador == 2
    assert [i.linha_csv for i in com.itens] == [2, 3, 4]  # a resposta continua na ordem do CSV


def test_hot_reload_validadores_sem_deploy(engine, pasta_dados):
    """O gestor troca uma regra com o sistema no ar: o mesmo motor, sem reiniciar,
    passa a usar a regra nova na validação seguinte, e o JSON em disco é atualizado."""
    lote = montar_csv(linha_csv(SACADO_LIVRE, "M1", "50,00", "21/11/2026"))  # abaixo do mínimo de R$ 100
    antes = engine.validar_lote(lote)
    assert antes.itens[0].status == "RECUSADA"
    assert antes.itens[0].erros[0].codigo == "VALOR_MINIMO"
    versao = engine.versao_config

    engine.atualizar_config(config_com(engine, "VALOR_MINIMO", ativo=False))

    depois = engine.validar_lote(lote)
    assert depois.itens[0].status == "APROVADA"
    assert engine.versao_config == versao + 1
    no_disco = json.loads((pasta_dados / "validadores_antecipe.json").read_text(encoding="utf-8"))
    assert next(v for v in no_disco["validadores"] if v["codigo"] == "VALOR_MINIMO")["ativo"] is False
