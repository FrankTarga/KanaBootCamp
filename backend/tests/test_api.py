from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.main import app

from .conftest import SACADO_CONCENTRADO, SACADO_LIVRE, linha_csv, montar_csv

CHAVES_META = {
    "batch_hash_idempotencia", "tempo_processamento_ms", "data_base_utilizada", "taxa_mensal_aplicada",
    "otimizador_ativo", "valor_liquido_sem_otimizador", "ganho_otimizador_reais", "qtd_notas_salvas_otimizador",
}
CHAVES_RESUMO = {
    "total_notas", "qtd_aprovadas", "qtd_recusadas", "qtd_alertas_fraude", "valor_bruto_total",
    "valor_bruto_aprovado", "valor_bruto_recusado", "desagio_total", "valor_liquido_receber",
    "prazo_medio_ponderado_dias", "contagem_por_motivo",
}
CHAVES_ITEM = {
    "linha_csv", "ordem_avaliacao", "hash_titulo", "nu_documento", "nome_cedente", "doc_cedente", "nome_sacado",
    "doc_sacado", "tipo_recebivel", "valor_nominal", "data_vencimento", "data_aquisicao", "prazo_dias",
    "desagio_reais", "valor_liquido", "status", "severidade", "salva_pelo_otimizador", "erros",
}
CHAVES_ERRO = {"codigo", "titulo_amigavel", "mensagem_empresa", "acao_recomendada"}

CHAVE = "chave-teste"
AUTH = {"X-API-Key": CHAVE}

LOTE = montar_csv(
    linha_csv(SACADO_LIVRE, "A1", "10.000,00", "21/11/2026"),
    linha_csv(SACADO_LIVRE, "A2", "50,00", "21/11/2026"),
    linha_csv(SACADO_CONCENTRADO, "A3", "20000,00", "21/11/2026"),
)


@pytest.fixture()
def client(pasta_dados, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(pasta_dados))
    monkeypatch.delenv("DATA_BASE_PADRAO", raising=False)
    monkeypatch.delenv("RECEITA_API_URL", raising=False)
    monkeypatch.setenv("ADMIN_API_KEY", CHAVE)
    with TestClient(app) as c:
        yield c


def enviar(client, conteudo=LOTE, **campos):
    return client.post("/api/v1/batches/validate", files={"file": ("lote.csv", conteudo, "text/csv")}, data=campos)


def test_health(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["status"] == "ready"
    assert corpo["data_base_padrao"] == "22/10/2026"
    assert corpo["estoque_total_linhas"] == 4
    assert corpo["estoque_antecipe_linhas"] == 3
    assert corpo["patrimonio_antecipe_fidc"] == 1_000_000.0
    assert corpo["fundos_monitorados"] == 2
    assert corpo["regras_ativas_count"] == 7
    assert corpo["taxa_mensal_padrao"] == 0.02
    assert r.headers["X-Request-ID"]


def test_validate_respeita_contrato(client):
    r = enviar(client)
    assert r.status_code == 200
    corpo = r.json()
    assert set(corpo) == {"meta", "resumo", "itens", "analise_recusas"}
    assert set(corpo["meta"]) == CHAVES_META
    assert set(corpo["resumo"]) == CHAVES_RESUMO
    assert all(set(i) == CHAVES_ITEM for i in corpo["itens"])
    assert all(set(e) == CHAVES_ERRO for i in corpo["itens"] for e in i["erros"])
    assert {i["status"] for i in corpo["itens"]} <= {"APROVADA", "RECUSADA"}
    assert {i["severidade"] for i in corpo["itens"]} <= {"OK", "REGRA_NEGOCIO", "DUPLICIDADE", "FRAUDE"}
    assert corpo["meta"]["data_base_utilizada"] == "22/10/2026"
    assert corpo["resumo"]["qtd_aprovadas"] == 1
    assert {m["codigo"] for m in corpo["resumo"]["contagem_por_motivo"]} == {"VALOR_MINIMO", "CONCENTRACAO_MAXIMA_SACADO"}


def test_parametros_do_form(client):
    corpo = enviar(client, data_base="23/10/2026", taxa_mensal="0,025", otimizar_lote="false").json()
    assert corpo["meta"]["data_base_utilizada"] == "23/10/2026"
    assert corpo["meta"]["taxa_mensal_aplicada"] == 0.025
    assert corpo["meta"]["otimizador_ativo"] is False
    assert corpo["itens"][0]["prazo_dias"] == 29


@pytest.mark.parametrize(
    ("campos", "codigo"),
    [
        ({"data_base": "32/13/2026"}, "DATA_BASE_INVALIDA"),
        ({"taxa_mensal": "2.5"}, "TAXA_INVALIDA"),
        ({"otimizar_lote": "talvez"}, "OTIMIZAR_LOTE_INVALIDO"),
        ({"validadores_override": "{nao e json"}, "OVERRIDE_INVALIDO"),
    ],
)
def test_parametros_invalidos(client, campos, codigo):
    r = enviar(client, **campos)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == codigo


def test_arquivo_invalido(client):
    r = enviar(client, conteudo=b"COLUNA_A;COLUNA_B\n1;2\n")
    assert r.status_code == 422
    erro = r.json()["error"]
    assert erro["code"] == "ARQUIVO_INVALIDO" and "DOC_SACADO" in erro["message"]
    assert client.post("/api/v1/batches/validate").json()["error"]["code"] == "REQUISICAO_INVALIDA"


def test_idempotencia_de_requisicao(client):
    primeira = enviar(client)
    segunda = enviar(client)
    assert primeira.headers["X-Idempotent-Replay"] == "false"
    assert segunda.headers["X-Idempotent-Replay"] == "true"
    assert primeira.json() == segunda.json()
    assert enviar(client, otimizar_lote="false").headers["X-Idempotent-Replay"] == "false"


def test_put_validators_zero_deploy(client, pasta_dados):
    assert enviar(client).json()["resumo"]["qtd_aprovadas"] == 1
    config = client.get("/api/v1/validators").json()
    assert config == json.loads((pasta_dados / "validadores_antecipe.json").read_text(encoding="utf-8"))
    for v in config["validadores"]:
        if v["codigo"] == "VALOR_MINIMO":
            v["ativo"] = False

    r = client.put("/api/v1/validators", headers=AUTH, json=config)
    assert r.status_code == 200 and r.json() == config
    em_disco = json.loads((pasta_dados / "validadores_antecipe.json").read_text(encoding="utf-8"))
    assert em_disco == config
    assert client.get("/api/v1/health").json()["versao_config"] == 2
    assert client.get("/api/v1/health").json()["regras_ativas_count"] == 6

    revalidado = enviar(client)
    assert revalidado.headers["X-Idempotent-Replay"] == "false"  # cache invalidado pela nova versão
    assert revalidado.json()["resumo"]["qtd_aprovadas"] == 2


def test_put_validators_invalido_nao_altera_nada(client, pasta_dados):
    antes = (pasta_dados / "validadores_antecipe.json").read_text(encoding="utf-8")
    config = client.get("/api/v1/validators").json()
    config["validadores"].append({"codigo": "REGRA_INVENTADA", "ativo": True, "parametros": {}})
    r = client.put("/api/v1/validators", headers=AUTH, json=config)
    assert r.status_code == 422
    erro = r.json()["error"]
    assert erro["code"] == "CONFIGURACAO_INVALIDA" and any("REGRA_INVENTADA" in d for d in erro["details"])
    assert client.put("/api/v1/validators", headers=AUTH, json={"validadores": "x"}).json()["error"]["code"] == "REQUISICAO_INVALIDA"
    assert (pasta_dados / "validadores_antecipe.json").read_text(encoding="utf-8") == antes
    assert client.get("/api/v1/health").json()["versao_config"] == 1


def test_what_if_override_nao_persiste(client, pasta_dados):
    antes = (pasta_dados / "validadores_antecipe.json").read_text(encoding="utf-8")
    config = client.get("/api/v1/validators").json()
    for v in config["validadores"]:
        if v["codigo"] == "CONCENTRACAO_MAXIMA_SACADO":
            v["ativo"] = False
    simulado = enviar(client, validadores_override=json.dumps(config)).json()
    assert simulado["resumo"]["qtd_aprovadas"] == 2
    assert enviar(client).json()["resumo"]["qtd_aprovadas"] == 1
    assert (pasta_dados / "validadores_antecipe.json").read_text(encoding="utf-8") == antes


def test_trocar_fundo_e_recusado_no_put_e_no_what_if(client):
    config = client.get("/api/v1/validators").json()
    config["fundo"]["nome"] = "OUTRO FIDC"
    r = client.put("/api/v1/validators", headers=AUTH, json=config)
    assert r.status_code == 422 and any("reiniciar" in d for d in r.json()["error"]["details"])
    r = enviar(client, validadores_override=json.dumps(config))
    assert r.status_code == 422 and r.json()["error"]["code"] == "OVERRIDE_INVALIDO"


def test_health_reflete_taxa_do_put(client):
    config = client.get("/api/v1/validators").json()
    config["precificacao"]["taxa_mensal_percentual"] = 1.5
    assert client.put("/api/v1/validators", headers=AUTH, json=config).status_code == 200
    assert client.get("/api/v1/health").json()["taxa_mensal_padrao"] == 0.015
    assert enviar(client).json()["meta"]["taxa_mensal_aplicada"] == 0.015


def test_put_exige_api_key(client):
    config = client.get("/api/v1/validators").json()
    assert client.put("/api/v1/validators", json=config).json()["error"]["code"] == "NAO_AUTORIZADO"
    r = client.put("/api/v1/validators", headers={"X-API-Key": "errada"}, json=config)
    assert r.status_code == 401
    assert client.get("/api/v1/health").json()["versao_config"] == 1


def test_put_bloqueado_sem_admin_api_key(pasta_dados, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(pasta_dados))
    monkeypatch.delenv("ADMIN_API_KEY", raising=False)
    with TestClient(app) as c:
        r = c.put("/api/v1/validators", headers=AUTH, json=c.get("/api/v1/validators").json())
    assert r.status_code == 403 and r.json()["error"]["code"] == "PUT_DESABILITADO"


# ---------------------------------------------------------------------------
# Erros padronizados, limites e cache
# ---------------------------------------------------------------------------

def test_rota_inexistente_e_raiz(client):
    r = client.get("/api/v1/nao-existe")
    assert r.status_code == 404 and r.json()["error"]["code"] == "NAO_ENCONTRADO"
    assert client.get("/").json()["docs"] == "/docs"


def test_erro_inesperado_nao_vaza_stack_trace(pasta_dados, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(pasta_dados))
    with TestClient(app, raise_server_exceptions=False) as c:
        def explode(*args, **kwargs):
            raise RuntimeError("segredo interno")
        monkeypatch.setattr(c.app.state.engine, "validar_lote", explode)
        r = enviar(c)
    assert r.status_code == 500
    assert r.json()["error"]["code"] == "ERRO_INTERNO" and "segredo" not in r.text
    assert r.headers["X-Request-ID"] in r.json()["error"]["message"]


def test_arquivo_vazio_e_grande_demais(pasta_dados, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(pasta_dados))
    monkeypatch.setenv("MAX_UPLOAD_MB", "0")
    with TestClient(app) as c:
        assert enviar(c).status_code == 413
    monkeypatch.setenv("MAX_UPLOAD_MB", "20")
    with TestClient(app) as c:
        r = enviar(c, conteudo=b"   \n")
    assert r.status_code == 422 and r.json()["error"]["code"] == "ARQUIVO_INVALIDO"


@pytest.mark.parametrize(("campos", "codigo"), [
    ({"taxa_mensal": "abc"}, "TAXA_INVALIDA"),
    ({"validadores_override": '{"validadores": "x"}'}, "OVERRIDE_INVALIDO"),
])
def test_mais_parametros_invalidos(client, campos, codigo):
    assert enviar(client, **campos).json()["error"]["code"] == codigo


def test_otimizar_aceita_sim(client):
    assert enviar(client, otimizar_lote="sim").json()["meta"]["otimizador_ativo"] is True


def test_put_que_nao_consegue_gravar_nao_muda_nada(client, monkeypatch):
    from app import rule_engine

    def falha(*args):
        raise OSError("disco cheio")

    monkeypatch.setattr(rule_engine, "salvar_config", falha)
    r = client.put("/api/v1/validators", headers=AUTH, json=client.get("/api/v1/validators").json())
    assert r.status_code == 500 and r.json()["error"]["code"] == "FALHA_PERSISTENCIA"
    assert client.get("/api/v1/health").json()["versao_config"] == 1


def test_cache_idempotencia_descarta_o_mais_antigo():
    from app.main import CacheIdempotencia

    cache = CacheIdempotencia(1)
    cache.guardar("a", 1)
    cache.guardar("b", 2)
    assert cache.obter("a") is None and cache.obter("b") == 2
    desligado = CacheIdempotencia(0)
    desligado.guardar("a", 1)
    assert desligado.obter("a") is None


# ---------------------------------------------------------------------------
# analise_recusas (painel do Estatístico) na resposta da validação
# ---------------------------------------------------------------------------

def test_analise_recusas_vem_na_resposta_e_bate_com_a_funcao_do_quant(client):
    from app.analise_recusas import analisar_recusas

    corpo = enviar(client).json()
    analise = corpo["analise_recusas"]
    assert analise == analisar_recusas(corpo["itens"])  # mesma função, mesmos itens: a tela não recalcula nada
    assert analise["qtd_notas"] == 3 and analise["qtd_recusadas"] == 2
    grupos = analise["grupos"]
    assert round(sum(g["pct_das_recusadas"] for g in grupos["um_problema"]) + grupos["mais_de_um_problema"]["pct_das_recusadas"], 1) == 100.0
    assert {m["codigo"] for m in analise["motivos"]} == {"VALOR_MINIMO", "CONCENTRACAO_MAXIMA_SACADO"}


def test_analise_recusas_no_what_if_reflete_as_regras_simuladas(client):
    config = client.get("/api/v1/validators").json()
    for v in config["validadores"]:
        if v["codigo"] == "VALOR_MINIMO":
            v["ativo"] = False
    analise = enviar(client, validadores_override=json.dumps(config)).json()["analise_recusas"]
    assert analise["qtd_recusadas"] == 1
    assert [m["codigo"] for m in analise["motivos"]] == ["CONCENTRACAO_MAXIMA_SACADO"]


def test_analise_recusas_sem_recusas(client):
    corpo = enviar(client, conteudo=montar_csv(linha_csv(SACADO_LIVRE, "OK", "1000,00", "21/11/2026"))).json()
    analise = corpo["analise_recusas"]
    assert analise["qtd_recusadas"] == 0 and analise["motivos"] == [] and analise["grupos"]["um_problema"] == []


def test_cache_nao_guarda_lote_grande(pasta_dados, monkeypatch):
    """Resposta acima de CACHE_MAX_NOTAS não fica na memória; lote pequeno continua com replay."""
    monkeypatch.setenv("DATA_DIR", str(pasta_dados))
    monkeypatch.setenv("CACHE_MAX_NOTAS", "2")
    monkeypatch.delenv("RECEITA_API_URL", raising=False)
    grande = montar_csv(*(linha_csv(SACADO_LIVRE, f"G{i}", "1000,00", "21/11/2026") for i in range(3)))
    pequeno = montar_csv(linha_csv(SACADO_LIVRE, "P1", "1000,00", "21/11/2026"))
    with TestClient(app) as c:
        replays_grande = [enviar(c, conteudo=grande).headers["X-Idempotent-Replay"] for _ in range(2)]
        replays_pequeno = [enviar(c, conteudo=pequeno).headers["X-Idempotent-Replay"] for _ in range(2)]
        resposta = enviar(c, conteudo=pequeno)
    assert replays_grande == ["false", "false"]
    assert replays_pequeno == ["false", "true"]
    assert resposta.headers["content-type"] == "application/json"
    assert resposta.json()["itens"][0]["nu_documento"] == "P1"
