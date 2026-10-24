"""Contratar a antecipação (POST /batches/{hash}/liquidate): login, dono do lote e revalidação antes de comprar."""

from __future__ import annotations

import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.main import app

from .conftest import SACADO_CONCENTRADO, SACADO_LIVRE, linha_csv, montar_csv
from .test_historico import CEDENTE, GESTOR, _ambiente, bearer

LOTE = montar_csv(
    linha_csv(SACADO_LIVRE, "L1", "1234,56", "21/11/2026"),
    linha_csv(SACADO_LIVRE, "L2", "50,00", "21/11/2026"),  # recusada: VALOR_MINIMO
)


@pytest.fixture()
def client(pasta_dados, monkeypatch):
    _ambiente(pasta_dados, monkeypatch)
    with TestClient(app) as c:
        yield c


def validar(c, conteudo, token, **campos):
    r = c.post("/api/v1/batches/validate", files={"file": ("l.csv", conteudo, "text/csv")}, data=campos, headers=token)
    assert r.status_code == 200, r.text
    return r.json()["meta"]["batch_hash_idempotencia"]


def liquidar(c, batch_hash, token=None):
    return c.post(f"/api/v1/batches/{batch_hash}/liquidate", headers=token or {})


def titulos_comprados(pasta_dados):
    with sqlite3.connect(pasta_dados / "antecipe_acid.db") as conn:
        return [l[0] for l in conn.execute("SELECT nu_documento FROM titulos_adquiridos ORDER BY nu_documento")]


def test_contratar_exige_login(client):
    batch_hash = validar(client, LOTE, bearer(client, *CEDENTE))
    for token in (None, {"Authorization": "Bearer token-forjado"}):
        r = liquidar(client, batch_hash, token)
        assert r.status_code == 401 and r.json()["error"]["code"] == "SESSAO_INVALIDA"


def test_cedente_so_contrata_o_proprio_lote_e_gestor_contrata_qualquer_um(client, pasta_dados):
    gestor, cedente = bearer(client, *GESTOR), bearer(client, *CEDENTE)
    do_gestor = validar(client, montar_csv(linha_csv(SACADO_LIVRE, "G1", "2000,00", "21/11/2026")), gestor)
    r = liquidar(client, do_gestor, cedente)
    assert r.status_code == 404 and r.json()["error"]["code"] == "LOTE_NAO_ENCONTRADO"  # não revela que existe

    do_cedente = validar(client, LOTE, cedente)
    r = liquidar(client, do_cedente, cedente)
    assert r.status_code == 200, r.text
    assert (r.json()["status"], r.json()["qtd_titulos_comprados"]) == ("LIQUIDADO", 1)  # só a aprovada
    assert liquidar(client, do_cedente, cedente).json()["status"] == "JA_LIQUIDADO"
    assert liquidar(client, do_gestor, gestor).status_code == 200
    assert titulos_comprados(pasta_dados) == ["G1", "L1"]

    with sqlite3.connect(pasta_dados / "antecipe_acid.db") as conn:
        ids = dict(conn.execute("SELECT role, id FROM usuarios"))
        quem_contratou = dict(conn.execute("SELECT batch_hash, liquidado_por FROM lotes_operacoes"))
    assert quem_contratou == {do_cedente: ids["CEDENTE"], do_gestor: ids["GESTOR"]}


def test_lote_validado_sem_login_so_o_gestor_contrata(client):
    batch_hash = validar(client, LOTE, {})
    assert liquidar(client, batch_hash, bearer(client, *CEDENTE)).status_code == 404
    assert liquidar(client, batch_hash, bearer(client, *GESTOR)).status_code == 200


def test_reenvio_do_cache_passa_o_lote_para_quem_reenviou(client):
    validar(client, LOTE, bearer(client, *GESTOR))
    cedente = bearer(client, *CEDENTE)
    batch_hash = validar(client, LOTE, cedente)  # mesma chave: resposta do cache
    assert liquidar(client, batch_hash, cedente).status_code == 200


def test_simulacao_do_gestor_nao_vira_compra(client, pasta_dados):
    cedente, gestor = bearer(client, *CEDENTE), bearer(client, *GESTOR)
    batch_hash = validar(client, LOTE, cedente)
    regras = client.get("/api/v1/validators").json()
    for v in regras["validadores"]:
        if v["codigo"] == "VALOR_MINIMO":
            v["ativo"] = False
    # mesmo arquivo, regra relaxada só na simulação: aprovaria as duas notas
    assert validar(client, LOTE, gestor, validadores_override=json.dumps(regras)) == batch_hash
    r = liquidar(client, batch_hash, cedente)
    assert r.status_code == 200 and r.json()["qtd_titulos_comprados"] == 1
    assert titulos_comprados(pasta_dados) == ["L1"]


def test_carteira_nao_vira_compra(client):
    gestor = bearer(client, *GESTOR)
    batch_hash = validar(client, montar_csv(linha_csv(SACADO_LIVRE, "C1", "1000,00", "21/11/2026")), gestor, modo="carteira")
    assert liquidar(client, batch_hash, gestor).status_code == 404


@pytest.mark.parametrize("campos", [{"taxa_mensal": "0"}, {"data_base": "01/11/2026"}])
def test_condicao_escolhida_no_envio_nao_vira_compra(client, pasta_dados, campos):
    """Taxa zero ou data-base escolhida pela empresa mudam o deságio: a compra sai só nas condições do fundo."""
    cedente = bearer(client, *CEDENTE)
    batch_hash = validar(client, LOTE, cedente, **campos)
    r = liquidar(client, batch_hash, cedente)
    assert r.status_code == 409 and r.json()["error"]["code"] == "LOTE_DESATUALIZADO"
    assert titulos_comprados(pasta_dados) == []
    # validando de novo nas condições do fundo, a compra sai
    assert liquidar(client, validar(client, LOTE, cedente), cedente).status_code == 200


def test_dois_lotes_que_juntos_estouram_a_concentracao(client, pasta_dados):
    """Sacado com 9% da carteira de 1 milhão: cada nota de 8 mil cabe sozinha no teto de 10%, as duas juntas não."""
    cedente = bearer(client, *CEDENTE)
    lote_a = validar(client, montar_csv(linha_csv(SACADO_CONCENTRADO, "A1", "8000,00", "21/11/2026")), cedente)
    lote_b = validar(client, montar_csv(linha_csv(SACADO_CONCENTRADO, "B1", "8000,00", "21/11/2026")), cedente)
    assert liquidar(client, lote_a, cedente).status_code == 200
    r = liquidar(client, lote_b, cedente)
    assert r.status_code == 409 and r.json()["error"]["code"] == "LOTE_DESATUALIZADO"
    assert titulos_comprados(pasta_dados) == ["A1"]


def test_nota_comprada_em_outro_lote_nao_e_comprada_de_novo(client, pasta_dados):
    cedente = bearer(client, *CEDENTE)
    nota = linha_csv(SACADO_LIVRE, "D1", "1000,00", "21/11/2026")
    lote_a = validar(client, montar_csv(nota), cedente)
    lote_b = validar(client, montar_csv(nota, linha_csv(SACADO_LIVRE, "D2", "1000,00", "21/11/2026")), cedente)
    assert liquidar(client, lote_a, cedente).status_code == 200
    r = liquidar(client, lote_b, cedente)
    assert r.status_code == 409 and r.json()["error"]["code"] == "LOTE_DESATUALIZADO"
    assert "UNIQUE" not in r.text  # sem detalhe do SQLite na resposta
    assert titulos_comprados(pasta_dados) == ["D1"]


def test_historico_de_operacoes_cada_um_ve_o_seu(client):
    gestor, cedente = bearer(client, *GESTOR), bearer(client, *CEDENTE)
    do_gestor = validar(client, montar_csv(linha_csv(SACADO_LIVRE, "H1", "2000,00", "21/11/2026")), gestor)
    do_cedente = validar(client, LOTE, cedente)
    assert client.get("/api/v1/batches/history").status_code == 401

    def lotes(token):
        return {op["batch_hash"] for op in client.get("/api/v1/batches/history", headers=token).json()["historico"]}

    assert lotes(cedente) == {do_cedente}
    assert lotes(gestor) == {do_gestor, do_cedente}


def test_auditoria_de_regras_so_para_gestor(client):
    rota = "/api/v1/validators/audit"
    assert client.get(rota).status_code == 401
    r = client.get(rota, headers=bearer(client, *CEDENTE))
    assert r.status_code == 403 and r.json()["error"]["code"] == "SEM_PERMISSAO"
    assert client.get(rota, headers=bearer(client, *GESTOR)).status_code == 200
