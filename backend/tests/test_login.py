"""Login do portal: usuário da banca semeado pelo env, senha só como hash."""

from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.historico import hash_senha, senha_confere
from app.main import app

EMAIL = "banca@antecipe.com.br"
SENHA = "senha-da-banca"


@pytest.fixture()
def client(pasta_dados, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(pasta_dados))
    monkeypatch.setenv("BANCA_SENHA", SENHA)
    monkeypatch.delenv("BANCA_EMAIL", raising=False)
    monkeypatch.delenv("RECEITA_API_URL", raising=False)
    with TestClient(app) as c:
        yield c


def login(c, email, senha):
    return c.post("/api/v1/auth/login", json={"email": email, "senha": senha})


def test_banca_entra_com_a_senha_do_env(client):
    r = login(client, "  Banca@Antecipe.com.br ", SENHA)
    assert r.status_code == 200
    assert r.json() == {"email": EMAIL, "nome": "Banca avaliadora", "cargo": "Gestor do fundo", "role": "GESTOR"}


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
