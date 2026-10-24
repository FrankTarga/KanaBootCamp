"""Motor de regras Zero-Deploy do ANTECIPE FIDC.

- Configuração em memória, trocada de forma atômica e persistida em validadores_antecipe.json.
- Avaliação exaustiva (sem short-circuit) de todos os validadores ativos.
- Shadow Ledger: exposições de sacado/cedente/patrimônio atualizadas a cada nota aprovada no lote.
- Triplo radar de duplicidade (lote, fundo, outros fundos) pela chave canônica SHA-256.
- Smart Batch Optimizer: simula ordens candidatas e devolve a de maior valor líquido.
- Tradutor de economês: cada recusa vira mensagem clara e ação recomendada para a empresa.
"""

from __future__ import annotations

import csv
import hashlib
import json
import logging
import math
import os
import tempfile
import threading
import time
import unicodedata
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable

from .api_schemas import (
    BatchValidationResponse,
    ContagemMotivo,
    ErroNota,
    ItemLote,
    MetaLote,
    PrecificacaoConfig,
    ResumoLote,
    ValidadoresConfig,
)
from .quant_analytics import (
    METODOS_PRECIFICACAO,
    ItemOtimizacao,
    RestricaoConcentracao,
    calcular_prazo_dias,
    formatar_brl,
    formatar_data_br,
    formatar_percentual,
    gerar_ordens_candidatas,
    parse_data_br,
    parse_valor_br,
    precificar,
)
from .stock_index import (
    AGRUPAMENTO_DOCUMENTO,
    AGRUPAMENTO_RAIZ,
    StockIndex,
    agrupar_documento,
    decodificar_csv,
    detectar_delimitador,
    gerar_hash_titulo,
    normalizar_documento,
)

logger = logging.getLogger("antecipe.rule_engine")

SEV_OK = "OK"
SEV_REGRA = "REGRA_NEGOCIO"
SEV_DUPLICIDADE = "DUPLICIDADE"
SEV_FRAUDE = "FRAUDE"
_RANK_SEVERIDADE = {SEV_OK: 0, SEV_REGRA: 1, SEV_DUPLICIDADE: 2, SEV_FRAUDE: 3}

TAXA_MENSAL_PADRAO = 0.025
SITUACAO_SE_AUSENTE = "ATIVA"

CODIGO_FORMATO = "FORMATO_INVALIDO"
TITULO_FORMATO = "Dados da nota incompletos ou inválidos"

COLUNAS_LOTE = (
    "NOME_FUNDO",
    "DOC_FUNDO",
    "NOME_CEDENTE",
    "DOC_CEDENTE",
    "NOME_SACADO",
    "DOC_SACADO",
    "NU_DOCUMENTO",
    "TIPO_RECEBIVEL",
    "VALOR_NOMINAL",
    "DATA_VENCIMENTO_ORIGINAL",
    "DATA_AQUISICAO",
)
COLUNAS_OBRIGATORIAS_LOTE = (
    "DOC_CEDENTE",
    "DOC_SACADO",
    "NU_DOCUMENTO",
    "TIPO_RECEBIVEL",
    "VALOR_NOMINAL",
    "DATA_VENCIMENTO_ORIGINAL",
)
_ALIASES_COLUNA = {
    "DATA_VENCIMENTO": "DATA_VENCIMENTO_ORIGINAL",
    "VENCIMENTO": "DATA_VENCIMENTO_ORIGINAL",
    "VALOR": "VALOR_NOMINAL",
    "NUMERO_DOCUMENTO": "NU_DOCUMENTO",
    "TIPO": "TIPO_RECEBIVEL",
}
_ALIASES_AGRUPAMENTO = {
    "RAIZ_CNPJ": AGRUPAMENTO_RAIZ,
    "RAIZ": AGRUPAMENTO_RAIZ,
    "CNPJ": AGRUPAMENTO_DOCUMENTO,
    "CNPJ_COMPLETO": AGRUPAMENTO_DOCUMENTO,
    "DOCUMENTO": AGRUPAMENTO_DOCUMENTO,
}


class ErroArquivoLote(ValueError):
    """CSV de upload ilegível; a mensagem pode ser exibida ao usuário."""


class ErroConfiguracao(ValueError):
    def __init__(self, erros: list[str]):
        super().__init__("; ".join(erros))
        self.erros = erros


# ---------------------------------------------------------------------------
# Estruturas
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ErroValidacao:
    codigo: str
    titulo_amigavel: str
    mensagem_empresa: str
    acao_recomendada: str
    severidade: str
    ordem: int  # posição do validador no JSON, para ordenar a lista de erros


@dataclass
class LinhaLote:
    linha_csv: int
    nome_cedente: str
    doc_cedente: str
    doc_cedente_original: str
    nome_sacado: str
    doc_sacado: str
    doc_sacado_original: str
    nu_documento: str
    tipo_recebivel: str
    valor_nominal: float
    valor_ok: bool
    data_vencimento: date | None
    data_vencimento_texto: str
    hash_titulo: str
    prazo_dias: int
    desagio_reais: float
    valor_liquido: float
    problemas_formato: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ContextoValidacao:
    data_base: date
    index: StockIndex
    situacoes: dict[str, str]
    nome_fundo: str


class ShadowLedger:
    """Overlay leve sobre as exposições do estoque: base somente leitura + deltas do lote."""

    _CHAVES = tuple(
        (dimensao, agrupamento)
        for dimensao in ("sacado", "cedente")
        for agrupamento in (AGRUPAMENTO_RAIZ, AGRUPAMENTO_DOCUMENTO)
    )

    def __init__(self, index: StockIndex):
        self._index = index
        self._delta: dict[tuple[str, str], dict[str, float]] = {chave: {} for chave in self._CHAVES}
        self.patrimonio_delta = 0.0
        self.hashes_vistos: dict[str, int] = {}  # hash -> linha da primeira ocorrência no lote

    @property
    def patrimonio(self) -> float:
        return self._index.patrimonio_antecipe + self.patrimonio_delta

    def exposicao(self, dimensao: str, agrupamento: str, grupo: str) -> float:
        base = self._index.mapa_exposicao(dimensao, agrupamento).get(grupo, 0.0)
        return base + self._delta[(dimensao, agrupamento)].get(grupo, 0.0)

    def registrar_visto(self, linha: LinhaLote) -> None:
        self.hashes_vistos.setdefault(linha.hash_titulo, linha.linha_csv)

    def registrar_aprovacao(self, linha: LinhaLote) -> None:
        valor = linha.valor_nominal
        for dimensao, agrupamento in self._CHAVES:
            doc = linha.doc_sacado if dimensao == "sacado" else linha.doc_cedente
            grupo = agrupar_documento(doc, agrupamento)
            delta = self._delta[(dimensao, agrupamento)]
            delta[grupo] = delta.get(grupo, 0.0) + valor
        self.patrimonio_delta += valor


@dataclass
class ResultadoSimulacao:
    ordem: list[int]
    erros: list[list[ErroValidacao]]
    aprovadas: set[int]
    valor_liquido: float


# ---------------------------------------------------------------------------
# Situação cadastral (arquivo local, recarregado quando muda: zero-deploy)
# ---------------------------------------------------------------------------

class CadastroSituacao:
    def __init__(self, caminho: Path | None):
        self._caminho = Path(caminho) if caminho else None
        self._assinatura: tuple[int, int] | None = None
        self._situacoes: dict[str, str] = {}
        self._lock = threading.Lock()
        self._recarregar_se_mudou()

    @property
    def versao(self) -> tuple[int, int] | None:
        self._recarregar_se_mudou()
        return self._assinatura

    def snapshot(self) -> dict[str, str]:
        self._recarregar_se_mudou()
        return self._situacoes

    def _recarregar_se_mudou(self) -> None:
        if self._caminho is None:
            return
        try:
            st = self._caminho.stat()
            assinatura: tuple[int, int] | None = (st.st_mtime_ns, st.st_size)
        except FileNotFoundError:
            assinatura = None
        if assinatura == self._assinatura:
            return
        with self._lock:
            situacoes: dict[str, str] = {}
            if assinatura is not None:
                try:
                    dados = json.loads(self._caminho.read_text(encoding="utf-8-sig"))
                except (OSError, json.JSONDecodeError) as exc:
                    logger.warning("situacao_cadastral ilegível, mantendo versão anterior: %s", exc)
                    return
                bruto = dados.get("situacoes", {}) if isinstance(dados, dict) else {}
                for doc, situacao in (bruto.items() if isinstance(bruto, dict) else []):
                    doc_limpo = normalizar_documento(doc)
                    if doc_limpo:
                        situacoes[doc_limpo] = str(situacao).strip().upper()
            self._situacoes = situacoes
            self._assinatura = assinatura


# ---------------------------------------------------------------------------
# Documentos (CNPJ numérico/alfanumérico e CPF)
# ---------------------------------------------------------------------------

_PESOS_CNPJ = ((5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2), (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2))


def cnpj_valido(doc: str) -> bool:
    if len(doc) != 14 or not doc[12:].isdigit() or not doc[:12].isalnum() or len(set(doc)) == 1:
        return False
    base = doc[:12]
    for pesos in _PESOS_CNPJ:
        resto = sum((ord(ch) - 48) * peso for ch, peso in zip(base, pesos)) % 11
        base += "0" if resto < 2 else str(11 - resto)
    return base[12:] == doc[12:]


def cpf_valido(doc: str) -> bool:
    if len(doc) != 11 or not doc.isdigit() or len(set(doc)) == 1:
        return False
    for n in (9, 10):
        soma = sum(int(doc[i]) * (n + 1 - i) for i in range(n))
        if (soma * 10) % 11 % 10 != int(doc[n]):
            return False
    return True


def diagnosticar_documento(doc: str) -> str | None:
    """None se o documento é válido; senão, o motivo em linguagem simples."""
    if not doc:
        return "o campo está vazio"
    if len(doc) == 14:
        if len(set(doc)) == 1:
            return "todos os dígitos são iguais"
        return None if cnpj_valido(doc) else "os dígitos verificadores do CNPJ não conferem"
    if len(doc) == 11:
        if len(set(doc)) == 1:
            return "todos os dígitos são iguais"
        return None if cpf_valido(doc) else "os dígitos verificadores do CPF não conferem"
    return f"ele tem {len(doc)} caracteres, mas um CNPJ tem 14 e um CPF tem 11"


def formatar_documento(doc: str) -> str:
    if len(doc) == 14:
        return f"{doc[:2]}.{doc[2:5]}.{doc[5:8]}/{doc[8:12]}-{doc[12:]}"
    if len(doc) == 11:
        return f"{doc[:3]}.{doc[3:6]}.{doc[6:9]}-{doc[9:]}"
    if len(doc) == 8:
        return f"{doc[:2]}.{doc[2:5]}.{doc[5:]}"
    return doc


# ---------------------------------------------------------------------------
# Helpers de texto do tradutor de economês
# ---------------------------------------------------------------------------

def _normalizar_texto(texto: str) -> str:
    sem_acento = "".join(
        ch for ch in unicodedata.normalize("NFKD", str(texto)) if not unicodedata.combining(ch)
    )
    return " ".join(sem_acento.casefold().split())


def _lista_humana(itens: list[str], conjuncao: str = "e") -> str:
    itens = [str(i) for i in itens]
    if len(itens) <= 1:
        return "".join(itens)
    return f"{', '.join(itens[:-1])} {conjuncao} {itens[-1]}"


def _dias(n: int) -> str:
    return f"{n} dia" if abs(n) == 1 else f"{n} dias"


def _cliente(linha: LinhaLote) -> str:
    nome = linha.nome_sacado.strip()
    doc = formatar_documento(linha.doc_sacado) or "sem documento"
    return f"{nome} ({doc})" if nome else doc


def _descricao_nota(linha: LinhaLote) -> str:
    nome = linha.nome_sacado.strip() or formatar_documento(linha.doc_sacado)
    return (
        f"nº {linha.nu_documento or '(sem número)'}, cliente {nome}, "
        f"{formatar_brl(linha.valor_nominal)}, vencimento {linha.data_vencimento_texto}"
    )


def _agrupamento(params: dict[str, Any]) -> str:
    return _ALIASES_AGRUPAMENTO.get(str(params.get("agrupamento") or "CNPJ").strip().upper(), AGRUPAMENTO_DOCUMENTO)


# ---------------------------------------------------------------------------
# Handlers: (linha, parametros, contexto, ledger|None) -> (mensagem, ação) | None
# ---------------------------------------------------------------------------

Resultado = tuple[str, str] | None


def _r_cnpj_sacado(linha: LinhaLote, params: dict, ctx: ContextoValidacao, ledger: ShadowLedger | None) -> Resultado:
    motivo = diagnosticar_documento(linha.doc_sacado)
    if motivo is None:
        return None
    doc = linha.doc_sacado_original.strip() or "vazio"
    nome = linha.nome_sacado.strip()
    quem = f"{nome} ({doc})" if nome else f"({doc})"
    return (
        f"O documento do cliente {quem} não é um CNPJ ou CPF válido: {motivo}.",
        "Confira o CNPJ do cliente na nota fiscal ou no cadastro e reenvie esta nota com o documento correto.",
    )


def _r_cnpj_cedente(linha: LinhaLote, params: dict, ctx: ContextoValidacao, ledger: ShadowLedger | None) -> Resultado:
    motivo = diagnosticar_documento(linha.doc_cedente)
    if motivo is None:
        return None
    doc = linha.doc_cedente_original.strip() or "vazio"
    return (
        f"O CNPJ da sua empresa informado nesta nota ({doc}) não é válido: {motivo}.",
        "Corrija o CNPJ da sua empresa na coluna DOC_CEDENTE da planilha e envie o arquivo de novo.",
    )


def _r_situacao_sacado(linha: LinhaLote, params: dict, ctx: ContextoValidacao, ledger: ShadowLedger | None) -> Resultado:
    if not linha.doc_sacado:
        return None
    situacao = ctx.situacoes.get(linha.doc_sacado, SITUACAO_SE_AUSENTE)
    aceitas = [str(s).strip().upper() for s in params.get("situacoes_aceitas", [])]
    if situacao in aceitas:
        return None
    return (
        f"O CNPJ do cliente {_cliente(linha)} aparece com situação cadastral \"{situacao}\" na Receita Federal. "
        f"O fundo só compra notas de clientes com situação {_lista_humana(aceitas, 'ou')}.",
        "Peça ao cliente para regularizar o CNPJ na Receita Federal. Enquanto isso, antecipe notas de outros clientes.",
    )


def _r_tipo_recebivel(linha: LinhaLote, params: dict, ctx: ContextoValidacao, ledger: ShadowLedger | None) -> Resultado:
    tipo = linha.tipo_recebivel.strip()
    tipo_norm = _normalizar_texto(tipo)
    aceitos = list(params.get("tipos_aceitos") or [])
    bloqueados = list(params.get("tipos_bloqueados") or [])
    acao = (
        f"Envie apenas recebíveis dos tipos aceitos ({_lista_humana(aceitos)}). "
        "Se esta venda gerou uma duplicata, corrija o tipo na planilha e reenvie."
        if aceitos
        else "Retire esta nota do lote e envie apenas recebíveis de outros tipos."
    )
    if bloqueados and tipo_norm in {_normalizar_texto(t) for t in bloqueados}:
        return (f"O fundo não compra títulos do tipo \"{tipo}\".", acao)
    if aceitos and tipo_norm not in {_normalizar_texto(t) for t in aceitos}:
        return (
            f"Esta nota é do tipo \"{tipo or 'não informado'}\", mas o fundo só compra {_lista_humana(aceitos)}.",
            acao,
        )
    return None


def _r_valor_minimo(linha: LinhaLote, params: dict, ctx: ContextoValidacao, ledger: ShadowLedger | None) -> Resultado:
    minimo = float(params["valor_minimo"])
    if not linha.valor_ok or linha.valor_nominal >= minimo:
        return None
    return (
        f"Esta nota vale {formatar_brl(linha.valor_nominal)}, abaixo do valor mínimo de "
        f"{formatar_brl(minimo)} por título aceito pelo fundo.",
        f"Envie apenas notas de {formatar_brl(minimo)} ou mais. "
        "Notas menores podem ser recebidas do cliente normalmente no vencimento.",
    )


def _r_valor_maximo(linha: LinhaLote, params: dict, ctx: ContextoValidacao, ledger: ShadowLedger | None) -> Resultado:
    maximo = float(params["valor_maximo"])
    if not linha.valor_ok or linha.valor_nominal <= maximo:
        return None
    return (
        f"Esta nota vale {formatar_brl(linha.valor_nominal)}, acima do valor máximo de "
        f"{formatar_brl(maximo)} por título aceito pelo fundo.",
        "Fale com o gestor do fundo sobre uma análise especial para esta nota ou antecipe recebíveis de valor menor.",
    )


def _r_nao_vencida(linha: LinhaLote, params: dict, ctx: ContextoValidacao, ledger: ShadowLedger | None) -> Resultado:
    venc = linha.data_vencimento
    if venc is None or venc >= ctx.data_base:
        return None
    atraso = (ctx.data_base - venc).days
    return (
        f"Esta nota venceu em {formatar_data_br(venc)}, {_dias(atraso)} antes da data da operação "
        f"({formatar_data_br(ctx.data_base)}). O fundo só compra títulos que ainda vão vencer.",
        "Cobre esta nota diretamente do cliente. Se o pagamento foi renegociado, "
        "emita uma nova duplicata com o novo vencimento e envie de novo.",
    )


def _r_prazo_maximo(linha: LinhaLote, params: dict, ctx: ContextoValidacao, ledger: ShadowLedger | None) -> Resultado:
    maximo = int(params["prazo_maximo_dias"])
    venc = linha.data_vencimento
    if venc is None or linha.prazo_dias <= maximo:
        return None
    elegivel_em = venc - timedelta(days=maximo)
    return (
        f"Esta nota vence em {formatar_data_br(venc)}, daqui a {_dias(linha.prazo_dias)}. "
        f"O prazo máximo aceito pelo fundo é de {_dias(maximo)}.",
        f"Guarde esta nota e envie a partir de {formatar_data_br(elegivel_em)}, "
        f"quando faltarem {_dias(maximo)} ou menos para o vencimento.",
    )


def _r_prazo_minimo(linha: LinhaLote, params: dict, ctx: ContextoValidacao, ledger: ShadowLedger | None) -> Resultado:
    minimo = int(params["prazo_minimo_dias"])
    venc = linha.data_vencimento
    if venc is None or linha.prazo_dias < 0 or linha.prazo_dias >= minimo:
        return None
    return (
        f"Esta nota vence em {formatar_data_br(venc)}, daqui a {_dias(linha.prazo_dias)}. "
        f"O fundo só compra títulos com pelo menos {_dias(minimo)} até o vencimento.",
        "Antecipe notas com vencimento mais distante. Esta pode ser recebida do cliente normalmente no vencimento.",
    )


def _avaliador_concentracao(dimensao: str) -> Callable[..., Resultado]:
    def avaliar(linha: LinhaLote, params: dict, ctx: ContextoValidacao, ledger: ShadowLedger | None) -> Resultado:
        doc = linha.doc_sacado if dimensao == "sacado" else linha.doc_cedente
        if ledger is None or not doc or not linha.valor_ok or linha.valor_nominal <= 0:
            return None
        agrupamento = _agrupamento(params)
        grupo = agrupar_documento(doc, agrupamento)
        valor = linha.valor_nominal
        exposicao = ledger.exposicao(dimensao, agrupamento, grupo)
        patrimonio = ledger.patrimonio
        exposicao_nova = exposicao + valor
        patrimonio_novo = patrimonio + valor
        percentual_novo = exposicao_nova / patrimonio_novo * 100 if patrimonio_novo > 0 else 100.0
        alvo = "cliente" if dimensao == "sacado" else "empresa cedente"

        estouros: list[str] = []
        folgas: list[float] = []
        if params.get("percentual_maximo") is not None:
            pct = float(params["percentual_maximo"])
            p = pct / 100
            folgas.append(math.inf if p >= 1 else (p * patrimonio - exposicao) / (1 - p))
            if percentual_novo > pct + 1e-9:
                estouros.append(
                    f"o equivalente a {formatar_percentual(percentual_novo)} da carteira, acima do limite de "
                    f"{formatar_percentual(pct)} por {alvo} (hoje, {formatar_brl(p * patrimonio_novo)})"
                )
        if params.get("valor_maximo") is not None:
            teto = float(params["valor_maximo"])
            folgas.append(teto - exposicao)
            if exposicao_nova > teto + 1e-6:
                estouros.append(f"acima do limite máximo de {formatar_brl(teto)} por {alvo}")
        if not estouros:
            return None

        folga = max(0.0, min(folgas))
        nome = (linha.nome_sacado if dimensao == "sacado" else linha.nome_cedente).strip()
        if agrupamento == AGRUPAMENTO_RAIZ and len(doc) == 14:
            ident = f"grupo econômico de CNPJ raiz {formatar_documento(doc[:8])}"
        else:
            ident = formatar_documento(doc)
        descricao = f"{nome} ({ident})" if nome else ident
        if dimensao == "sacado":
            quem, onde = f"o cliente {descricao}", "em títulos na carteira do fundo"
        else:
            quem, onde = f"a sua empresa, {descricao},", "em títulos vendidos ao fundo"
        disponivel = (
            f" Espaço ainda disponível: {formatar_brl(folga)}."
            if folga >= 0.01
            else " Não há mais espaço disponível no momento."
        )
        mensagem = (
            f"Com esta nota de {formatar_brl(valor)}, {quem} passaria a somar {formatar_brl(exposicao_nova)} "
            f"{onde}, {'; e '.join(estouros)}.{disponivel}"
        )
        if dimensao == "sacado":
            acao = (
                f"Substitua esta nota por recebíveis de outros clientes ou envie notas deste cliente que somem "
                f"até {formatar_brl(folga)}. Outra opção é aguardar a liquidação dos títulos atuais dele."
                if folga >= 0.01
                else "Substitua esta nota por recebíveis de outros clientes ou aguarde a liquidação dos "
                "títulos atuais deste cliente para liberar limite."
            )
        else:
            acao = (
                f"Envie um lote menor, de até {formatar_brl(folga)} em notas, ou aguarde a liquidação dos "
                "títulos já antecipados para liberar limite."
                if folga >= 0.01
                else "Aguarde a liquidação dos títulos já antecipados pela sua empresa para liberar limite."
            )
        return mensagem, acao

    return avaliar


def _r_documento_bloqueado(linha: LinhaLote, params: dict, ctx: ContextoValidacao, ledger: ShadowLedger | None) -> Resultado:
    bloqueados = {normalizar_documento(d) for d in params.get("documentos_bloqueados", [])}
    for doc, papel in ((linha.doc_sacado, "do cliente"), (linha.doc_cedente, "da sua empresa")):
        if doc and (doc in bloqueados or (len(doc) == 14 and doc[:8] in bloqueados)):
            return (
                f"O documento {papel} ({formatar_documento(doc)}) está na lista de restrição do fundo.",
                "Fale com o gestor do fundo para entender a restrição. Enquanto isso, antecipe notas de outros clientes.",
            )
    return None


def _r_duplicidade_lote(linha: LinhaLote, params: dict, ctx: ContextoValidacao, ledger: ShadowLedger | None) -> Resultado:
    if ledger is None:
        return None
    primeira = ledger.hashes_vistos.get(linha.hash_titulo)
    if primeira is None:
        return None
    return (
        f"Esta nota ({_descricao_nota(linha)}) aparece mais de uma vez neste arquivo. "
        f"Ela já está sendo analisada na linha {primeira}.",
        f"Apague a linha {linha.linha_csv} da planilha e mantenha só a linha {primeira}.",
    )


def _r_duplicidade_fundo(linha: LinhaLote, params: dict, ctx: ContextoValidacao, ledger: ShadowLedger | None) -> Resultado:
    data_aquisicao = ctx.index.hashes_antecipe.get(linha.hash_titulo)
    if data_aquisicao is None:
        return None
    quando = f" em {data_aquisicao}" if data_aquisicao else ""
    return (
        f"O {ctx.nome_fundo} já comprou esta nota ({_descricao_nota(linha)}){quando}. "
        "Cada nota só pode ser antecipada uma vez.",
        "Retire esta nota do lote. Confira no seu controle financeiro quais notas já foram antecipadas "
        "para não enviá-las de novo.",
    )


def _r_fraude_outro_fundo(linha: LinhaLote, params: dict, ctx: ContextoValidacao, ledger: ShadowLedger | None) -> Resultado:
    fundo = ctx.index.hashes_outros_fundos.get(linha.hash_titulo)
    if fundo is None:
        return None
    return (
        f"Esta nota ({_descricao_nota(linha)}) já está registrada na carteira de outro fundo de investimento "
        f"({fundo}). Vender a mesma nota para dois fundos (dupla cessão) é proibido.",
        f"Retire esta nota do lote. Se a venda para {fundo} foi desfeita, envie ao gestor o termo de recompra "
        "ou de baixa emitido por esse fundo antes de reenviar a nota.",
    )


# ---------------------------------------------------------------------------
# Validação de parâmetros (schema semântico do PUT /validators)
# ---------------------------------------------------------------------------

def _validar_numero(
    params: dict,
    nome: str,
    *,
    obrigatorio: bool = True,
    minimo: float | None = None,
    maximo: float | None = None,
    minimo_exclusivo: bool = False,
    inteiro: bool = False,
) -> list[str]:
    if params.get(nome) is None:
        return [f"parâmetro '{nome}' é obrigatório"] if obrigatorio else []
    valor = params[nome]
    if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not math.isfinite(valor):
        return [f"parâmetro '{nome}' deve ser numérico"]
    if inteiro and float(valor) != int(valor):
        return [f"parâmetro '{nome}' deve ser um número inteiro"]
    if minimo is not None and (valor <= minimo if minimo_exclusivo else valor < minimo):
        return [f"parâmetro '{nome}' deve ser {'maior que' if minimo_exclusivo else 'no mínimo'} {minimo}"]
    if maximo is not None and valor > maximo:
        return [f"parâmetro '{nome}' deve ser no máximo {maximo}"]
    return []


def _validar_lista_texto(params: dict, nome: str, *, obrigatorio: bool = True) -> list[str]:
    valor = params.get(nome)
    if valor is None:
        return [f"parâmetro '{nome}' é obrigatório"] if obrigatorio else []
    if not isinstance(valor, list) or not valor or not all(isinstance(v, str) and v.strip() for v in valor):
        return [f"parâmetro '{nome}' deve ser uma lista não vazia de textos"]
    return []


def _sem_parametros(params: dict) -> list[str]:
    return []


def _params_tipo(params: dict) -> list[str]:
    erros = _validar_lista_texto(params, "tipos_aceitos", obrigatorio=False)
    erros += _validar_lista_texto(params, "tipos_bloqueados", obrigatorio=False)
    if not params.get("tipos_aceitos") and not params.get("tipos_bloqueados"):
        erros.append("informe 'tipos_aceitos' e/ou 'tipos_bloqueados'")
    return erros


def _params_concentracao(params: dict) -> list[str]:
    erros = _validar_numero(params, "percentual_maximo", obrigatorio=False, minimo=0, maximo=100, minimo_exclusivo=True)
    erros += _validar_numero(params, "valor_maximo", obrigatorio=False, minimo=0, minimo_exclusivo=True)
    if params.get("percentual_maximo") is None and params.get("valor_maximo") is None:
        erros.append("informe 'percentual_maximo' (%) e/ou 'valor_maximo' (R$)")
    agrupamento = params.get("agrupamento")
    if agrupamento is not None and str(agrupamento).strip().upper() not in _ALIASES_AGRUPAMENTO:
        erros.append(f"agrupamento '{agrupamento}' inválido; use RAIZ_CNPJ ou CNPJ")
    return erros


@dataclass(frozen=True)
class Regra:
    codigo: str
    titulo_amigavel: str
    severidade: str
    stateful: bool  # depende da ordem de avaliação (Shadow Ledger)
    avaliar: Callable[[LinhaLote, dict, ContextoValidacao, ShadowLedger | None], Resultado]
    validar_parametros: Callable[[dict], list[str]]
    sistema: bool = False  # integridade: roda mesmo sem constar no JSON (desligável com ativo=false)

    def erro(self, resultado: tuple[str, str], ordem: int) -> ErroValidacao:
        mensagem, acao = resultado
        return ErroValidacao(self.codigo, self.titulo_amigavel, mensagem, acao, self.severidade, ordem)


REGRAS: dict[str, Regra] = {
    regra.codigo: regra
    for regra in (
        Regra("CNPJ_SACADO_VALIDO", "Documento do cliente inválido", SEV_REGRA, False,
              _r_cnpj_sacado, _sem_parametros),
        Regra("CNPJ_CEDENTE_VALIDO", "CNPJ da sua empresa inválido", SEV_REGRA, False,
              _r_cnpj_cedente, _sem_parametros),
        Regra("SITUACAO_CADASTRAL_SACADO", "Cadastro do cliente irregular na Receita Federal", SEV_REGRA, False,
              _r_situacao_sacado, lambda p: _validar_lista_texto(p, "situacoes_aceitas")),
        Regra("TIPO_RECEBIVEL", "Tipo de título não aceito", SEV_REGRA, False,
              _r_tipo_recebivel, _params_tipo),
        Regra("VALOR_MINIMO", "Valor abaixo do mínimo aceito", SEV_REGRA, False,
              _r_valor_minimo, lambda p: _validar_numero(p, "valor_minimo", minimo=0)),
        Regra("VALOR_MAXIMO", "Valor acima do máximo por título", SEV_REGRA, False,
              _r_valor_maximo, lambda p: _validar_numero(p, "valor_maximo", minimo=0, minimo_exclusivo=True)),
        Regra("NAO_VENCIDA", "Nota já vencida", SEV_REGRA, False,
              _r_nao_vencida, _sem_parametros),
        Regra("PRAZO_MAXIMO", "Prazo de pagamento muito longo", SEV_REGRA, False,
              _r_prazo_maximo, lambda p: _validar_numero(p, "prazo_maximo_dias", minimo=0, inteiro=True)),
        Regra("PRAZO_MINIMO", "Prazo de pagamento muito curto", SEV_REGRA, False,
              _r_prazo_minimo, lambda p: _validar_numero(p, "prazo_minimo_dias", minimo=0, inteiro=True)),
        Regra("CONCENTRACAO_MAXIMA_SACADO", "Limite de crédito do cliente atingido", SEV_REGRA, True,
              _avaliador_concentracao("sacado"), _params_concentracao),
        Regra("CONCENTRACAO_MAXIMA_CEDENTE", "Limite de antecipação da sua empresa atingido", SEV_REGRA, True,
              _avaliador_concentracao("cedente"), _params_concentracao),
        Regra("DOCUMENTO_BLOQUEADO", "Cliente ou empresa com restrição no fundo", SEV_REGRA, False,
              _r_documento_bloqueado, lambda p: _validar_lista_texto(p, "documentos_bloqueados")),
        Regra("DUPLICIDADE_LOTE", "Nota repetida no arquivo", SEV_DUPLICIDADE, True,
              _r_duplicidade_lote, _sem_parametros, sistema=True),
        Regra("DUPLICIDADE_FUNDO", "Nota já antecipada anteriormente", SEV_DUPLICIDADE, False,
              _r_duplicidade_fundo, _sem_parametros, sistema=True),
        Regra("FRAUDE_OUTRO_FUNDO", "Nota já vendida para outro fundo", SEV_FRAUDE, False,
              _r_fraude_outro_fundo, _sem_parametros, sistema=True),
    )
}


def validar_config(config: ValidadoresConfig) -> list[str]:
    """Validação semântica do JSON de validadores; lista vazia = configuração aplicável."""
    erros: list[str] = []
    vistos: set[str] = set()
    ativos: dict[str, dict] = {}
    for i, validador in enumerate(config.validadores):
        codigo = validador.codigo.strip().upper()
        if codigo in vistos:
            erros.append(f"validadores[{i}]: código '{validador.codigo}' duplicado")
            continue
        vistos.add(codigo)
        regra = REGRAS.get(codigo)
        if regra is None:
            erros.append(
                f"validadores[{i}]: código '{validador.codigo}' não é suportado pelo motor "
                f"(suportados: {', '.join(sorted(REGRAS))})"
            )
            continue
        erros += [f"{validador.codigo}: {e}" for e in regra.validar_parametros(validador.parametros)]
        if validador.ativo:
            ativos[codigo] = validador.parametros
    if "PRAZO_MINIMO" in ativos and "PRAZO_MAXIMO" in ativos and not erros:
        if ativos["PRAZO_MINIMO"]["prazo_minimo_dias"] > ativos["PRAZO_MAXIMO"]["prazo_maximo_dias"]:
            erros.append("PRAZO_MINIMO: prazo_minimo_dias maior que prazo_maximo_dias recusaria todas as notas")
    precificacao = config.precificacao
    if precificacao is not None:
        if precificacao.metodo not in METODOS_PRECIFICACAO:
            erros.append(
                f"precificacao.metodo '{precificacao.metodo}' não suportado (use {', '.join(METODOS_PRECIFICACAO)})"
            )
        taxa = precificacao.taxa_mensal_percentual
        if taxa is not None and not (0 <= taxa < 100):
            erros.append("precificacao.taxa_mensal_percentual deve estar entre 0 e 100 (ex.: 2.0 = 2% a.m.)")
        if precificacao.base_dias <= 0:
            erros.append("precificacao.base_dias deve ser maior que zero")
    return erros


def carregar_config(caminho: Path) -> ValidadoresConfig:
    dados = json.loads(Path(caminho).read_text(encoding="utf-8-sig"))
    return ValidadoresConfig.model_validate(dados)


def salvar_config(caminho: Path, config: ValidadoresConfig) -> None:
    """Escrita atômica: arquivo temporário no mesmo diretório + os.replace."""
    caminho = Path(caminho)
    conteudo = json.dumps(config.para_json(), ensure_ascii=False, indent=2) + "\n"
    fd, temporario = tempfile.mkstemp(prefix=".validadores-", suffix=".json", dir=caminho.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as arquivo:
            arquivo.write(conteudo)
            arquivo.flush()
            os.fsync(arquivo.fileno())
        os.replace(temporario, caminho)
    except BaseException:
        Path(temporario).unlink(missing_ok=True)
        raise


# ---------------------------------------------------------------------------
# Leitura resiliente do CSV de upload
# ---------------------------------------------------------------------------

def _normalizar_coluna(nome: str) -> str:
    coluna = _normalizar_texto(nome.replace("﻿", "")).upper().replace(" ", "_").replace("-", "_")
    return _ALIASES_COLUNA.get(coluna, coluna)


def ler_lote_csv(conteudo: bytes) -> list[tuple[int, dict[str, str]]]:
    """Devolve (linha física no arquivo, registro) para cada nota. Cabeçalho = linha 1."""
    texto = decodificar_csv(conteudo)
    linhas = texto.splitlines()
    inicio = next((i for i, linha in enumerate(linhas) if linha.strip()), None)
    if inicio is None:
        raise ErroArquivoLote("O arquivo está vazio.")
    leitor = csv.reader(linhas[inicio:], delimiter=detectar_delimitador(linhas[inicio]))
    cabecalho = [_normalizar_coluna(c) for c in next(leitor)]
    faltando = [c for c in COLUNAS_OBRIGATORIAS_LOTE if c not in cabecalho]
    if faltando:
        raise ErroArquivoLote(
            f"O arquivo não tem as colunas obrigatórias: {', '.join(faltando)}. "
            f"Use o cabeçalho padrão separado por ponto e vírgula: {';'.join(COLUNAS_LOTE)}."
        )
    registros: list[tuple[int, dict[str, str]]] = []
    for campos in leitor:
        if not any(c.strip() for c in campos):
            continue
        registro = {coluna: "" for coluna in COLUNAS_LOTE}
        for coluna, valor in zip(cabecalho, campos):
            registro[coluna] = valor
        registros.append((inicio + leitor.line_num, registro))
    if not registros:
        raise ErroArquivoLote("O arquivo não tem nenhuma nota abaixo do cabeçalho.")
    return registros


def montar_linha(
    numero: int,
    registro: dict[str, str],
    data_base: date,
    taxa_mensal: float,
    precificacao: PrecificacaoConfig,
) -> LinhaLote:
    problemas: list[str] = []
    valor_texto = registro["VALOR_NOMINAL"].strip()
    try:
        valor, valor_ok = parse_valor_br(valor_texto), True
    except ValueError:
        valor, valor_ok = 0.0, False
        problemas.append(f"o valor \"{valor_texto}\" não é um número válido" if valor_texto else "o valor nominal está vazio")

    venc_texto = registro["DATA_VENCIMENTO_ORIGINAL"].strip()
    try:
        vencimento: date | None = parse_data_br(venc_texto)
    except ValueError:
        vencimento = None
        problemas.append(
            f"a data de vencimento \"{venc_texto}\" não é uma data válida (use dd/mm/aaaa)"
            if venc_texto
            else "a data de vencimento está vazia"
        )

    nu_documento = registro["NU_DOCUMENTO"].strip()
    if not nu_documento:
        problemas.append("o número da nota (NU_DOCUMENTO) está vazio")
    doc_cedente = normalizar_documento(registro["DOC_CEDENTE"])
    if not doc_cedente:
        problemas.append("o CNPJ da sua empresa (DOC_CEDENTE) está vazio")
    doc_sacado = normalizar_documento(registro["DOC_SACADO"])

    venc_normalizado = formatar_data_br(vencimento) if vencimento else venc_texto
    prazo = calcular_prazo_dias(vencimento, data_base) if vencimento else 0
    if valor_ok:
        preco = precificar(valor, prazo, taxa_mensal, precificacao.metodo, precificacao.base_dias)
        desagio, liquido = preco.desagio_reais, preco.valor_liquido
    else:
        desagio = liquido = 0.0

    return LinhaLote(
        linha_csv=numero,
        nome_cedente=registro["NOME_CEDENTE"].strip(),
        doc_cedente=doc_cedente,
        doc_cedente_original=registro["DOC_CEDENTE"],
        nome_sacado=registro["NOME_SACADO"].strip(),
        doc_sacado=doc_sacado,
        doc_sacado_original=registro["DOC_SACADO"],
        nu_documento=nu_documento,
        tipo_recebivel=registro["TIPO_RECEBIVEL"].strip(),
        valor_nominal=round(valor, 2),
        valor_ok=valor_ok,
        data_vencimento=vencimento,
        data_vencimento_texto=venc_normalizado,
        hash_titulo=gerar_hash_titulo(doc_cedente, doc_sacado, nu_documento, valor, venc_normalizado),
        prazo_dias=prazo,
        desagio_reais=desagio,
        valor_liquido=liquido,
        problemas_formato=problemas,
    )


# ---------------------------------------------------------------------------
# Motor
# ---------------------------------------------------------------------------

class RuleEngine:
    def __init__(self, index: StockIndex, config: ValidadoresConfig, caminho_config: Path, cadastro: CadastroSituacao):
        erros = validar_config(config)
        if erros:
            raise ErroConfiguracao(erros)
        self.index = index
        self._config = config
        self._caminho_config = Path(caminho_config)
        self._cadastro = cadastro
        self._lock = threading.Lock()
        self.versao_config = 1

    @property
    def config(self) -> ValidadoresConfig:
        return self._config

    def atualizar_config(self, nova: ValidadoresConfig) -> ValidadoresConfig:
        """Zero-Deploy: valida, persiste em disco e troca a configuração em memória."""
        erros = validar_config(nova)
        if erros:
            raise ErroConfiguracao(erros)
        with self._lock:
            salvar_config(self._caminho_config, nova)
            self._config = nova
            self.versao_config += 1
        logger.info("validadores atualizados: versao=%s ativos=%s", self.versao_config, self.regras_ativas_count())
        return nova

    def regras_ativas_count(self, config: ValidadoresConfig | None = None) -> int:
        return sum(1 for v in (config or self._config).validadores if v.ativo)

    def assinatura_estado(self) -> tuple[Any, ...]:
        return self.versao_config, self._cadastro.versao

    @staticmethod
    def taxa_configurada(config: ValidadoresConfig) -> float:
        precificacao = config.precificacao
        if precificacao is not None and precificacao.taxa_mensal_percentual is not None:
            return precificacao.taxa_mensal_percentual / 100
        return TAXA_MENSAL_PADRAO

    @staticmethod
    def _regras_em_uso(config: ValidadoresConfig) -> list[tuple[Regra, dict, int]]:
        em_uso: list[tuple[Regra, dict, int]] = []
        declarados: set[str] = set()
        for ordem, validador in enumerate(config.validadores):
            codigo = validador.codigo.strip().upper()
            declarados.add(codigo)
            regra = REGRAS.get(codigo)
            if regra is not None and validador.ativo:
                em_uso.append((regra, validador.parametros, ordem))
        for regra in REGRAS.values():
            if regra.sistema and regra.codigo not in declarados:
                em_uso.append((regra, {}, -1))
        return em_uso

    def _simular(
        self,
        linhas: list[LinhaLote],
        erros_estaticos: list[list[ErroValidacao]],
        ordem: list[int],
        regras_stateful: list[tuple[Regra, dict, int]],
        ctx: ContextoValidacao,
    ) -> ResultadoSimulacao:
        ledger = ShadowLedger(self.index)
        erros_por_linha: list[list[ErroValidacao]] = [[] for _ in linhas]
        aprovadas: set[int] = set()
        liquido = 0.0
        for pos in ordem:
            linha = linhas[pos]
            erros = list(erros_estaticos[pos])
            for regra, params, ordem_regra in regras_stateful:
                resultado = regra.avaliar(linha, params, ctx, ledger)
                if resultado:
                    erros.append(regra.erro(resultado, ordem_regra))
            ledger.registrar_visto(linha)
            if not erros:
                ledger.registrar_aprovacao(linha)
                aprovadas.add(pos)
                liquido += linha.valor_liquido
            erros_por_linha[pos] = erros
        return ResultadoSimulacao(ordem, erros_por_linha, aprovadas, round(liquido, 2))

    def _restricoes_otimizador(
        self, regras: list[tuple[Regra, dict, int]], linhas: list[LinhaLote]
    ) -> tuple[list[RestricaoConcentracao], str, str]:
        restricoes: list[RestricaoConcentracao] = []
        agrupamentos = {"sacado": AGRUPAMENTO_DOCUMENTO, "cedente": AGRUPAMENTO_DOCUMENTO}
        for regra, params, _ in regras:
            if not regra.codigo.startswith("CONCENTRACAO_MAXIMA_"):
                continue
            dimensao = "sacado" if regra.codigo.endswith("SACADO") else "cedente"
            agrupamento = _agrupamento(params)
            agrupamentos[dimensao] = agrupamento
            base = self.index.mapa_exposicao(dimensao, agrupamento)
            grupos = {
                agrupar_documento(l.doc_sacado if dimensao == "sacado" else l.doc_cedente, agrupamento) for l in linhas
            }
            restricoes.append(
                RestricaoConcentracao(
                    dimensao=dimensao,
                    percentual_maximo=params.get("percentual_maximo"),
                    valor_maximo=params.get("valor_maximo"),
                    patrimonio_inicial=self.index.patrimonio_antecipe,
                    exposicao_inicial={g: base.get(g, 0.0) for g in grupos},
                )
            )
        return restricoes, agrupamentos["sacado"], agrupamentos["cedente"]

    def validar_lote(
        self,
        conteudo: bytes,
        data_base: date | None = None,
        taxa_mensal: float | None = None,
        otimizar_lote: bool = True,
        config: ValidadoresConfig | None = None,
    ) -> BatchValidationResponse:
        inicio = time.perf_counter()
        cfg = config or self._config
        data_base = data_base or self.index.data_base_padrao
        taxa = taxa_mensal if taxa_mensal is not None else self.taxa_configurada(cfg)
        precificacao = cfg.precificacao or PrecificacaoConfig()

        linhas = [
            montar_linha(numero, registro, data_base, taxa, precificacao)
            for numero, registro in ler_lote_csv(conteudo)
        ]
        ctx = ContextoValidacao(data_base, self.index, self._cadastro.snapshot(), cfg.fundo.nome)
        regras = self._regras_em_uso(cfg)
        estaticas = [r for r in regras if not r[0].stateful]
        stateful = [r for r in regras if r[0].stateful]

        # Regras independentes da ordem: avaliadas uma única vez por nota.
        erros_estaticos: list[list[ErroValidacao]] = []
        for linha in linhas:
            erros: list[ErroValidacao] = []
            if linha.problemas_formato:
                erros.append(ErroValidacao(
                    CODIGO_FORMATO,
                    TITULO_FORMATO,
                    f"Não foi possível ler esta linha: {'; '.join(linha.problemas_formato)}.",
                    "Corrija esta linha na planilha (valores como 1.500,50 e datas como 22/10/2026) "
                    "e envie o arquivo de novo.",
                    SEV_REGRA,
                    -2,
                ))
            for regra, params, ordem_regra in estaticas:
                resultado = regra.avaliar(linha, params, ctx, None)
                if resultado:
                    erros.append(regra.erro(resultado, ordem_regra))
            erros_estaticos.append(erros)

        original = self._simular(linhas, erros_estaticos, list(range(len(linhas))), stateful, ctx)
        melhor = original
        if otimizar_lote and len(linhas) > 1:
            restricoes, agrup_sacado, agrup_cedente = self._restricoes_otimizador(regras, linhas)
            checa_lote = any(r.codigo == "DUPLICIDADE_LOTE" for r, _, _ in stateful)
            primeira: dict[str, int] = {}
            for pos, linha in enumerate(linhas):
                primeira.setdefault(linha.hash_titulo, pos)
            itens = [
                ItemOtimizacao(
                    idx=pos,
                    valor_nominal=linha.valor_nominal,
                    prazo_dias=linha.prazo_dias,
                    valor_liquido=linha.valor_liquido,
                    grupo_sacado=agrupar_documento(linha.doc_sacado, agrup_sacado),
                    grupo_cedente=agrupar_documento(linha.doc_cedente, agrup_cedente),
                    elegivel=not erros_estaticos[pos] and (not checa_lote or primeira[linha.hash_titulo] == pos),
                )
                for pos, linha in enumerate(linhas)
            ]
            for ordem in gerar_ordens_candidatas(itens, restricoes)[1:]:
                simulacao = self._simular(linhas, erros_estaticos, ordem, stateful, ctx)
                if simulacao.valor_liquido > melhor.valor_liquido + 0.005:
                    melhor = simulacao

        return self._montar_resposta(conteudo, linhas, original, melhor, data_base, taxa, otimizar_lote, inicio)

    def _montar_resposta(
        self,
        conteudo: bytes,
        linhas: list[LinhaLote],
        original: ResultadoSimulacao,
        melhor: ResultadoSimulacao,
        data_base: date,
        taxa: float,
        otimizar_lote: bool,
        inicio: float,
    ) -> BatchValidationResponse:
        posicao = {pos: i + 1 for i, pos in enumerate(melhor.ordem)}
        data_base_txt = formatar_data_br(data_base)
        motivos: dict[str, list[Any]] = {}
        itens: list[ItemLote] = []
        bruto_total = bruto_aprovado = desagio_total = liquido_total = prazo_x_valor = 0.0
        qtd_fraude = qtd_salvas = 0

        for pos, linha in enumerate(linhas):
            erros = sorted(melhor.erros[pos], key=lambda e: (-_RANK_SEVERIDADE[e.severidade], e.ordem))
            aprovada = pos in melhor.aprovadas
            salva = otimizar_lote and aprovada and pos not in original.aprovadas
            severidade = max((e.severidade for e in erros), key=lambda s: _RANK_SEVERIDADE[s], default=SEV_OK)
            bruto_total += linha.valor_nominal
            if aprovada:
                bruto_aprovado += linha.valor_nominal
                desagio_total += linha.desagio_reais
                liquido_total += linha.valor_liquido
                prazo_x_valor += linha.prazo_dias * linha.valor_nominal
            qtd_fraude += severidade == SEV_FRAUDE
            qtd_salvas += salva
            for erro in erros:
                motivo = motivos.setdefault(erro.codigo, [erro.titulo_amigavel, 0, 0.0])
                motivo[1] += 1
                motivo[2] += linha.valor_nominal
            itens.append(ItemLote(
                linha_csv=linha.linha_csv,
                ordem_avaliacao=posicao[pos],
                hash_titulo=linha.hash_titulo,
                nu_documento=linha.nu_documento,
                nome_cedente=linha.nome_cedente,
                doc_cedente=linha.doc_cedente,
                nome_sacado=linha.nome_sacado,
                doc_sacado=linha.doc_sacado,
                tipo_recebivel=linha.tipo_recebivel,
                valor_nominal=linha.valor_nominal,
                data_vencimento=linha.data_vencimento_texto,
                data_aquisicao=data_base_txt,
                prazo_dias=linha.prazo_dias,
                desagio_reais=linha.desagio_reais,
                valor_liquido=linha.valor_liquido,
                status="APROVADA" if aprovada else "RECUSADA",
                severidade=severidade,
                salva_pelo_otimizador=salva,
                erros=[
                    ErroNota(
                        codigo=e.codigo,
                        titulo_amigavel=e.titulo_amigavel,
                        mensagem_empresa=e.mensagem_empresa,
                        acao_recomendada=e.acao_recomendada,
                    )
                    for e in erros
                ],
            ))

        contagem = [
            ContagemMotivo(codigo=codigo, titulo_amigavel=dados[0], quantidade=dados[1], valor_impactado=round(dados[2], 2))
            for codigo, dados in sorted(motivos.items(), key=lambda kv: (-kv[1][1], -kv[1][2]))
        ]
        qtd_aprovadas = len(melhor.aprovadas)
        resumo = ResumoLote(
            total_notas=len(linhas),
            qtd_aprovadas=qtd_aprovadas,
            qtd_recusadas=len(linhas) - qtd_aprovadas,
            qtd_alertas_fraude=qtd_fraude,
            valor_bruto_total=round(bruto_total, 2),
            valor_bruto_aprovado=round(bruto_aprovado, 2),
            valor_bruto_recusado=round(bruto_total - bruto_aprovado, 2),
            desagio_total=round(desagio_total, 2),
            valor_liquido_receber=round(liquido_total, 2),
            prazo_medio_ponderado_dias=round(prazo_x_valor / bruto_aprovado, 2) if bruto_aprovado > 0 else 0.0,
            contagem_por_motivo=contagem,
        )
        meta = MetaLote(
            batch_hash_idempotencia=hashlib.sha256(conteudo).hexdigest(),
            tempo_processamento_ms=round((time.perf_counter() - inicio) * 1000, 2),
            data_base_utilizada=data_base_txt,
            taxa_mensal_aplicada=taxa,
            otimizador_ativo=otimizar_lote,
            valor_liquido_sem_otimizador=original.valor_liquido,
            ganho_otimizador_reais=round(max(0.0, melhor.valor_liquido - original.valor_liquido), 2),
            qtd_notas_salvas_otimizador=qtd_salvas,
        )
        return BatchValidationResponse(meta=meta, resumo=resumo, itens=itens)
