// Tipos espelhados do contrato REST (backend/app/api_schemas.py). Base: /api/v1

export type StatusNota = "APROVADA" | "RECUSADA";
export type Severidade = "OK" | "REGRA_NEGOCIO" | "DUPLICIDADE" | "FRAUDE";

// GET /health
export interface HealthResponse {
  status: "ready" | "loading";
  data_base_padrao: string; // dd/mm/aaaa
  estoque_total_linhas: number;
  estoque_antecipe_linhas: number;
  patrimonio_antecipe_fidc: number;
  fundos_monitorados: number;
  regras_ativas_count: number;
  tempo_carga_estoque_ms: number;
  versao_config: number;
}

// GET/PUT /validators (validadores_antecipe.json)
export interface ValidadorConfig {
  codigo: string;
  ativo: boolean;
  parametros: Record<string, unknown>;
}

export interface ValidadoresConfig {
  fundo: { nome: string; cnpj: string };
  validadores: ValidadorConfig[];
  precificacao?: {
    metodo: "DESCONTO_SIMPLES" | "DESCONTO_COMPOSTO";
    taxa_mensal_percentual: number | null;
    base_dias: number;
  };
}

// POST /batches/validate
export interface ErroNota {
  codigo: string;
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
  data_vencimento: string;
  data_aquisicao: string;
  prazo_dias: number;
  desagio_reais: number;
  valor_liquido: number;
  status: StatusNota;
  severidade: Severidade;
  salva_pelo_otimizador: boolean;
  erros: ErroNota[];
}

export interface ContagemMotivo {
  codigo: string;
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
  taxa_mensal_aplicada: number;
  otimizador_ativo: boolean;
  valor_liquido_sem_otimizador: number;
  ganho_otimizador_reais: number;
  qtd_notas_salvas_otimizador: number;
}

export interface BatchValidationResponse {
  meta: MetaLote;
  resumo: ResumoLote;
  itens: ItemLote[];
}

export interface OpcoesValidacao {
  dataBase?: string; // dd/mm/aaaa
  taxaMensal?: number; // decimal: 0.025 = 2,5% a.m.
  otimizarLote?: boolean; // padrão true
  validadoresOverride?: ValidadoresConfig; // what-if do gestor: simula sem salvar
}

// Formato único de erro da API
export interface ErroApiCorpo {
  error: { code: string; message: string; details: unknown[] };
}
