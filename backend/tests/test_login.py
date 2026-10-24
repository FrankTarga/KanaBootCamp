"""Login do portal: usuário da banca semeado pelo env, senha só como hash."""

from __future__ import annotations

import base64
import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.historico import hash_senha, senha_confere
from app.main import app
from app.sessao import emitir_token, ler_token

EMAIL = "banca@antecipe.com.br"
SENHA = "senha-da-banca"
SENHA_CEDENTE = "senha-da-empresa"


@pytest.fixture()
def client(pasta_dados, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(pasta_dados))
    monkeypatch.setenv("BANCA_SENHA", SENHA)
    monkeypatch.setenv("CEDENTE_SENHA", SENHA_CEDENTE)
    monkeypatch.delenv("BANCA_EMAIL", raising=False)
    monkeypatch.delenv("CEDENTE_EMAIL", raising=False)
    monkeypatch.delenv("RECEITA_API_URL", raising=False)
    with TestClient(app) as c:
        yield c


def test_cedente_entra_com_o_proprio_perfil_e_nao_com_a_senha_do_gestor(client):
    r = login(client, "empresa@antecipe.com.br", SENHA_CEDENTE)
    assert r.status_code == 200 and r.json()["role"] == "CEDENTE"
    assert login(client, "empresa@antecipe.com.br", SENHA).status_code == 401


def login(c, email, senha):
    return c.post("/api/v1/auth/login", json={"email": email, "senha": senha})


def test_banca_entra_com_a_senha_do_env(client):
    r = login(client, "  Banca@Antecipe.com.br ", SENHA)
    assert r.status_code == 200
    corpo = r.json()
    assert corpo.pop("token")
    assert corpo == {"email": EMAIL, "nome": "Banca avaliadora", "cargo": "Gestor do fundo", "role": "GESTOR"}


def me(c, token):
    return c.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})


def test_token_do_login_abre_a_sessao(client):
    token = login(client, EMAIL, SENHA).json()["token"]
    r = me(client, token)
    assert r.status_code == 200 and r.json()["role"] == "GESTOR" and r.json()["email"] == EMAIL


def test_token_forjado_ou_ausente_da_401(client):
    payload, _, assinatura = login(client, EMAIL, SENHA).json()["token"].partition(".")
    forjado = base64.urlsafe_b64encode(json.dumps({"email": "x", "nome": "x", "cargo": "x", "role": "GESTOR", "exp": 9e9}).encode()).decode().rstrip("=")
    for token in (f"{forjado}.{assinatura}", f"{payload}.assinatura-falsa", "lixo", ""):
        r = me(client, token)
        assert r.status_code == 401 and r.json()["error"]["code"] == "SESSAO_INVALIDA"
    assert client.get("/api/v1/auth/me").status_code == 401


def test_token_vencido_da_401():
    usuario = {"email": EMAIL, "role": "GESTOR"}
    assert ler_token(b"s", emitir_token(b"s", usuario, 60)) == usuario
    assert ler_token(b"s", emitir_token(b"s", usuario, -1)) is None
    assert ler_token(b"outro", emitir_token(b"s", usuario, 60)) is None


@pytest.mark.parametrize("email,senha", [(EMAIL, "errada"), ("ninguem@x.com", SENHA)])
def test_credencial_errada_da_401_sem_dizer_qual_campo(client, email, senha):
    r = login(client, email, senha)
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "CREDENCIAIS_INVALIDAS"


def test_corpo_invalido_da_422(client):
    assert client.post("/api/v1/auth/login", json={"email": EMAIL}).status_code == 422


def test_senha_fica_so_como_hash_no_banco(client, pasta_dados):
    with sqlite3.connect(pasta_dados / "historico.db") as conn:
        [(guardado,)] = conn.execute("SELECT senha_hash FROM usuarios WHERE email = ?", (EMAIL,)).fetchall()
    assert SENHA not in guardado and guardado.startswith("scrypt$")


def test_sem_banca_senha_ninguem_entra(pasta_dados, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(pasta_dados))
    monkeypatch.delenv("BANCA_SENHA", raising=False)
    monkeypatch.delenv("RECEITA_API_URL", raising=False)
    with TestClient(app) as c:
        assert login(c, EMAIL, SENHA).status_code == 401


def test_hash_tem_salt_e_confere():
    a, b = hash_senha("x"), hash_senha("x")
    assert a != b and senha_confere("x", a) and not senha_confere("y", a)


def test_login_com_usuario_do_banco_acid(client, pasta_dados):
    import app.database as db_mod

    db_mod.salvar_usuario(
        email="analista.acid@antecipe.com.br",
        senha="SenhaForteAcid123",
        nome="Analista ACID",
        cargo="Analista de Risco",
        role="GESTOR",
    )

    # Tentativa com senha errada
    r_errada = login(client, "analista.acid@antecipe.com.br", "senha_incorreta")
    assert r_errada.status_code == 401
    assert r_errada.json()["error"]["code"] == "CREDENCIAIS_INVALIDAS"

    # Login com sucesso pelo endpoint /auth/login
    r_ok = login(client, "analista.acid@antecipe.com.br", "SenhaForteAcid123")
    assert r_ok.status_code == 200
    dados = r_ok.json()
    assert dados["email"] == "analista.acid@antecipe.com.br"
    assert dados["role"] == "GESTOR"
    assert dados["nome"] == "Analista ACID"
    assert "token" in dados

    # Acessa /auth/me usando o token gerado
    r_me = me(client, dados["token"])
    assert r_me.status_code == 200
    assert r_me.json()["email"] == "analista.acid@antecipe.com.br"


def test_startup_semeia_usuarios_no_banco_acid(client, pasta_dados):
    import app.database as db_mod

    u_banca = db_mod.autenticar_usuario(EMAIL, SENHA)
    assert u_banca is not None
    assert u_banca["email"] == EMAIL
    assert u_banca["role"] == "GESTOR"

    u_cedente = db_mod.autenticar_usuario("empresa@antecipe.com.br", SENHA_CEDENTE)
    assert u_cedente is not None
    assert u_cedente["role"] == "CEDENTE"



@pytest.mark.parametrize("valor", [None, ""])  # ausente, ou vazio como o docker-compose repassa
def test_sem_sessao_segredo_ninguem_forja_token(pasta_dados, monkeypatch, valor):
    monkeypatch.setenv("DATA_DIR", str(pasta_dados))
    monkeypatch.setenv("BANCA_SENHA", SENHA)
    monkeypatch.delenv("RECEITA_API_URL", raising=False)
    if valor is None:
        monkeypatch.delenv("SESSAO_SEGREDO", raising=False)
    else:
        monkeypatch.setenv("SESSAO_SEGREDO", valor)
    gestor = {"id": 1, "email": EMAIL, "nome": "Banca", "cargo": "Gestor", "role": "GESTOR"}
    with TestClient(app) as c:
        for chave in (b"", b"segredo-antecipe-pro-fidc-2026"):  # chave vazia e o antigo valor fixo do código
            forjado = emitir_token(chave, gestor, 3600)
            assert c.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {forjado}"}).status_code == 401
        token = login(c, EMAIL, SENHA).json()["token"]
        assert c.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200


def test_tirar_a_senha_do_env_desativa_a_conta(client, pasta_dados, monkeypatch):
    """Sem CEDENTE_SENHA no boot seguinte, a senha antiga para de valer nos dois bancos e o histórico fica."""
    token = login(client, "empresa@antecipe.com.br", SENHA_CEDENTE).json()["token"]
    lote = b"DOC_CEDENTE;DOC_SACADO;NU_DOCUMENTO;TIPO_RECEBIVEL;VALOR_NOMINAL;DATA_VENCIMENTO_ORIGINAL\n1;2;3;Duplicata;1;01/01/2027\n"
    r = client.post("/api/v1/batches/validate", files={"file": ("l.csv", lote, "text/csv")},
                    headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200  # lote ligado ao cedente (chave estrangeira em historico.lotes)

    monkeypatch.delenv("CEDENTE_SENHA")
    with TestClient(app) as c:
        assert login(c, "empresa@antecipe.com.br", SENHA_CEDENTE).status_code == 401
        assert login(c, EMAIL, SENHA).status_code == 200
    with sqlite3.connect(pasta_dados / "historico.db") as conn:
        assert conn.execute("SELECT COUNT(*) FROM lotes WHERE usuario_id IS NOT NULL").fetchone()[0] == 1
