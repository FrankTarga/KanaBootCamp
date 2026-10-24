import type {
  BatchValidationResponse,
  ErroApiCorpo,
  HealthResponse,
  OpcoesValidacao,
  ValidadoresConfig,
} from "../types/api";
import mockLote from "./mockLote.json";

export const API_URL = (import.meta.env.VITE_API_URL ?? "http://localhost:8000/api/v1").replace(/\/$/, "");
export const USAR_MOCK = import.meta.env.VITE_USE_MOCK === "true";

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

async function requisitar<T>(caminho: string, init?: RequestInit): Promise<{ dados: T; resposta: Response }> {
  let resposta: Response;
  try {
    resposta = await fetch(`${API_URL}${caminho}`, init);
  } catch {
    throw new ApiError(0, "API_INDISPONIVEL", `Não foi possível conectar à API em ${API_URL}.`);
  }
  if (!resposta.ok) {
    const corpo = (await resposta.json().catch(() => null)) as ErroApiCorpo | null;
    throw new ApiError(
      resposta.status,
      corpo?.error.code ?? `HTTP_${resposta.status}`,
      corpo?.error.message ?? resposta.statusText,
      corpo?.error.details ?? [],
    );
  }
  return { dados: (await resposta.json()) as T, resposta };
}

export async function obterHealth(): Promise<HealthResponse> {
  return (await requisitar<HealthResponse>("/health")).dados;
}

export async function obterValidadores(): Promise<ValidadoresConfig> {
  return (await requisitar<ValidadoresConfig>("/validators")).dados;
}

export async function salvarValidadores(config: ValidadoresConfig): Promise<ValidadoresConfig> {
  const init: RequestInit = {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  };
  return (await requisitar<ValidadoresConfig>("/validators", init)).dados;
}

export interface ResultadoValidacao {
  dados: BatchValidationResponse;
  replayIdempotente: boolean; // true = mesma requisição já processada (cache do back-end)
}

export async function validarLote(arquivo: File, opcoes: OpcoesValidacao = {}): Promise<ResultadoValidacao> {
  if (USAR_MOCK) {
    return { dados: mockLote as BatchValidationResponse, replayIdempotente: false };
  }
  const form = new FormData();
  form.append("file", arquivo);
  if (opcoes.dataBase) form.append("data_base", opcoes.dataBase);
  if (opcoes.taxaMensal !== undefined) form.append("taxa_mensal", String(opcoes.taxaMensal));
  if (opcoes.otimizarLote !== undefined) form.append("otimizar_lote", String(opcoes.otimizarLote));
  if (opcoes.validadoresOverride) form.append("validadores_override", JSON.stringify(opcoes.validadoresOverride));

  const { dados, resposta } = await requisitar<BatchValidationResponse>("/batches/validate", {
    method: "POST",
    body: form,
  });
  return { dados, replayIdempotente: resposta.headers.get("X-Idempotent-Replay") === "true" };
}
