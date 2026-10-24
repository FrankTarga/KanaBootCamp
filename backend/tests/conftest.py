from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.api_schemas import ValidadoresConfig  # noqa: E402
from app.rule_engine import CadastroSituacao, RuleEngine, carregar_config  # noqa: E402
from app.stock_index import carregar_estoque  # noqa: E402

CABECALHO = (
    "NOME_FUNDO;DOC_FUNDO;NOME_CEDENTE;DOC_CEDENTE;NOME_SACADO;DOC_SACADO;NU_DOCUMENTO;"
    "TIPO_RECEBIVEL;VALOR_NOMINAL;DATA_VENCIMENTO_ORIGINAL;DATA_AQUISICAO"
)
FUNDO = "ANTECIPE FIDC;92.234.400/0001-80"
OUTRO_FUNDO = "MARÉ ALTA DUPLICATAS FIDC;38.977.622/0001-47"


def gerar_cnpj(base12: str) -> str:
    """Completa 12 dígitos com os 2 dígitos verificadores corretos."""
    pesos = ((5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2), (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2))
    doc = base12
    for p in pesos:
        resto = sum(int(d) * w for d, w in zip(doc, p)) % 11
        doc += "0" if resto < 2 else str(11 - resto)
    return doc


CEDENTE = gerar_cnpj("761234560001")
SACADO_CONCENTRADO = gerar_cnpj("112223330001")  # 90.000 de exposição (9% da carteira)
SACADO_MESMA_RAIZ = gerar_cnpj("112223330002")  # mesmo grupo econômico, outra filial
SACADO_GRANDE = gerar_cnpj("445556660001")  # 910.000 de exposição
SACADO_LIVRE = gerar_cnpj("778889990001")  # sem exposição
SACADO_OTIMIZADOR = gerar_cnpj("998887770001")  # sem exposição
SACADO_BAIXADO = gerar_cnpj("665554440001")
SACADO_SEM_CADASTRO = gerar_cnpj("123123120001")  # CNPJ válido que a Receita não conhece
SACADOS_ATIVOS = (SACADO_CONCENTRADO, SACADO_MESMA_RAIZ, SACADO_GRANDE, SACADO_LIVRE, SACADO_OTIMIZADOR)

# Títulos de estoque reutilizados pelos testes de duplicidade/fraude
TITULO_ANTECIPE = (SACADO_GRANDE, "000777", "1500,00", "10/11/2026")
TITULO_OUTRO_FUNDO = (SACADO_LIVRE, "NF-888", "2500,00", "12/11/2026")


def linha_csv(sacado: str, nu: str, valor: str, venc: str, tipo: str = "Duplicata",
              cedente: str = CEDENTE, nome_sacado: str = "CLIENTE TESTE LTDA", fundo: str = FUNDO,
              aquisicao: str = "22/10/2026") -> str:
    return f"{fundo};EMPRESA TESTE LTDA;{cedente};{nome_sacado};{sacado};{nu};{tipo};{valor};{venc};{aquisicao}"


def montar_csv(*linhas: str) -> bytes:
    return ("\n".join((CABECALHO,) + linhas) + "\n").encode("utf-8")


@pytest.fixture()
def pasta_dados(tmp_path: Path) -> Path:
    """Estoque sintético: patrimônio ANTECIPE = 1.000.000,00; maior aquisição = quarta 21/10/2026."""
    estoque = montar_csv(
        linha_csv(SACADO_CONCENTRADO, "1", "90000,00", "20/12/2026", aquisicao="20/10/2026"),
        linha_csv(SACADO_GRANDE, "2", "908500,00", "20/12/2026", aquisicao="21/10/2026"),
        linha_csv(*TITULO_ANTECIPE, aquisicao="15/09/2026"),
        linha_csv(*TITULO_OUTRO_FUNDO, fundo=OUTRO_FUNDO, aquisicao="01/10/2026"),
    )
    (tmp_path / "estoque_antecipe.csv").write_bytes(estoque)
    shutil.copy(BACKEND_DIR / "data" / "validadores_antecipe.json", tmp_path / "validadores_antecipe.json")
    (tmp_path / "situacao_cadastral.json").write_text(
        json.dumps({"situacoes": {**{d: "ATIVA" for d in SACADOS_ATIVOS}, SACADO_BAIXADO: "BAIXADA"}}), encoding="utf-8"
    )
    return tmp_path


@pytest.fixture()
def engine(pasta_dados: Path) -> RuleEngine:
    config = carregar_config(pasta_dados / "validadores_antecipe.json")
    index = carregar_estoque(pasta_dados / "estoque_antecipe.csv", config.fundo.nome, config.fundo.cnpj)
    return RuleEngine(
        index, config, pasta_dados / "validadores_antecipe.json", CadastroSituacao(pasta_dados / "situacao_cadastral.json")
    )


def config_com(engine: RuleEngine, codigo: str, *, ativo: bool | None = None, **parametros) -> ValidadoresConfig:
    """Cópia da configuração atual alterando um validador (what-if)."""
    dados = engine.config.para_json()
    for validador in dados["validadores"]:
        if validador["codigo"] == codigo:
            if ativo is not None:
                validador["ativo"] = ativo
            validador["parametros"].update(parametros)
    return ValidadoresConfig.model_validate(dados)
