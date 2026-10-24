"""mock-receita/: mesma resposta da BrasilAPI para os CNPJs do estoque + sobrescritas da demo."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from fastapi.testclient import TestClient

from .conftest import SACADO_BAIXADO, SACADO_GRANDE, SACADO_SEM_CADASTRO

MOCK = Path(__file__).resolve().parents[2] / "mock-receita" / "main.py"


def carregar_mock(pasta_dados, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(pasta_dados))
    spec = importlib.util.spec_from_file_location("mock_receita_main", MOCK)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return TestClient(modulo.app)


def test_mock_responde_no_formato_da_brasilapi(pasta_dados, monkeypatch):
    c = carregar_mock(pasta_dados, monkeypatch)
    ativo = c.get(f"/api/cnpj/v1/{SACADO_GRANDE}")  # o back-end sempre consulta só com dígitos, como na BrasilAPI
    assert ativo.status_code == 200
    assert ativo.json() == {"cnpj": SACADO_GRANDE, "razao_social": "CLIENTE TESTE LTDA", "descricao_situacao_cadastral": "ATIVA"}
    assert c.get(f"/api/cnpj/v1/{SACADO_BAIXADO}").json()["descricao_situacao_cadastral"] == "BAIXADA"
    assert c.get(f"/api/cnpj/v1/{SACADO_SEM_CADASTRO}").status_code == 404


def test_mock_sem_arquivo_de_sobrescritas(pasta_dados, monkeypatch):
    (pasta_dados / "situacao_cadastral.json").unlink()
    c = carregar_mock(pasta_dados, monkeypatch)
    assert c.get(f"/api/cnpj/v1/{SACADO_BAIXADO}").status_code == 404
    assert json.loads(c.get(f"/api/cnpj/v1/{SACADO_GRANDE}").text)["descricao_situacao_cadastral"] == "ATIVA"
