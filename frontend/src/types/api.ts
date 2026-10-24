// Tipos espelhados do contrato REST (backend/app/api_schemas.py). Base: /api/v1
// Mudou um, muda o outro no mesmo commit.

export type StatusNota = "APROVADA" | "RECUSADA";
export type Severidade = "OK" | "REGRA_NEGOCIO" | "DUPLICIDADE" | "FRAUDE";

// ---------------------------------------------------------------------------
// Códigos canônicos de erro (decisão do time: os do validadores_antecipe.json
// + verificações de integridade do motor). Mantidos em sincronia com REGRAS
// em backend/app/rule_engine.py.
// ---------------------------------------------------------------------------

/** Regras configuráveis pelo gestor no validadores_antecipe.json. */
export type CodigoRegraConfiguravel =
  | "CNPJ_SACADO_VALIDO"
  | "SITUACAO_CADASTRAL_SACADO"
  | "TIPO_RECEBIVEL"
  | "VALOR_MINIMO"
  | "NAO_VENCIDA"
  | "PRAZO_MAXIMO"
  | "CONCENTRACAO_MAXIMA_SACADO"
  | "PRAZO_MINIMO"
  | "CONCENTRACAO_MAXIMA_CEDENTE"
  | "CNPJ_CEDENTE_VALIDO"
  | "VALOR_MAXIMO"
  | "DOCUMENTO_BLOQUEADO";

/** Verificações de integridade que o motor sempre executa (triplo radar). */
export type CodigoVerificacaoSistema = "DUPLICIDADE_LOTE" | "DUPLICIDADE_FUNDO" | "FRAUDE_OUTRO_FUNDO";

/** Linha do CSV ilegível (valor, data ou campos obrigatórios). */
export type CodigoFormato = "FORMATO_INVALIDO";

export type CodigoErro = CodigoRegraConfiguravel | CodigoVerificacaoSistema | CodigoFormato;

// ---------------------------------------------------------------------------
// GET /health
// ---------------------------------------------------------------------------

export interface HealthResponse {
  status: "ready" | "loading";
  data_base_padrao: string; // dd/mm/aaaa
  estoque_total_linhas: number;
  estoque_antecipe_linhas: number;
  patrimonio_antecipe_fidc: number;
  fundos_monitorados: number;
  regras_ativas_count: number;
  taxa_mensal_padrao: number;
  tempo_carga_estoque_ms: number;
  versao_config: number;
}

// ---------------------------------------------------------------------------
// GET/PUT /validators (validadores_antecipe.json)
// ---------------------------------------------------------------------------

export type ValorParametro = string | number | boolean | string[] | number[] | null;

export interface ValidadorConfig {
  codigo: string;
  ativo: boolean;
  parametros: Record<string, ValorParametro>;
}

export type MetodoPrecificacao = "DESCONTO_SIMPLES" | "DESCONTO_COMPOSTO";

export interface PrecificacaoConfig {
  metodo: MetodoPrecificacao;
  /** Percentual ao mês no JSON (2.0 = 2% a.m.). A API de validação recebe a fração (0.02). */
  taxa_mensal_percentual: number | null;
  base_dias: number;
}

export interface ValidadoresConfig {
  fundo: { nome: string; cnpj: string };
  validadores: ValidadorConfig[];
  precificacao?: PrecificacaoConfig;
}

// ---------------------------------------------------------------------------
// POST /batches/validate
// ---------------------------------------------------------------------------

export interface ErroNota {
  codigo: CodigoErro;
  titulo_amigavel: string;
  mensagem_empresa: string;
  acao_recomendada: string;
}

export interface ItemLote {
  linha_csv: number; // linha física do arquivo (cabeçalho = 1), igual ao Excel
  ordem_avaliacao: number;
  hash_titulo: string;
  nu_documento: string;
  nome_cedente: string;
  doc_cedente: string;
  nome_sacado: string;
  doc_sacado: string;
  tipo_recebivel: string;
  valor_nominal: number;
  data_vencimento: string; // dd/mm/aaaa
  data_aquisicao: string; // dd/mm/aaaa
  prazo_dias: number;
  desagio_reais: number;
  valor_liquido: number;
  status: StatusNota;
  severidade: Severidade;
  salva_pelo_otimizador: boolean;
  erros: ErroNota[];
}

export interface ContagemMotivo {
  codigo: CodigoErro;
  titulo_amigavel: string;
  quantidade: number;
  valor_impactado: number;
}

export interface ResumoLote {
  total_notas: number;
  qtd_aprovadas: number;
  qtd_recusadas: number;
  qtd_alertas_fraude: number;
  valor_bruto_total: number;
  valor_bruto_aprovado: number;
  valor_bruto_recusado: number;
  desagio_total: number;
  valor_liquido_receber: number;
  prazo_medio_ponderado_dias: number;
  contagem_por_motivo: ContagemMotivo[];
}

export interface MetaLote {
  batch_hash_idempotencia: string;
  tempo_processamento_ms: number;
  data_base_utilizada: string;
  taxa_mensal_aplicada: number; // fração: 0.02 = 2% a.m.
  otimizador_ativo: boolean;
  valor_liquido_sem_otimizador: number;
  ganho_otimizador_reais: number;
  qtd_notas_salvas_otimizador: number;
}

// Painel de recusas (contrato: docs/analise-recusas.md). Mostrar como vem: os percentuais já fecham 100%.
export interface GrupoUmProblema {
  codigo: string;
  titulo_amigavel: string;
  corrigivel: boolean;
  qtd: number;
  valor: number;
  pct_das_recusadas: number;
  liquido_liberado: number | null; // null = sem estimativa (ex.: nota vencida)
}

export interface CombinacaoProblemas {
  codigos: string[];
  titulos: string[];
  qtd: number;
  valor: number;
  pct_do_grupo: number;
}

export interface SubgrupoProblemas {
  qtd_problemas: number;
  qtd: number;
  valor: number;
  pct_do_grupo: number;
  combinacoes: CombinacaoProblemas[];
}

export interface AnaliseRecusas {
  qtd_notas: number;
  qtd_recusadas: number;
  pct_recusadas: number;
  valor_recusado: number;
  qtd_com_mais_de_um_erro: number;
  pct_com_mais_de_um_erro: number;
  grupos: {
    um_problema: GrupoUmProblema[];
    mais_de_um_problema: { qtd: number; valor: number; pct_das_recusadas: number; subgrupos: SubgrupoProblemas[] };
  };
}

export interface BatchValidationResponse {
  meta: MetaLote;
  resumo: ResumoLote;
  itens: ItemLote[];
  analise_recusas?: AnaliseRecusas; // a API sempre manda; o lote de demonstração local não tem
}

/** lote: notas novas contra o estoque · carteira: julga o próprio estoque (regras do gabarito) */
export type ModoValidacao = "lote" | "carteira";

export interface OpcoesValidacao {
  dataBase?: string; // dd/mm/aaaa
  taxaMensal?: number; // fração: 0.02 = 2% a.m.
  otimizarLote?: boolean; // padrão true
  validadoresOverride?: ValidadoresConfig; // what-if do gestor: simula sem salvar
  modo?: ModoValidacao; // padrão: lote
}

// Formato único de erro da API
export interface ErroApiCorpo {
  error: { code: string; message: string; details: unknown[] };
}

// ---------------------------------------------------------------------------
// Tipos exclusivos do front-end
// ---------------------------------------------------------------------------

/** De onde veio o resultado exibido: motor real (FastAPI) ou motor de demonstração local. */
export type FonteDados = "api" | "demo";

export interface ResultadoProcessamento {
  dados: BatchValidationResponse;
  fonte: FonteDados;
  replayIdempotente: boolean;
}

/** Comparativo antes/depois de uma mudança de regra do gestor. */
export interface ComparativoRegras {
  tipo: "aplicado" | "simulado";
  liquidoAntes: number;
  liquidoDepois: number;
  aprovadasAntes: number;
  aprovadasDepois: number;
  totalNotas: number;
}
