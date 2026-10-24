"""Regras opcionais, validação semântica do JSON, persistência e leitura do CSV de upload."""

from __future__ import annotations

import pytest

from app import rule_engine
from app.api_schemas import ValidadoresConfig
from app.rule_engine import (
    CadastroSituacao,
    ErroArquivoLote,
    ErroConfiguracao,
    RuleEngine,
    diagnosticar_documento,
    formatar_documento,
    ler_lote_csv,
    salvar_config,
    validar_config,
)

from .conftest import (
    CABECALHO,
    SACADO_LIVRE,
    SACADO_OTIMIZADOR,
    config_com,
    gerar_cnpj,
    linha_csv,
    montar_csv,
)

OUTRO_CEDENTE = gerar_cnpj("551112220001")  # sem exposição no estoque


def codigos(item) -> list[str]:
    return [e.codigo for e in item.erros]


def config_mais(engine, *validadores: dict) -> ValidadoresConfig:
    dados = engine.config.para_json()
    dados["validadores"].extend(validadores)
    return ValidadoresConfig.model_validate(dados)


def validar(engine, *linhas, **kwargs):
    return engine.validar_lote(montar_csv(*linhas), **kwargs)


# ---------------------------------------------------------------------------
# Documentos
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("doc", "motivo"),
    [
        ("", "o campo está vazio"),
        ("11111111111111", "todos os dígitos são iguais"),
        ("11111111111", "todos os dígitos são iguais"),
        ("52998224724", "os dígitos verificadores do CPF não conferem"),
        ("123456", "ele tem 6 caracteres, mas um CNPJ tem 14 e um CPF tem 11"),
    ],
)
def test_diagnostico_de_documento_explica_o_motivo(doc, motivo):
    assert diagnosticar_documento(doc) == motivo


def test_cpf_valido_nao_tem_motivo():
    assert diagnosticar_documento("52998224725") is None


def test_formatacao_de_documentos():
    assert formatar_documento("52998224725") == "529.982.247-25"
    assert formatar_documento("11222333") == "11.222.333"
    assert formatar_documento("ABC") == "ABC"


# ---------------------------------------------------------------------------
# Regras opcionais (valem quando o gestor as coloca no JSON)
# ---------------------------------------------------------------------------

def test_cnpj_do_cedente_invalido(engine):
    cfg = config_mais(engine, {"codigo": "CNPJ_CEDENTE_VALIDO", "ativo": True, "parametros": {}})
    item = validar(engine, linha_csv(SACADO_LIVRE, "C1", "1000,00", "21/11/2026", cedente="12.345.678/0001-00"),
                   config=cfg).itens[0]
    assert codigos(item) == ["CNPJ_CEDENTE_VALIDO"]
    assert "DOC_CEDENTE" in item.erros[0].acao_recomendada


def test_valor_maximo_por_titulo(engine):
    cfg = config_mais(engine, {"codigo": "VALOR_MAXIMO", "ativo": True, "parametros": {"valor_maximo": 5000}})
    acima, no_limite = validar(
        engine,
        linha_csv(SACADO_LIVRE, "M1", "5000,01", "21/11/2026"),
        linha_csv(SACADO_LIVRE, "M2", "5000,00", "21/11/2026"),
        config=cfg,
    ).itens
    assert codigos(acima) == ["VALOR_MAXIMO"] and "R$ 5.000,00" in acima.erros[0].mensagem_empresa
    assert no_limite.status == "APROVADA"


def test_documento_bloqueado_pela_raiz_do_cnpj(engine):
    cfg = config_mais(engine, {"codigo": "DOCUMENTO_BLOQUEADO", "ativo": True,
                               "parametros": {"documentos_bloqueados": [SACADO_LIVRE[:8]]}})
    bloqueada, livre = validar(
        engine,
        linha_csv(SACADO_LIVRE, "B1", "1000,00", "21/11/2026"),
        linha_csv(SACADO_OTIMIZADOR, "B2", "1000,00", "21/11/2026"),
        config=cfg,
    ).itens
    assert codigos(bloqueada) == ["DOCUMENTO_BLOQUEADO"]
    assert "do cliente" in bloqueada.erros[0].mensagem_empresa
    assert livre.status == "APROVADA"


def test_tipo_bloqueado_ignora_acento_e_maiuscula(engine):
    cfg = config_com(engine, "TIPO_RECEBIVEL", tipos_bloqueados=["Duplicata de Serviço"])
    item = validar(engine, linha_csv(SACADO_LIVRE, "T1", "1000,00", "21/11/2026", tipo="DUPLICATA DE SERVICO"),
                   config=cfg).itens[0]
    assert codigos(item) == ["TIPO_RECEBIVEL"]
    assert "não compra títulos do tipo" in item.erros[0].mensagem_empresa


def test_concentracao_de_cedente_e_explicacao_da_nota_preterida(engine):
    """Teto de R$ 6.000 por empresa: o otimizador troca a nota de 5k (60 dias) pelas duas de 3k."""
    cfg = config_com(engine, "CONCENTRACAO_MAXIMA_CEDENTE", ativo=True, percentual_maximo=None, valor_maximo=6000.0)
    r = validar(
        engine,
        linha_csv(SACADO_LIVRE, "E1", "5000,00", "21/12/2026", cedente=OUTRO_CEDENTE),
        linha_csv(SACADO_OTIMIZADOR, "E2", "3000,00", "01/11/2026", cedente=OUTRO_CEDENTE),
        linha_csv(SACADO_LIVRE, "E3", "3000,00", "03/11/2026", cedente=OUTRO_CEDENTE),
        config=cfg,
    )
    preterida = r.itens[0]
    msg = preterida.erros[0].mensagem_empresa
    assert codigos(preterida) == ["CONCENTRACAO_MAXIMA_CEDENTE"]
    assert "a sua empresa, EMPRESA TESTE LTDA (55.111.222/0001-" in msg
    assert "não cabem todas as notas da sua empresa" in msg
    assert "nº E2 (linha 3) e nº E3 (linha 4)" in msg
    assert [i.salva_pelo_otimizador for i in r.itens] == [False, True, True]


def test_explicacao_resume_quando_muitas_notas_entram_no_lugar(engine):
    cfg = config_com(engine, "CONCENTRACAO_MAXIMA_SACADO", percentual_maximo=None, valor_maximo=10000.0)
    r = validar(
        engine,
        linha_csv(SACADO_LIVRE, "G0", "9500,00", "20/01/2027"),
        *(linha_csv(SACADO_LIVRE, f"G{i}", "1600,00", f"0{i}/11/2026") for i in range(1, 7)),
        config=cfg,
    )
    assert r.itens[0].status == "RECUSADA"
    assert all(i.salva_pelo_otimizador for i in r.itens[1:])
    assert "e mais 1, que somam R$ 9.600,00" in r.itens[0].erros[0].mensagem_empresa


def test_desconto_composto(engine):
    dados = engine.config.para_json()
    dados["precificacao"]["metodo"] = "DESCONTO_COMPOSTO"
    item = validar(engine, linha_csv(SACADO_LIVRE, "DC", "10000,00", "21/12/2026"),
                   config=ValidadoresConfig.model_validate(dados)).itens[0]
    assert item.valor_liquido == round(10000 / 1.02 ** 2, 2)  # 60 dias a 2% a.m.


def test_taxa_padrao_quando_json_nao_tem_precificacao(engine):
    dados = engine.config.para_json()
    del dados["precificacao"]
    r = validar(engine, linha_csv(SACADO_LIVRE, "TP", "10000,00", "21/11/2026"), config=ValidadoresConfig.model_validate(dados))
    assert r.meta.taxa_mensal_aplicada == 0.025
    assert r.itens[0].desagio_reais == 250.0


# ---------------------------------------------------------------------------
# Validação semântica do JSON (PUT /validators)
# ---------------------------------------------------------------------------

def _erros_com(engine, codigo=None, parametros=None, precificacao=None, ativo=None) -> str:
    dados = engine.config.para_json()
    for v in dados["validadores"]:
        if v["codigo"] == codigo:
            v["parametros"] = parametros
            if ativo is not None:
                v["ativo"] = ativo
    if precificacao:
        dados["precificacao"].update(precificacao)
    return " | ".join(validar_config(ValidadoresConfig.model_validate(dados)))


@pytest.mark.parametrize(
    ("codigo", "parametros", "trecho"),
    [
        ("VALOR_MINIMO", {"valor_minimo": True}, "deve ser numérico"),
        ("VALOR_MINIMO", {"valor_minimo": "100"}, "deve ser numérico"),
        ("VALOR_MINIMO", {"valor_minimo": -1}, "no mínimo 0"),
        ("VALOR_MINIMO", {}, "é obrigatório"),
        ("PRAZO_MAXIMO", {"prazo_maximo_dias": 10.5}, "número inteiro"),
        ("SITUACAO_CADASTRAL_SACADO", {"situacoes_aceitas": []}, "lista não vazia"),
        ("TIPO_RECEBIVEL", {}, "informe 'tipos_aceitos'"),
        ("CONCENTRACAO_MAXIMA_SACADO", {"agrupamento": "RAIZ_CNPJ"}, "informe 'percentual_maximo'"),
        ("CONCENTRACAO_MAXIMA_SACADO", {"percentual_maximo": 0}, "maior que 0"),
        ("CONCENTRACAO_MAXIMA_SACADO", {"percentual_maximo": 10, "agrupamento": "GRUPO"}, "agrupamento 'GRUPO' inválido"),
    ],
)
def test_parametros_invalidos_sao_recusados(engine, codigo, parametros, trecho):
    assert trecho in _erros_com(engine, codigo, parametros)


def test_prazo_minimo_maior_que_maximo_e_recusado(engine):
    assert "recusaria todas as notas" in _erros_com(engine, "PRAZO_MINIMO", {"prazo_minimo_dias": 200}, ativo=True)


@pytest.mark.parametrize(
    ("precificacao", "trecho"),
    [
        ({"taxa_mensal_percentual": 150}, "entre 0 e 100"),
        ({"prazo_minimo_cobranca_dias": -1}, "não pode ser negativo"),
        ({"base_dias": 0}, "maior que zero"),
    ],
)
def test_precificacao_invalida_e_recusada(engine, precificacao, trecho):
    assert trecho in _erros_com(engine, precificacao=precificacao)


def test_motor_nao_sobe_com_config_invalida(engine, pasta_dados):
    dados = engine.config.para_json()
    dados["precificacao"]["base_dias"] = 0
    with pytest.raises(ErroConfiguracao):
        RuleEngine(engine.index, ValidadoresConfig.model_validate(dados), pasta_dados / "v.json", CadastroSituacao(None))


def test_falha_ao_gravar_nao_corrompe_o_json(engine, pasta_dados, monkeypatch):
    arquivo = pasta_dados / "validadores_antecipe.json"
    antes = arquivo.read_text(encoding="utf-8")

    def falha(*args):
        raise OSError("disco cheio")

    monkeypatch.setattr(rule_engine.os, "replace", falha)
    with pytest.raises(OSError):
        salvar_config(arquivo, engine.config)
    assert arquivo.read_text(encoding="utf-8") == antes
    assert not list(pasta_dados.glob(".validadores-*"))  # temporário removido


# ---------------------------------------------------------------------------
# Leitura do CSV de upload
# ---------------------------------------------------------------------------

def test_linhas_em_branco_sao_ignoradas_e_numero_da_linha_e_o_do_arquivo():
    conteudo = (CABECALHO + "\n\n;;;;;;;;;;\n" + linha_csv(SACADO_LIVRE, "X", "1,00", "21/11/2026") + "\n").encode()
    [(numero, registro)] = ler_lote_csv(conteudo)
    assert numero == 4 and registro["NU_DOCUMENTO"] == "X"


def test_so_cabecalho_e_recusado():
    with pytest.raises(ErroArquivoLote, match="nenhuma nota"):
        ler_lote_csv((CABECALHO + "\n").encode())


def test_numero_da_nota_e_cedente_vazios_viram_formato_invalido(engine):
    item = validar(engine, linha_csv(SACADO_LIVRE, "", "1000,00", "21/11/2026", cedente="")).itens[0]
    assert codigos(item) == ["FORMATO_INVALIDO"]
    assert "NU_DOCUMENTO" in item.erros[0].mensagem_empresa and "DOC_CEDENTE" in item.erros[0].mensagem_empresa


def test_cabecalho_aceita_variacoes_de_nome():
    conteudo = "doc cedente;Doc-Sacado;Numero Documento;Tipo;Valor;Vencimento\nA;B;1;Duplicata;10,00;21/11/2026\n"
    [(_, registro)] = ler_lote_csv(conteudo.encode())
    assert registro["VALOR_NOMINAL"] == "10,00" and registro["DATA_VENCIMENTO_ORIGINAL"] == "21/11/2026"


# ---------------------------------------------------------------------------
# Situação cadastral: arquivo local
# ---------------------------------------------------------------------------

def test_arquivo_local_ausente_recusa_tudo(tmp_path):
    cadastro = CadastroSituacao(tmp_path / "nao_existe.json")
    assert cadastro.consultar({SACADO_LIVRE}) == {SACADO_LIVRE: "NAO_ENCONTRADO"}


def test_arquivo_local_recarrega_quando_muda_e_ignora_json_quebrado(tmp_path):
    arquivo = tmp_path / "s.json"
    arquivo.write_text('{"situacoes": {"%s": "ATIVA"}}' % SACADO_LIVRE, encoding="utf-8")
    cadastro = CadastroSituacao(arquivo)
    assert cadastro.consultar({SACADO_LIVRE}) == {SACADO_LIVRE: "ATIVA"}

    arquivo.write_text('{"situacoes": {"%s": "baixada", "  ": "ATIVA"}}' % SACADO_LIVRE, encoding="utf-8")
    assert cadastro.consultar({SACADO_LIVRE}) == {SACADO_LIVRE: "BAIXADA"}

    arquivo.write_text("{quebrado", encoding="utf-8")
    assert cadastro.consultar({SACADO_LIVRE}) == {SACADO_LIVRE: "BAIXADA"}  # mantém a última versão boa


def test_api_fora_do_ar_conta_como_falha():
    cadastro = CadastroSituacao(None, "http://127.0.0.1:9/api/cnpj/v1", timeout_s=0.5)  # porta 9: nada escuta
    assert cadastro.consultar({SACADO_LIVRE}) == {}
    assert cadastro.versao[1] == 1


def test_cnpj_invalido_explica_por_que_nao_da_para_consultar_a_receita(engine):
    item = validar(engine, linha_csv("12.345.678/0001-00", "I1", "1000,00", "21/11/2026")).itens[0]
    situacao = next(e for e in item.erros if e.codigo == "SITUACAO_CADASTRAL_SACADO")
    assert "porque o CNPJ informado está errado" in situacao.mensagem_empresa
    assert "erro de documento desta mesma nota" in situacao.acao_recomendada


def test_concentracao_por_raiz_explica_matriz_e_filiais(engine):
    from .conftest import SACADO_MESMA_RAIZ

    item = validar(engine, linha_csv(SACADO_MESMA_RAIZ, "R1", "15000,00", "21/11/2026")).itens[0]
    assert "somando matriz e filiais, todos os CNPJs que começam com 11.222.333" in item.erros[0].mensagem_empresa
    assert "raiz" not in item.erros[0].mensagem_empresa
