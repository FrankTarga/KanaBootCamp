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

LOTE = montar_csv(
    linha_csv(SACADO_LIVRE, "A1", "10.000,00", "21/11/2026"),
    linha_csv(SACADO_LIVRE, "A2", "50,00", "21/11/2026"),
    linha_csv(SACADO_CONCENTRADO, "A3", "20000,00", "21/11/2026"),
)


@pytest.fixture()
def client(pasta_dados, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(pasta_dados))
    monkeypatch.delenv("DATA_BASE_PADRAO", raising=False)
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
    assert r.headers["X-Request-ID"]


def test_validate_respeita_contrato(client):
    r = enviar(client)
    assert r.status_code == 200
    corpo = r.json()
    assert set(corpo) == {"meta", "resumo", "itens"}
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

    r = client.put("/api/v1/validators", json=config)
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
    r = client.put("/api/v1/validators", json=config)
    assert r.status_code == 422
    erro = r.json()["error"]
    assert erro["code"] == "CONFIGURACAO_INVALIDA" and any("REGRA_INVENTADA" in d for d in erro["details"])
    assert client.put("/api/v1/validators", json={"validadores": "x"}).json()["error"]["code"] == "REQUISICAO_INVALIDA"
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
