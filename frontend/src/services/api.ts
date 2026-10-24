import type {
  BatchValidationResponse,
  ErroApiCorpo,
  FonteDados,
  DetalheLoteHistorico,
  HealthResponse,
  HistoricoLote,
  ItemLote,
  MudancaRegras,
  OcorrenciaNota,
  PaginaHistorico,
  OpcoesValidacao,
  ResultadoProcessamento,
  ValidadoresConfig,
} from "../types/api";
import mockLoteBase from "./mockLote.json";

export const API_URL = (import.meta.env.VITE_API_URL ?? "http://localhost:8000/api/v1").replace(/\/$/, "");
export const FORCAR_MOCK = import.meta.env.VITE_USE_MOCK === "true";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
    public readonly details: unknown[] = [],
  ) {
    super(message);
    this.name = "ApiError";
  }
}

// ---------------------------------------------------------------------------
// Mock em memória resiliente e dinâmico (Fallback de Segurança & Modo Demo)
// ---------------------------------------------------------------------------

export const VALIDADORES_PADRAO: ValidadoresConfig = {
  fundo: {
    nome: "ANTECIPE FIDC",
    cnpj: "92.234.400/0001-80",
  },
  validadores: [
    {
      codigo: "CNPJ_SACADO_VALIDO",
      ativo: true,
      parametros: {},
    },
    {
      codigo: "SITUACAO_CADASTRAL_SACADO",
      ativo: true,
      parametros: {
        situacoes_aceitas: ["ATIVA"],
      },
    },
    {
      codigo: "TIPO_RECEBIVEL",
      ativo: true,
      parametros: {
        tipos_aceitos: ["Duplicata", "Duplicata de Serviço"],
      },
    },
    {
      codigo: "VALOR_MINIMO",
      ativo: true,
      parametros: {
        valor_minimo: 100.0,
      },
    },
    {
      codigo: "NAO_VENCIDA",
      ativo: true,
      parametros: {},
    },
    {
      codigo: "PRAZO_MAXIMO",
      ativo: true,
      parametros: {
        prazo_maximo_dias: 180,
      },
    },
    {
      codigo: "CONCENTRACAO_MAXIMA_SACADO",
      ativo: true,
      parametros: {
        percentual_maximo: 10.0,
        agrupamento: "RAIZ_CNPJ",
      },
    },
    {
      codigo: "PRAZO_MINIMO",
      ativo: false,
      parametros: {
        prazo_minimo_dias: 30,
      },
    },
    {
      codigo: "CONCENTRACAO_MAXIMA_CEDENTE",
      ativo: false,
      parametros: {
        percentual_maximo: 8.0,
      },
    },
  ],
  precificacao: {
    metodo: "DESCONTO_SIMPLES",
    taxa_mensal_percentual: 2.0,
    base_dias: 30,
  },
};

let validadoresEmMemoria: ValidadoresConfig = JSON.parse(JSON.stringify(VALIDADORES_PADRAO));

export const HEALTH_MOCK: HealthResponse = {
  status: "ready",
  data_base_padrao: "22/10/2026",
  estoque_total_linhas: 100554,
  estoque_antecipe_linhas: 8450,
  patrimonio_antecipe_fidc: 18540230.0,
  fundos_monitorados: 18,
  regras_ativas_count: 7,
  taxa_mensal_padrao: 0.02,
  tempo_carga_estoque_ms: 685.4,
  versao_config: 1,
};

// ---------------------------------------------------------------------------
// Cliente HTTP com Timeout e tratamento de erros padrão
// ---------------------------------------------------------------------------

async function requisitar<T>(caminho: string, init?: RequestInit, timeoutMs = 8000): Promise<{ dados: T; resposta: Response }> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  let resposta: Response;
  try {
    resposta = await fetch(`${API_URL}${caminho}`, {
      ...init,
      signal: controller.signal,
    });
  } catch (err: unknown) {
    clearTimeout(timer);
    const msg = err instanceof Error && err.name === "AbortError" ? "Tempo limite esgotado ao contatar a API." : `Falha de conexão com a API em ${API_URL}.`;
    throw new ApiError(0, "API_INDISPONIVEL", msg);
  } finally {
    clearTimeout(timer);
  }

  if (!resposta.ok) {
    const corpo = (await resposta.json().catch(() => null)) as ErroApiCorpo | null;
    throw new ApiError(
      resposta.status,
      corpo?.error?.code ?? `HTTP_${resposta.status}`,
      corpo?.error?.message ?? resposta.statusText,
      corpo?.error?.details ?? [],
    );
  }

  const dados = (await resposta.json()) as T;
  return { dados, resposta };
}

// ---------------------------------------------------------------------------
// Funções Públicas de Consumo com Fallback Gracioso
// ---------------------------------------------------------------------------

export async function obterHealth(): Promise<{ dados: HealthResponse; fonte: FonteDados }> {
  if (FORCAR_MOCK) {
    return { dados: HEALTH_MOCK, fonte: "demo" };
  }
  try {
    const res = await requisitar<HealthResponse>("/health");
    return { dados: res.dados, fonte: "api" };
  } catch (e) {
    console.warn("API de health offline, utilizando fallback de demonstração:", e);
    return { dados: HEALTH_MOCK, fonte: "demo" };
  }
}

export type Sessao = { email: string; nome: string; cargo: string; role: "CEDENTE" | "GESTOR"; token: string };

export async function entrar(email: string, senha: string): Promise<Sessao> {
  const res = await requisitar<Sessao>("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, senha }),
  });
  return res.dados;
}

/** Confere no servidor se o token salvo ainda vale (assinatura e validade); lança ApiError 401 se não. */
export async function sessaoAtual(token: string): Promise<Sessao> {
  const res = await requisitar<Sessao>("/auth/me", { headers: { Authorization: `Bearer ${token}` } });
  return res.dados;
}

export async function obterValidadores(): Promise<{ dados: ValidadoresConfig; fonte: FonteDados }> {
  if (FORCAR_MOCK) {
    return { dados: validadoresEmMemoria, fonte: "demo" };
  }
  try {
    const res = await requisitar<ValidadoresConfig>("/validators");
    validadoresEmMemoria = JSON.parse(JSON.stringify(res.dados));
    return { dados: res.dados, fonte: "api" };
  } catch (e) {
    console.warn("API de validadores offline, utilizando configuração em memória:", e);
    return { dados: validadoresEmMemoria, fonte: "demo" };
  }
}

function lerChaveDaSessao(): string | null {
  try { return sessionStorage.getItem("admin_api_key"); } catch { return null; } // armazenamento bloqueado
}

export async function salvarValidadores(
  config: ValidadoresConfig,
  apiKey?: string,
): Promise<{ dados: ValidadoresConfig; fonte: FonteDados }> {
  if (FORCAR_MOCK) {
    validadoresEmMemoria = JSON.parse(JSON.stringify(config));
    return { dados: validadoresEmMemoria, fonte: "demo" };
  }

  const chave =
    apiKey ||
    lerChaveDaSessao() ||
    (import.meta.env.VITE_ADMIN_API_KEY as string | undefined);
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (chave) {
    headers["X-API-Key"] = chave;
  }

  try {
    const res = await requisitar<ValidadoresConfig>("/validators", {
      method: "PUT",
      headers,
      body: JSON.stringify(config),
    });
    validadoresEmMemoria = JSON.parse(JSON.stringify(res.dados));
    return { dados: res.dados, fonte: "api" };
  } catch (e) {
    if (e instanceof ApiError && e.status === 0) {
      console.warn("API de validadores offline ao salvar, atualizando apenas em memória:", e);
      validadoresEmMemoria = JSON.parse(JSON.stringify(config));
      return { dados: validadoresEmMemoria, fonte: "demo" };
    }
    throw e;
  }
}

// ---------------------------------------------------------------------------
// Histórico (banco SQLite do backend). Sem fallback: offline, a tela avisa em vez de inventar dados.
// ---------------------------------------------------------------------------
export async function listarHistoricoLotes(limite = 50, offset = 0): Promise<PaginaHistorico<HistoricoLote>> {
  return (await requisitar<PaginaHistorico<HistoricoLote>>(`/historico/lotes?limite=${limite}&offset=${offset}`)).dados;
}

export async function listarHistoricoRegras(limite = 50, offset = 0): Promise<PaginaHistorico<MudancaRegras>> {
  return (await requisitar<PaginaHistorico<MudancaRegras>>(`/historico/regras?limite=${limite}&offset=${offset}`)).dados;
}

/** Notas e motivos de um lote antigo (até 10 mil por página, limite do backend). */
export async function obterLoteHistorico(loteId: number, limite = 10_000, offset = 0): Promise<DetalheLoteHistorico> {
  return (await requisitar<DetalheLoteHistorico>(`/historico/lotes/${loteId}?limite=${limite}&offset=${offset}`, undefined, 30_000)).dados;
}

/** Em quais lotes um número de nota apareceu (zeros à esquerda não importam). */
export async function buscarNotaHistorico(nuDocumento: string, limite = 50, offset = 0): Promise<PaginaHistorico<OcorrenciaNota>> {
  const q = encodeURIComponent(nuDocumento.trim());
  return (await requisitar<PaginaHistorico<OcorrenciaNota>>(`/historico/notas?nu_documento=${q}&limite=${limite}&offset=${offset}`)).dados;
}

/**
 * Validação de Lote com Fallback Transparente para o Mock Inteligente.
 * Se a API estiver online, roda no RuleEngine FastAPI em Python.
 * Se offline, simula o recálculo em memória com o dataset de demonstração!
 */
export async function validarLote(arquivo: File | null, opcoes: OpcoesValidacao = {}): Promise<ResultadoProcessamento> {
  // Se forçado mock ou sem arquivo físico (ex: teste rápido clicando em demo)
  if (FORCAR_MOCK || !arquivo) {
    return {
      dados: simularLoteLocal(opcoes),
      fonte: "demo",
      replayIdempotente: false,
    };
  }

  const form = new FormData();
  form.append("file", arquivo);
  if (opcoes.dataBase) form.append("data_base", opcoes.dataBase);
  if (opcoes.taxaMensal !== undefined) form.append("taxa_mensal", String(opcoes.taxaMensal));
  if (opcoes.otimizarLote !== undefined) form.append("otimizar_lote", String(opcoes.otimizarLote));
  if (opcoes.validadoresOverride) form.append("validadores_override", JSON.stringify(opcoes.validadoresOverride));
  if (opcoes.modo && opcoes.modo !== "lote") form.append("modo", opcoes.modo);

  try {
    const { dados, resposta } = await requisitar<BatchValidationResponse>(
      "/batches/validate",
      {
        method: "POST",
        body: form,
      },
      120_000,
    );
    return {
      dados,
      fonte: "api",
      replayIdempotente: resposta.headers.get("X-Idempotent-Replay") === "true",
    };
  } catch (err) {
    if (err instanceof ApiError && err.status === 0) {
      console.warn("Backend offline ou erro de conexão no upload. Acionando motor de contingência demo:", err);
      return {
        dados: simularLoteLocal(opcoes),
        fonte: "demo",
        replayIdempotente: false,
      };
    }
    throw err;
  }
}

/**
 * Simulador Local Dinâmico (Offline / What-If / Demo)
 * Recalcula deságio, prazos e impacto de ativação/desativação de regras
 */
export function simularLoteLocal(opcoes: OpcoesValidacao = {}): BatchValidationResponse {
  const base = JSON.parse(JSON.stringify(mockLoteBase)) as BatchValidationResponse;
  const config = opcoes.validadoresOverride ?? validadoresEmMemoria;
  const taxaMensal = opcoes.taxaMensal ?? (config.precificacao?.taxa_mensal_percentual ? config.precificacao.taxa_mensal_percentual / 100 : 0.02);
  const otimizar = opcoes.otimizarLote ?? true;

  // Mapa de validadores ativos
  const regrasAtivas = new Map<string, boolean>();
  config.validadores.forEach((v) => regrasAtivas.set(v.codigo, v.ativo));

  let brutoTotal = 0;
  let brutoAprovado = 0;
  let desagioTotal = 0;
  let liquidoTotal = 0;
  let somaPrazoPonderado = 0;
  let qtdFraude = 0;
  let qtdSalvas = 0;

  const motivoMap = new Map<string, { titulo: string; qtd: number; valor: number }>();

  const itensAtualizados: ItemLote[] = base.itens.map((item) => {
    brutoTotal += item.valor_nominal;

    // Filtra erros mantendo apenas os das regras que continuam ATIVAS
    const errosFiltrados = item.erros.filter((erro) => {
      // Regras de sistema (duplicidade/fraude) estão sempre ativas
      if (erro.codigo.startsWith("DUPLICIDADE_") || erro.codigo.startsWith("FRAUDE_")) {
        return true;
      }
      return regrasAtivas.get(erro.codigo) !== false;
    });

    const isAprovada = errosFiltrados.length === 0;

    // Recalcula deságio com a taxa selecionada
    const prazo = Math.max(0, item.prazo_dias);
    const desagio = isAprovada ? Math.round(item.valor_nominal * taxaMensal * (prazo / 30) * 100) / 100 : 0;
    const liquido = isAprovada ? Math.round((item.valor_nominal - desagio) * 100) / 100 : 0;

    let severidade = item.severidade;
    if (isAprovada) {
      severidade = "OK";
    } else if (errosFiltrados.some((e) => e.codigo === "FRAUDE_OUTRO_FUNDO")) {
      severidade = "FRAUDE";
    } else if (errosFiltrados.some((e) => e.codigo.startsWith("DUPLICIDADE_"))) {
      severidade = "DUPLICIDADE";
    } else {
      severidade = "REGRA_NEGOCIO";
    }

    if (severidade === "FRAUDE") qtdFraude++;

    if (isAprovada) {
      brutoAprovado += item.valor_nominal;
      desagioTotal += desagio;
      liquidoTotal += liquido;
      somaPrazoPonderado += item.valor_nominal * prazo;
      if (item.salva_pelo_otimizador && otimizar) qtdSalvas++;
    } else {
      errosFiltrados.forEach((erro) => {
        const atual = motivoMap.get(erro.codigo) ?? { titulo: erro.titulo_amigavel, qtd: 0, valor: 0 };
        atual.qtd += 1;
        atual.valor += item.valor_nominal;
        motivoMap.set(erro.codigo, atual);
      });
    }

    return {
      ...item,
      status: isAprovada ? "APROVADA" : "RECUSADA",
      severidade,
      desagio_reais: desagio,
      valor_liquido: liquido,
      salva_pelo_otimizador: isAprovada && otimizar && item.salva_pelo_otimizador,
      erros: errosFiltrados,
    };
  });

  const qtdAprovadas = itensAtualizados.filter((i) => i.status === "APROVADA").length;
  const qtdRecusadas = itensAtualizados.length - qtdAprovadas;

  const contagemPorMotivo = Array.from(motivoMap.entries())
    .map(([codigo, dados]) => ({
      codigo: codigo as ItemLote["erros"][0]["codigo"],
      titulo_amigavel: dados.titulo,
      quantidade: dados.qtd,
      valor_impactado: Math.round(dados.valor * 100) / 100,
    }))
    .sort((a, b) => b.quantidade - a.quantidade || b.valor_impactado - a.valor_impactado);

  const ganhoOtimizador = otimizar ? (base.meta.ganho_otimizador_reais > 0 ? base.meta.ganho_otimizador_reais : 33200.0) : 0;

  return {
    meta: {
      batch_hash_idempotencia: "simulacao_demo_" + Math.random().toString(16).substring(2, 10),
      tempo_processamento_ms: 12.4,
      data_base_utilizada: opcoes.dataBase ?? "22/10/2026",
      taxa_mensal_aplicada: taxaMensal,
      otimizador_ativo: otimizar,
      valor_liquido_sem_otimizador: Math.round((liquidoTotal - ganhoOtimizador) * 100) / 100,
      ganho_otimizador_reais: ganhoOtimizador,
      qtd_notas_salvas_otimizador: otimizar ? Math.max(qtdSalvas, 2) : 0,
    },
    resumo: {
      total_notas: itensAtualizados.length,
      qtd_aprovadas: qtdAprovadas,
      qtd_recusadas: qtdRecusadas,
      qtd_alertas_fraude: qtdFraude,
      valor_bruto_total: Math.round(brutoTotal * 100) / 100,
      valor_bruto_aprovado: Math.round(brutoAprovado * 100) / 100,
      valor_bruto_recusado: Math.round((brutoTotal - brutoAprovado) * 100) / 100,
      desagio_total: Math.round(desagioTotal * 100) / 100,
      valor_liquido_receber: Math.round(liquidoTotal * 100) / 100,
      prazo_medio_ponderado_dias: brutoAprovado > 0 ? Math.round((somaPrazoPonderado / brutoAprovado) * 100) / 100 : 0,
      contagem_por_motivo: contagemPorMotivo,
    },
    itens: itensAtualizados,
  };
}
