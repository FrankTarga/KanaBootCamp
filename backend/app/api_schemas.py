"""Modelos Pydantic v2 fiéis ao contrato REST unificado (/api/v1)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

StatusNota = Literal["APROVADA", "RECUSADA"]
Severidade = Literal["OK", "REGRA_NEGOCIO", "DUPLICIDADE", "FRAUDE"]


# ---------------------------------------------------------------------------
# validadores_antecipe.json
# ---------------------------------------------------------------------------

class FundoConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    nome: str = Field(min_length=1)
    cnpj: str = ""


class ValidadorConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    codigo: str = Field(min_length=1)
    ativo: bool
    parametros: dict[str, Any] = Field(default_factory=dict)


class PrecificacaoConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    metodo: str = "DESCONTO_SIMPLES"
    taxa_mensal_percentual: float | None = None
    base_dias: int = 30


class ValidadoresConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    fundo: FundoConfig
    validadores: list[ValidadorConfig]
    precificacao: PrecificacaoConfig | None = None

    def para_json(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude_unset=True)


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: Literal["ready", "loading"]
    data_base_padrao: str
    estoque_total_linhas: int
    estoque_antecipe_linhas: int
    patrimonio_antecipe_fidc: float
    fundos_monitorados: int
    regras_ativas_count: int
    tempo_carga_estoque_ms: float
    versao_config: int


# ---------------------------------------------------------------------------
# POST /batches/validate
# ---------------------------------------------------------------------------

class ErroNota(BaseModel):
    codigo: str
    titulo_amigavel: str
    mensagem_empresa: str
    acao_recomendada: str


class ItemLote(BaseModel):
    linha_csv: int
    ordem_avaliacao: int
    hash_titulo: str
    nu_documento: str
    nome_cedente: str
    doc_cedente: str
    nome_sacado: str
    doc_sacado: str
    tipo_recebivel: str
    valor_nominal: float
    data_vencimento: str
    data_aquisicao: str
    prazo_dias: int
    desagio_reais: float
    valor_liquido: float
    status: StatusNota
    severidade: Severidade
    salva_pelo_otimizador: bool
    erros: list[ErroNota]


class ContagemMotivo(BaseModel):
    codigo: str
    titulo_amigavel: str
    quantidade: int
    valor_impactado: float


class ResumoLote(BaseModel):
    total_notas: int
    qtd_aprovadas: int
    qtd_recusadas: int
    qtd_alertas_fraude: int
    valor_bruto_total: float
    valor_bruto_aprovado: float
    valor_bruto_recusado: float
    desagio_total: float
    valor_liquido_receber: float
    prazo_medio_ponderado_dias: float
    contagem_por_motivo: list[ContagemMotivo]


class MetaLote(BaseModel):
    batch_hash_idempotencia: str
    tempo_processamento_ms: float
    data_base_utilizada: str
    taxa_mensal_aplicada: float
    otimizador_ativo: bool
    valor_liquido_sem_otimizador: float
    ganho_otimizador_reais: float
    qtd_notas_salvas_otimizador: int


class BatchValidationResponse(BaseModel):
    meta: MetaLote
    resumo: ResumoLote
    itens: list[ItemLote]


# ---------------------------------------------------------------------------
# Erros (formato único para toda a API)
# ---------------------------------------------------------------------------

class ErroApiCorpo(BaseModel):
    code: str
    message: str
    details: list[Any] = Field(default_factory=list)


class ErroApi(BaseModel):
    error: ErroApiCorpo
