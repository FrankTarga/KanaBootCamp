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


# ---------------------------------------------------------------------------
# Notas e erros dos lotes antigos
# ---------------------------------------------------------------------------

def _ultimo_lote_id(c):
    return c.get("/api/v1/historico/lotes", params={"limite": 1}).json()["itens"][0]["id"]


def test_detalhe_de_lote_antigo_traz_notas_e_motivos(client):
    resposta = enviar(client).json()
    detalhe = client.get(f"/api/v1/historico/lotes/{_ultimo_lote_id(client)}").json()
    assert detalhe["notas_guardadas"] is True and detalhe["total_notas_guardadas"] == 2
    aprovada, recusada = detalhe["notas"]
    assert (aprovada["nu_documento"], aprovada["status"], aprovada["erros"]) == ("H1", "APROVADA", [])
    assert recusada["status"] == "RECUSADA" and recusada["erros"][0]["codigo"] == "VALOR_MINIMO"
    # é a mesma explicação que a empresa recebeu na hora
    assert recusada["erros"] == resposta["itens"][1]["erros"]
    assert recusada["valor_liquido"] == resposta["itens"][1]["valor_liquido"]


def test_repeticao_do_cache_mostra_as_notas_do_envio_original(client):
    enviar(client)
    original = _ultimo_lote_id(client)
    enviar(client)
    replay = _ultimo_lote_id(client)
    detalhe = client.get(f"/api/v1/historico/lotes/{replay}").json()
    assert detalhe["lote"]["replay"] is True
    assert detalhe["notas_de_lote_id"] == original and detalhe["total_notas_guardadas"] == 2


def test_modo_carteira_guarda_so_o_resumo(client):
    enviar(client, modo="carteira")
    detalhe = client.get(f"/api/v1/historico/lotes/{_ultimo_lote_id(client)}").json()
    assert detalhe["lote"]["modo"] == "carteira" and detalhe["lote"]["total_notas"] == 2
    assert detalhe["notas_guardadas"] is False and detalhe["notas"] == []


def test_paginacao_das_notas_e_lote_inexistente(client):
    enviar(client)
    lote_id = _ultimo_lote_id(client)
    pagina = client.get(f"/api/v1/historico/lotes/{lote_id}", params={"limite": 1, "offset": 1}).json()
    assert pagina["total_notas_guardadas"] == 2 and [n["nu_documento"] for n in pagina["notas"]] == ["H2"]
    r = client.get("/api/v1/historico/lotes/999999")
    assert r.status_code == 404 and r.json()["error"]["code"] == "LOTE_NAO_ENCONTRADO"


def test_busca_por_numero_da_nota_ignora_zeros_a_esquerda(client):
    zeros = montar_csv(linha_csv(SACADO_LIVRE, "000123", "1000,00", "21/11/2026"))
    client.post("/api/v1/batches/validate", files={"file": ("a.csv", zeros, "text/csv")})
    sem_zeros = montar_csv(linha_csv(SACADO_LIVRE, "123", "50,00", "22/11/2026"))
    client.post("/api/v1/batches/validate", files={"file": ("b.csv", sem_zeros, "text/csv")})
    pagina = client.get("/api/v1/historico/notas", params={"nu_documento": "0000123"}).json()
    assert pagina["total"] == 2
    recente, antiga = pagina["itens"]
    assert (recente["nu_documento"], recente["status"], recente["codigos_erro"]) == ("123", "RECUSADA", ["VALOR_MINIMO"])
    assert (antiga["nu_documento"], antiga["status"], antiga["codigos_erro"]) == ("000123", "APROVADA", [])
    assert client.get("/api/v1/historico/notas", params={"nu_documento": "inexistente"}).json()["total"] == 0
    assert client.get("/api/v1/historico/notas").status_code == 422  # nu_documento é obrigatório


def test_lote_e_notas_entram_juntos_ou_nao_entram(client, monkeypatch):
    """Se a gravação das notas falhar depois do resumo, nada fica gravado (transação única)."""
    def quebra(_nu):
        raise ValueError("falha no meio da gravação das notas")

    monkeypatch.setattr(historico_mod, "normalizar_nu_documento", quebra)
    assert enviar(client).status_code == 200  # a validação segue
    assert client.get("/api/v1/historico/lotes").json()["total"] == 0
