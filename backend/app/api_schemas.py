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
    prazo_minimo_cobranca_dias: int = 0  # deságio cobra ao menos N dias, mesmo para prazo menor


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
    taxa_mensal_padrao: float  # decimal (0.02 = 2% a.m.); fonte única: precificacao do JSON
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


# Painel de recusas (contrato: docs/analise-recusas.md, dono: Estatístico). extra="allow": campo novo do
# Quant passa adiante em vez de sumir. O front mostra os números como vêm (percentuais já fecham 100%).

class _Painel(BaseModel):
    model_config = ConfigDict(extra="allow")


class GrupoUmProblema(_Painel):
    codigo: str
    titulo_amigavel: str
    corrigivel: bool
    qtd: int
    valor: float
    pct_das_recusadas: float
    liquido_liberado: float | None  # None = sem estimativa (ex.: nota vencida)


class CombinacaoProblemas(_Painel):
    codigos: list[str]
    titulos: list[str]
    qtd: int
    valor: float
    pct_do_grupo: float


class SubgrupoProblemas(_Painel):
    qtd_problemas: int
    qtd: int
    valor: float
    pct_do_grupo: float
    combinacoes: list[CombinacaoProblemas]


class GrupoMaisDeUmProblema(_Painel):
    qtd: int
    valor: float
    pct_das_recusadas: float
    subgrupos: list[SubgrupoProblemas]


class GruposRecusas(_Painel):
    um_problema: list[GrupoUmProblema]
    mais_de_um_problema: GrupoMaisDeUmProblema


class MotivoRecusa(_Painel):
    codigo: str
    titulo_amigavel: str
    corrigivel: bool
    qtd_notas: int
    valor_impactado: float
    qtd_so_este_erro: int
    liquido_liberado: float | None
    pct_das_recusadas: float


class AnaliseRecusas(_Painel):
    qtd_notas: int
    qtd_recusadas: int
    pct_recusadas: float
    valor_recusado: float
    qtd_com_mais_de_um_erro: int
    pct_com_mais_de_um_erro: float
    grupos: GruposRecusas
    motivos: list[MotivoRecusa]


class BatchValidationResponse(BaseModel):
    meta: MetaLote
    resumo: ResumoLote
    itens: list[ItemLote]
    analise_recusas: AnaliseRecusas


# ---------------------------------------------------------------------------
# GET /historico/* (SQLite, paginado)
# ---------------------------------------------------------------------------

class HistoricoLote(BaseModel):
    id: int
    criado_em: str  # ISO 8601 em UTC
    request_id: str
    chave_idempotencia: str
    batch_hash: str
    modo: str
    data_base: str
    taxa_mensal: float
    otimizar_lote: bool
    versao_config: int
    what_if: bool
    replay: bool
    total_notas: int
    qtd_aprovadas: int
    qtd_recusadas: int
    qtd_alertas_fraude: int
    valor_bruto_total: float
    valor_liquido_receber: float
    tempo_processamento_ms: float


class MudancaRegras(BaseModel):
    id: int
    criado_em: str
    request_id: str
    versao_config: int
    regras_ativas: int
    config: dict[str, Any]


class NotaHistorico(BaseModel):
    linha_csv: int
    nu_documento: str
    nome_cedente: str
    doc_cedente: str
    nome_sacado: str
    doc_sacado: str
    tipo_recebivel: str
    valor_nominal: float
    data_vencimento: str
    prazo_dias: int
    desagio_reais: float
    valor_liquido: float
    status: StatusNota
    severidade: Severidade
    salva_pelo_otimizador: bool
    erros: list[ErroNota]


class DetalheLoteHistorico(BaseModel):
    lote: HistoricoLote
    notas_de_lote_id: int  # repetição do cache aponta para o envio original
    notas_guardadas: bool  # False no modo carteira (só o resumo é guardado)
    total_notas_guardadas: int
    limite: int
    offset: int
    notas: list[NotaHistorico]


class OcorrenciaNota(BaseModel):
    lote_id: int
    criado_em: str
    modo: str
    what_if: bool
    batch_hash: str
    linha_csv: int
    nu_documento: str
    nome_cedente: str
    doc_cedente: str
    nome_sacado: str
    doc_sacado: str
    tipo_recebivel: str
    valor_nominal: float
    data_vencimento: str
    prazo_dias: int
    desagio_reais: float
    valor_liquido: float
    status: StatusNota
    severidade: Severidade
    salva_pelo_otimizador: bool
    codigos_erro: list[str]


class PaginaOcorrenciasNota(BaseModel):
    total: int
    limite: int
    offset: int
    itens: list[OcorrenciaNota]


class PaginaHistoricoLotes(BaseModel):
    total: int
    limite: int
    offset: int
    itens: list[HistoricoLote]


class PaginaMudancasRegras(BaseModel):
    total: int
    limite: int
    offset: int
    itens: list[MudancaRegras]


# ---------------------------------------------------------------------------
# Login do portal
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    senha: str = Field(min_length=1, max_length=128)


class UsuarioLogado(BaseModel):
    # shortcut: o token protege a sessão do portal (GET /auth/me), mas as rotas de dados seguem abertas
    # para Swagger/curl da banca; o PUT /validators continua exigindo X-API-Key. Exigir o token nelas se virar produto.
    email: str
    nome: str
    cargo: str
    role: Literal["CEDENTE", "GESTOR"]
    token: str


# ---------------------------------------------------------------------------
# Erros (formato único para toda a API)
# ---------------------------------------------------------------------------

class ErroApiCorpo(BaseModel):
    code: str
    message: str
    details: list[Any] = Field(default_factory=list)


class ErroApi(BaseModel):
    error: ErroApiCorpo
