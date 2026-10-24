"""Conformidade com o gabarito oficial: as 100.554 linhas do estoque_antecipe.csv no modo carteira.

A situação cadastral usada no gabarito vem de uma tabela da organização que não foi publicada no kit:
os CNPJs do dataset são sintéticos e a Receita real (BrasilAPI) dá outra situação para eles. Por isso a
situação aqui é "todos ATIVA" e as demais regras são cobradas linha a linha; a igualdade total fica como
pendência conhecida até a fonte oficial chegar.
"""

from __future__ import annotations

import collections
import csv
import json
from pathlib import Path

import pytest

from app.rule_engine import CadastroSituacao, RuleEngine, carregar_config, normalizar_documento
from app.stock_index import carregar_estoque

RAIZ = Path(__file__).resolve().parents[2]
DADOS = RAIZ / "backend" / "data"
GABARITO = RAIZ / "resultado_esperado_100k.json"
SITUACAO = "SITUACAO_CADASTRAL_SACADO"


@pytest.fixture(scope="module")
def gabarito() -> list[dict]:
    if not GABARITO.exists():
        pytest.skip("resultado_esperado_100k.json não está na raiz do repositório")
    return json.loads(GABARITO.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def resultado(gabarito, tmp_path_factory) -> list[dict]:
    estoque = csv.DictReader(open(DADOS / "estoque_antecipe.csv", encoding="utf-8"), delimiter=";")
    arquivo = tmp_path_factory.mktemp("cadastro") / "situacao.json"
    arquivo.write_text(json.dumps({"situacoes": {normalizar_documento(r["DOC_SACADO"]): "ATIVA" for r in estoque}}),
                       encoding="utf-8")
    config = carregar_config(DADOS / "validadores_antecipe.json")
    index = carregar_estoque(DADOS / "estoque_antecipe.csv", config.fundo.nome, config.fundo.cnpj)
    engine = RuleEngine(index, config, DADOS / "validadores_antecipe.json", CadastroSituacao(arquivo))
    return engine.validar_carteira((DADOS / "estoque_antecipe.csv").read_bytes())


def _sem_situacao(item: dict) -> list[str]:
    return [c for c in item.get("barrado_por", []) if c != SITUACAO]


def test_todas_as_regras_do_kit_batem_linha_a_linha(gabarito, resultado):
    assert len(resultado) == len(gabarito) == 100_554
    assert [(r["linha"], r["id"]) for r in resultado] == [(g["linha"], g["id"]) for g in gabarito]
    divergentes = [(n, e) for n, e in zip(resultado, gabarito) if _sem_situacao(n) != _sem_situacao(e)]
    assert not divergentes, f"{len(divergentes)} linhas divergentes, ex.: {divergentes[:3]}"


def test_divergencias_restantes_sao_so_de_situacao_cadastral(gabarito, resultado):
    sobras = collections.Counter(
        tuple(sorted(set(e.get("barrado_por", [])) ^ set(n.get("barrado_por", []))))
        for n, e in zip(resultado, gabarito) if n != e
    )
    assert set(sobras) == {(SITUACAO,)}
    assert sum(sobras.values()) == 2_317  # as linhas dos 87 CNPJs que o gabarito marca como irregulares


@pytest.mark.xfail(strict=True, reason="falta a fonte oficial de situação cadastral usada no gabarito")
def test_igualdade_total_com_o_gabarito(gabarito, resultado):
    assert resultado == gabarito
