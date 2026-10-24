"""mock-receita/: formato da BrasilAPI e as 3 fontes de situação (SITUACAO_FONTE)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from .conftest import SACADO_BAIXADO, SACADO_GRANDE, SACADO_LIVRE, SACADO_SEM_CADASTRO

MOCK = Path(__file__).resolve().parents[2] / "mock-receita" / "main.py"


def carregar_mock(pasta_dados, monkeypatch, fonte: str | None = None):
    monkeypatch.setenv("DATA_DIR", str(pasta_dados))
    if fonte is None:
        monkeypatch.delenv("SITUACAO_FONTE", raising=False)
    else:
        monkeypatch.setenv("SITUACAO_FONTE", fonte)
    spec = importlib.util.spec_from_file_location("mock_receita_main", MOCK)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return TestClient(modulo.app)


def situacao(c, doc):
    r = c.get(f"/api/cnpj/v1/{doc}")
    return r.json()["descricao_situacao_cadastral"] if r.status_code == 200 else r.status_code


def test_fonte_padrao_gabarito_no_formato_da_brasilapi(pasta_dados, monkeypatch):
    c = carregar_mock(pasta_dados, monkeypatch)
    ativo = c.get(f"/api/cnpj/v1/{SACADO_GRANDE}")  # o back-end sempre consulta só com dígitos, como na BrasilAPI
    assert ativo.json() == {"cnpj": SACADO_GRANDE, "razao_social": "CLIENTE TESTE LTDA", "descricao_situacao_cadastral": "ATIVA"}
    assert situacao(c, SACADO_BAIXADO) == "BAIXADA"  # vem do situacao_cadastral.json
    assert situacao(c, SACADO_SEM_CADASTRO) == "ATIVA"  # válido, fora do estoque: existe e está ATIVA
    assert situacao(c, "12345678000100") == 404  # DV inválido: não existe
    assert c.get("/health").json() == {"status": "ready", "fonte": "gabarito", "cnpjs_nao_ativos": 1}


def test_fonte_kanastra_usa_o_csv_oficial_e_ausente_e_ativa(pasta_dados, monkeypatch):
    (pasta_dados / "cnpj_situacao_mock.csv").write_text(
        f"DOC;SITUACAO_CADASTRAL\n{SACADO_LIVRE[:2]}.{SACADO_LIVRE[2:5]}.{SACADO_LIVRE[5:8]}/{SACADO_LIVRE[8:12]}-{SACADO_LIVRE[12:]};INAPTA\n"
        f"{SACADO_GRANDE};ativa\n", encoding="utf-8")
    c = carregar_mock(pasta_dados, monkeypatch, "kanastra")
    assert situacao(c, SACADO_LIVRE) == "INAPTA"
    assert situacao(c, SACADO_GRANDE) == "ATIVA"
    assert situacao(c, SACADO_BAIXADO) == "ATIVA"  # só o gabarito o marcava; ausente do CSV = ATIVA
    assert c.get("/health").json()["fonte"] == "kanastra"


def test_fonte_formato_nao_restringe_ninguem(pasta_dados, monkeypatch):
    c = carregar_mock(pasta_dados, monkeypatch, "formato")
    assert situacao(c, SACADO_BAIXADO) == "ATIVA"
    assert situacao(c, "12345678000100") == 404  # o formato continua valendo
    assert c.get("/health").json()["cnpjs_nao_ativos"] == 0


def test_fonte_invalida_ou_arquivo_faltando_falha_no_boot(pasta_dados, monkeypatch):
    with pytest.raises(ValueError, match="SITUACAO_FONTE 'receita' inválida"):
        carregar_mock(pasta_dados, monkeypatch, "receita")
    (pasta_dados / "situacao_cadastral.json").unlink()
    with pytest.raises(FileNotFoundError):  # sem arquivo, não sobe aprovando todo mundo em silêncio
        carregar_mock(pasta_dados, monkeypatch, "gabarito")
