"""Parse/formatação BR, precificação, mochila do otimizador e carga do estoque."""

from __future__ import annotations

from datetime import date

import pytest

from app.br_utils import formatar_brl, formatar_percentual, parse_data_br, parse_valor_br
from app.quant_analytics import ItemOtimizacao, _mochila, precificar
from app.stock_index import carregar_estoque, chave_canonica, normalizar_data_texto

from .conftest import CABECALHO, CEDENTE, OUTRO_FUNDO, SACADO_LIVRE, linha_csv


def test_parse_valor_aceita_numero_e_negativo():
    assert parse_valor_br(1500) == 1500.0
    assert parse_valor_br("-1.500,00") == -1500.0
    with pytest.raises(ValueError):
        parse_valor_br(float("inf"))


def test_parse_data_variacoes():
    assert parse_data_br(date(2026, 1, 2)) == date(2026, 1, 2)
    assert parse_data_br("22/10/26") == date(2026, 10, 22)
    assert parse_data_br("22/10/2026 00:00:00") == date(2026, 10, 22)
    for invalida in ("", "22/10", "abc"):
        with pytest.raises(ValueError):
            parse_data_br(invalida)


def test_formatacao_br():
    assert formatar_brl(-1234.5) == "-R$ 1.234,50"
    assert formatar_percentual(10.416) == "10,42%"


def test_precificacao_bordas():
    assert precificar(0.0, 30, 0.02).valor_liquido == 0.0
    assert precificar(100.0, 10_000, 0.02).valor_liquido == 0.0  # deságio nunca passa do valor da nota
    with pytest.raises(ValueError):
        precificar(100.0, 30, 0.02, "PRICE")


def _item(idx, valor, liquido):
    return ItemOtimizacao(idx, valor, 10, liquido, "S", "C", True)


def test_mochila_escolhe_o_subconjunto_de_maior_liquido():
    itens = [_item(0, 5000, 4800), _item(1, 3000, 2980), _item(2, 3000, 2976)]
    assert _mochila(itens, 6000) == {1, 2}
    assert _mochila(itens, 20000) == {0, 1, 2}  # tudo cabe
    assert _mochila(itens, 0) == set()


def test_datas_e_chave_canonica_toleram_formatos():
    assert normalizar_data_texto("1/2/2026") == "01/02/2026"
    assert chave_canonica("1", "2", "007", 10, "31/02/2026").endswith("|7|10.00|31/02/2026")


def _estoque(tmp_path, *linhas, cabecalho=CABECALHO):
    caminho = tmp_path / "estoque.csv"
    caminho.write_text("\n".join((cabecalho, *linhas)) + "\n", encoding="utf-8")
    return caminho


def test_estoque_com_aspas_milhar_e_linhas_ruins(tmp_path):
    caminho = _estoque(
        tmp_path,
        linha_csv(SACADO_LIVRE, "1", '"1.500,00"', "10/11/2026", aquisicao="20/10/2026"),
        linha_csv(SACADO_LIVRE, "2", "100,00", "31/02/2026"),  # aceito: só o formato é conferido (shortcut documentado)
        linha_csv(SACADO_LIVRE, "5", "100,00", "2026-13-01"),  # fora do formato e inválido: descartado
        linha_csv(SACADO_LIVRE, "3", "abc", "10/11/2026"),  # valor impossível
        "ANTECIPE FIDC;só três campos;x",  # linha curta
        linha_csv(SACADO_LIVRE, "4", "200,00", "10/11/2026", fundo=OUTRO_FUNDO),
    )
    idx = carregar_estoque(caminho, "ANTECIPE FIDC", "92.234.400/0001-80", data_base_override=date(2026, 10, 23))
    assert (idx.total_linhas, idx.linhas_antecipe, idx.linhas_invalidas) == (3, 2, 3)
    assert idx.patrimonio_antecipe == 1600.0
    assert idx.data_base_padrao == date(2026, 10, 23)
    assert idx.mapa_exposicao("cedente", "RAIZ_CNPJ") == {CEDENTE[:8]: 1600.0}


def test_estoque_sem_fundo_configurado_usa_o_nome_antecipe(tmp_path):
    caminho = _estoque(tmp_path, linha_csv(SACADO_LIVRE, "1", "100,00", "10/11/2026"))
    assert carregar_estoque(caminho, "", None).linhas_antecipe == 1  # fundo da linha: "ANTECIPE FIDC"


def test_estoque_sem_colunas_obrigatorias(tmp_path):
    with pytest.raises(ValueError, match="DATA_AQUISICAO"):
        carregar_estoque(_estoque(tmp_path, "x;y", cabecalho="NOME_FUNDO;DOC_FUNDO"), "ANTECIPE FIDC", None)
