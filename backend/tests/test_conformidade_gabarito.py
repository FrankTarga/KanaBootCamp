"""Conformidade com o gabarito oficial: as 100.554 linhas do estoque_antecipe.csv no modo carteira.

A situação cadastral é a mesma que a aplicação usa em produção de demo: a base do mock-receita
(sacados do estoque como ATIVA + data/situacao_cadastral.json, gerado por gerar_situacao_cadastral.py).
"""

from __future__ import annotations

import collections
import importlib.util
import json
from pathlib import Path

import pytest

from app.rule_engine import CadastroSituacao, RuleEngine, carregar_config
from app.stock_index import carregar_estoque

RAIZ = Path(__file__).resolve().parents[2]
DADOS = RAIZ / "backend" / "data"
GABARITO = RAIZ / "resultado_esperado_100k.json"


@pytest.fixture(scope="module")
def gabarito() -> list[dict]:
    if not GABARITO.exists():
        pytest.skip("resultado_esperado_100k.json não está na raiz do repositório")
    return json.loads(GABARITO.read_text(encoding="utf-8"))


def _base_do_mock() -> dict[str, str]:
    spec = importlib.util.spec_from_file_location("mock_receita_conformidade", RAIZ / "mock-receita" / "main.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)  # DATA_DIR padrão do mock = backend/data
    return {doc: registro["descricao_situacao_cadastral"] for doc, registro in modulo.BASE.items()}


@pytest.fixture(scope="module")
def engine(gabarito, tmp_path_factory) -> RuleEngine:
    arquivo = tmp_path_factory.mktemp("cadastro") / "situacao.json"
    arquivo.write_text(json.dumps({"situacoes": _base_do_mock()}), encoding="utf-8")
    config = carregar_config(DADOS / "validadores_antecipe.json")
    index = carregar_estoque(DADOS / "estoque_antecipe.csv", config.fundo.nome, config.fundo.cnpj)
    return RuleEngine(index, config, DADOS / "validadores_antecipe.json", CadastroSituacao(arquivo))


@pytest.fixture(scope="module")
def resultado(engine) -> list[dict]:
    return engine.validar_carteira((DADOS / "estoque_antecipe.csv").read_bytes())


def test_tela_modo_carteira_bate_com_o_gabarito(engine, gabarito):
    """A resposta rica (a que a tela recebe em POST /batches/validate com modo=carteira) nas 100.554 linhas."""
    r = engine.validar_lote((DADOS / "estoque_antecipe.csv").read_bytes(), modo="carteira")
    obtido = [("APROVADO" if i.status == "APROVADA" else "BARRADO", sorted(e.codigo for e in i.erros)) for i in r.itens]
    esperado = [(g["status"], sorted(g.get("barrado_por", []))) for g in gabarito]
    assert obtido == esperado
    assert r.resumo.qtd_aprovadas == 85_215
    assert all(e.mensagem_empresa and e.acao_recomendada for i in r.itens for e in i.erros)
    # painel do Estatístico sobre o estoque inteiro (números de docs/analise-recusas.md)
    analise = r.analise_recusas
    assert (analise.qtd_recusadas, analise.qtd_com_mais_de_um_erro, analise.pct_com_mais_de_um_erro) == (15_339, 4_770, 31.1)
    prazo = next(m for m in analise.motivos if m.codigo == "PRAZO_MAXIMO")
    assert prazo.qtd_so_este_erro == 0 and prazo.liquido_liberado == 0  # prazo nunca aparece sozinho


def test_carteira_bate_100_por_cento_com_o_gabarito(gabarito, resultado):
    assert len(resultado) == len(gabarito) == 100_554
    divergentes = [(n, e) for n, e in zip(resultado, gabarito) if n != e]
    resumo = collections.Counter((tuple(n.get("barrado_por", [])), tuple(e.get("barrado_por", []))) for n, e in divergentes)
    assert not divergentes, f"{len(divergentes)} linhas divergentes; (nosso, esperado): {resumo.most_common(5)}"


def test_totais_por_regra(resultado):
    status = collections.Counter(item["status"] for item in resultado)
    regras = collections.Counter(c for item in resultado for c in item.get("barrado_por", []))
    assert status == {"APROVADO": 85_215, "BARRADO": 15_339}
    assert regras == {
        "TIPO_RECEBIVEL": 9_842,
        "PRAZO_MAXIMO": 4_671,
        "CONCENTRACAO_MAXIMA_SACADO": 3_305,
        "SITUACAO_CADASTRAL_SACADO": 2_317,
        "VALOR_MINIMO": 34,
    }


def test_gerador_de_situacao_cadastral(tmp_path, monkeypatch):
    import gerar_situacao_cadastral as gerador

    from .conftest import SACADO_BAIXADO, SACADO_LIVRE, linha_csv, montar_csv

    estoque, gab, destino = tmp_path / "e.csv", tmp_path / "g.json", tmp_path / "s.json"
    estoque.write_bytes(montar_csv(linha_csv(SACADO_LIVRE, "1", "1,00", "21/11/2026"),
                                   linha_csv(SACADO_BAIXADO, "2", "1,00", "21/11/2026")))
    gab.write_text(json.dumps([{"linha": 2, "id": "1", "status": "APROVADO"},
                               {"linha": 3, "id": "2", "status": "BARRADO", "barrado_por": ["SITUACAO_CADASTRAL_SACADO"]}]),
                   encoding="utf-8")
    monkeypatch.setattr(gerador, "ESTOQUE", estoque)
    monkeypatch.setattr(gerador, "GABARITO", gab)
    monkeypatch.setattr(gerador, "DESTINO", destino)
    gerador.main()
    assert json.loads(destino.read_text(encoding="utf-8"))["situacoes"] == {SACADO_BAIXADO: "IRREGULAR"}


def test_arquivo_versionado_esta_em_dia_com_o_gabarito(gabarito):
    situacoes = json.loads((DADOS / "situacao_cadastral.json").read_text(encoding="utf-8"))["situacoes"]
    assert len(situacoes) == 87 and set(situacoes.values()) == {"IRREGULAR"}
