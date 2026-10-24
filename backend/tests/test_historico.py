"""Histórico em SQLite: lotes validados e mudanças de regras."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app import historico as historico_mod
from app.main import app

from .conftest import SACADO_LIVRE, linha_csv, montar_csv

CHAVE = "chave-teste"
AUTH = {"X-API-Key": CHAVE}
LOTE = montar_csv(
    linha_csv(SACADO_LIVRE, "H1", "1000,00", "21/11/2026"),
    linha_csv(SACADO_LIVRE, "H2", "50,00", "21/11/2026"),
)


@pytest.fixture()
def client(pasta_dados, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(pasta_dados))
    monkeypatch.setenv("ADMIN_API_KEY", CHAVE)
    monkeypatch.delenv("RECEITA_API_URL", raising=False)
    with TestClient(app) as c:
        yield c


def enviar(c, **campos):
    return c.post("/api/v1/batches/validate", files={"file": ("l.csv", LOTE, "text/csv")}, data=campos)


def test_lote_validado_fica_no_historico_com_a_chave_completa(client):
    r = enviar(client)
    pagina = client.get("/api/v1/historico/lotes").json()
    assert pagina["total"] == 1 and (pagina["limite"], pagina["offset"]) == (50, 0)
    [lote] = pagina["itens"]
    assert lote["batch_hash"] == r.json()["meta"]["batch_hash_idempotencia"]
    assert len(lote["chave_idempotencia"]) == 64 and lote["chave_idempotencia"] != lote["batch_hash"]
    assert (lote["total_notas"], lote["qtd_aprovadas"], lote["qtd_recusadas"]) == (2, 1, 1)
    assert lote["valor_liquido_receber"] == r.json()["resumo"]["valor_liquido_receber"]
    assert (lote["modo"], lote["data_base"], lote["taxa_mensal"], lote["versao_config"]) == ("lote", "22/10/2026", 0.02, 1)
    assert lote["replay"] is False and lote["what_if"] is False
    assert lote["request_id"] == r.headers["X-Request-ID"]
    assert lote["criado_em"].endswith("+00:00")


def test_repeticao_e_parametros_diferentes_viram_linhas_distintas(client):
    enviar(client)
    enviar(client)  # mesmo arquivo e parâmetros: replay
    enviar(client, modo="carteira")  # mesmo arquivo, outro modo: outra chave
    lotes = client.get("/api/v1/historico/lotes").json()["itens"]  # mais recente primeiro
    assert [l["replay"] for l in lotes] == [False, True, False]
    assert lotes[1]["chave_idempotencia"] == lotes[2]["chave_idempotencia"]
    assert lotes[0]["chave_idempotencia"] != lotes[1]["chave_idempotencia"]
    assert len({l["batch_hash"] for l in lotes}) == 1


def test_paginacao(client):
    for i in range(3):
        enviar(client, data_base=f"2{i}/10/2026")
    pagina = client.get("/api/v1/historico/lotes", params={"limite": 2, "offset": 1}).json()
    assert pagina["total"] == 3 and len(pagina["itens"]) == 2
    assert [l["data_base"] for l in pagina["itens"]] == ["21/10/2026", "20/10/2026"]
    assert client.get("/api/v1/historico/lotes", params={"limite": 0}).status_code == 422
    assert client.get("/api/v1/historico/lotes", params={"limite": 201}).status_code == 422


def test_mudanca_de_regras_aceita_vai_para_o_historico_e_a_recusada_nao(client):
    config = client.get("/api/v1/validators").json()
    assert client.put("/api/v1/validators", json=config).status_code == 401  # sem chave
    for v in config["validadores"]:
        if v["codigo"] == "VALOR_MINIMO":
            v["ativo"] = False
    assert client.put("/api/v1/validators", headers=AUTH, json=config).status_code == 200
    pagina = client.get("/api/v1/historico/regras").json()
    assert pagina["total"] == 1
    [mudanca] = pagina["itens"]
    assert (mudanca["versao_config"], mudanca["regras_ativas"]) == (2, 6)
    assert mudanca["config"] == config
    enviar(client, validadores_override=json.dumps(config))
    assert client.get("/api/v1/historico/lotes").json()["itens"][0]["what_if"] is True


def test_historico_sobrevive_ao_reinicio_da_api(pasta_dados, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(pasta_dados))
    monkeypatch.delenv("RECEITA_API_URL", raising=False)
    with TestClient(app) as c:
        enviar(c)
    with TestClient(app) as c:  # nova instância, mesmo arquivo historico.db
        assert c.get("/api/v1/historico/lotes").json()["total"] == 1
    assert (pasta_dados / "historico.db").exists()


def test_falha_no_historico_nao_derruba_a_validacao(client, monkeypatch):
    def quebrado(self, **campos):
        raise OSError("disco cheio")

    monkeypatch.setattr(historico_mod.Historico, "registrar_lote", quebrado)
    r = enviar(client)
    assert r.status_code == 200 and r.json()["resumo"]["total_notas"] == 2
    assert client.get("/api/v1/historico/lotes").json()["total"] == 0
