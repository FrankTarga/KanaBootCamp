import { useState, useEffect } from "react";
import {
  Check,
  Play,
  Save,
  Sliders,
  Sparkles,
  TrendingDown,
  TrendingUp,
  X,
} from "lucide-react";
import { obterValidadores } from "../services/api";
import type {
  ComparativoRegras,
  ValidadoresConfig,
} from "../types/api";
import { formatarMoeda } from "../utils/formatters";

interface GavetaGestorProps {
  aberto: boolean;
  onFechar: () => void;
  onAplicarRegras: (config: ValidadoresConfig) => Promise<void>;
  onSimularWhatIf: (config: ValidadoresConfig) => Promise<void>;
  carregando: boolean;
  comparativo: ComparativoRegras | null;
}

// Rótulos amigáveis para nomes técnicos de parâmetros
const ROTULOS_PARAMETROS: Record<string, { label: string; prefix?: string; suffix?: string; type: "number" | "text" | "list" }> = {
  valor_minimo: { label: "Valor Mínimo por Título", prefix: "R$", type: "number" },
  valor_maximo: { label: "Valor Máximo por Título", prefix: "R$", type: "number" },
  prazo_minimo_dias: { label: "Prazo Mínimo", suffix: "dias", type: "number" },
  prazo_maximo_dias: { label: "Prazo Máximo", suffix: "dias", type: "number" },
  percentual_maximo: { label: "Concentração Máxima", suffix: "%", type: "number" },
  agrupamento: { label: "Agrupamento de Risco", type: "text" },
  tipos_aceitos: { label: "Tipos de Título Aceitos (separados por vírgula)", type: "list" },
  situacoes_aceitas: { label: "Situações Cadastrais Aceitas (separadas por vírgula)", type: "list" },
};

export function GavetaGestor({
  aberto,
  onFechar,
  onAplicarRegras,
  onSimularWhatIf,
  carregando,
  comparativo,
}: GavetaGestorProps) {
  const [config, setConfig] = useState<ValidadoresConfig | null>(null);
  const [salvando, setSalvando] = useState(false);
  const [sucesso, setSucesso] = useState(false);

  useEffect(() => {
    if (aberto) {
      obterValidadores().then((res) => {
        setConfig(JSON.parse(JSON.stringify(res.dados)));
      });
    }
  }, [aberto]);

  if (!aberto || !config) return null;

  const toggleValidador = (index: number) => {
    setConfig((prev) => {
      if (!prev) return prev;
      const novo = JSON.parse(JSON.stringify(prev)) as ValidadoresConfig;
      novo.validadores[index].ativo = !novo.validadores[index].ativo;
      return novo;
    });
  };

  const atualizarParametro = (
    validadorIdx: number,
    chave: string,
    valor: string,
    tipo: "number" | "text" | "list"
  ) => {
    setConfig((prev) => {
      if (!prev) return prev;
      const novo = JSON.parse(JSON.stringify(prev)) as ValidadoresConfig;
      const validador = novo.validadores[validadorIdx];

      if (tipo === "number") {
        const num = parseFloat(valor);
        validador.parametros[chave] = isNaN(num) ? 0 : num;
      } else if (tipo === "list") {
        validador.parametros[chave] = valor
          .split(",")
          .map((v) => v.trim())
          .filter(Boolean);
      } else {
        validador.parametros[chave] = valor;
      }

      return novo;
    });
  };

  const atualizarPrecificacao = (campo: "taxa_mensal_percentual" | "base_dias", valor: number) => {
    setConfig((prev) => {
      if (!prev || !prev.precificacao) return prev;
      return {
        ...prev,
        precificacao: {
          ...prev.precificacao,
          [campo]: valor,
        },
      };
    });
  };

  const handleSalvarEPermutar = async () => {
    if (!config) return;
    setSalvando(true);
    try {
      await onAplicarRegras(config);
      setSucesso(true);
      setTimeout(() => setSucesso(false), 3000);
    } finally {
      setSalvando(false);
    }
  };

  const handleSimularWhatIf = async () => {
    if (!config) return;
    setSalvando(true);
    try {
      await onSimularWhatIf(config);
    } finally {
      setSalvando(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-hidden">
      {/* Backdrop */}
      <div
        onClick={onFechar}
        className="absolute inset-0 bg-slate-900/40 backdrop-blur-xs transition-opacity animate-fade-in"
      />

      <div className="fixed inset-y-0 right-0 max-w-full flex pl-10">
        <div className="w-screen max-w-xl bg-white shadow-2xl flex flex-col animate-slide-in-right">
          {/* Topo do Drawer */}
          <div className="p-6 border-b border-slate-200 bg-slate-900 text-white flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                <Sliders className="h-5 w-5" />
              </div>
              <div>
                <h2 className="text-base font-bold">Motor Zero-Deploy</h2>
                <p className="text-xs text-slate-400">
                  Ajuste políticas de risco do {config.fundo.nome} sem reiniciar a aplicação
                </p>
              </div>
            </div>

            <button
              type="button"
              onClick={onFechar}
              className="text-slate-400 hover:text-white p-2 rounded-lg hover:bg-slate-800 transition-colors"
            >
              <X className="h-5 w-5" />
            </button>
          </div>

          {/* Banner de Comparativo What-If se houver mudança recente */}
          {comparativo && (
            <div className="bg-emerald-50 border-b border-emerald-200 p-4">
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-bold text-emerald-950 uppercase tracking-wider flex items-center gap-1.5">
                  <Sparkles className="h-3.5 w-3.5 text-emerald-600" />
                  Impacto da Nova Configuração no Lote:
                </span>
                <span className="text-[10px] font-semibold bg-emerald-200/80 text-emerald-900 px-2 py-0.5 rounded-full">
                  {comparativo.tipo === "aplicado" ? "Persistido em Disco" : "Simulação What-If"}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-2 mt-2">
                <div className="bg-white rounded-lg p-2.5 border border-emerald-200">
                  <span className="text-[11px] text-slate-500 block">Variação de Caixa (Líquido):</span>
                  <div className="flex items-center gap-1 font-bold money text-sm">
                    {comparativo.liquidoDepois >= comparativo.liquidoAntes ? (
                      <>
                        <TrendingUp className="h-4 w-4 text-emerald-600" />
                        <span className="text-emerald-700">
                          + {formatarMoeda(comparativo.liquidoDepois - comparativo.liquidoAntes)}
                        </span>
                      </>
                    ) : (
                      <>
                        <TrendingDown className="h-4 w-4 text-rose-600" />
                        <span className="text-rose-700">
                          - {formatarMoeda(comparativo.liquidoAntes - comparativo.liquidoDepois)}
                        </span>
                      </>
                    )}
                  </div>
                </div>

                <div className="bg-white rounded-lg p-2.5 border border-emerald-200">
                  <span className="text-[11px] text-slate-500 block">Notas Aprovadas:</span>
                  <span className="font-bold text-slate-800 text-sm">
                    {comparativo.aprovadasDepois} de {comparativo.totalNotas}{" "}
                    <span className="text-xs font-normal text-slate-500">
                      ({comparativo.aprovadasDepois - comparativo.aprovadasAntes >= 0 ? "+" : ""}
                      {comparativo.aprovadasDepois - comparativo.aprovadasAntes})
                    </span>
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* Corpo Rolável com as Regras */}
          <div className="flex-1 overflow-y-auto p-6 space-y-6">
            {/* Bloco de Precificação Global */}
            {config.precificacao && (
              <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700">
                    Parâmetros Globais de Precificação
                  </h3>
                  <span className="text-[10px] font-mono text-slate-400 bg-white border border-slate-200 px-2 py-0.5 rounded">
                    {config.precificacao.metodo}
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-[11px] font-semibold text-slate-600 block mb-1">
                      Taxa Mensal Padrão (% a.m.)
                    </label>
                    <input
                      type="number"
                      step="0.1"
                      value={config.precificacao.taxa_mensal_percentual ?? 2.0}
                      onChange={(e) =>
                        atualizarPrecificacao("taxa_mensal_percentual", parseFloat(e.target.value) || 0)
                      }
                      className="input-base text-xs money"
                    />
                  </div>

                  <div>
                    <label className="text-[11px] font-semibold text-slate-600 block mb-1">
                      Base de Dias (Comercial)
                    </label>
                    <input
                      type="number"
                      value={config.precificacao.base_dias}
                      onChange={(e) =>
                        atualizarPrecificacao("base_dias", parseInt(e.target.value, 10) || 30)
                      }
                      className="input-base text-xs money"
                    />
                  </div>
                </div>
              </div>
            )}

            {/* Lista de Validadores */}
            <div className="space-y-3">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500">
                Regras de Elegibilidade & Limites ({config.validadores.length} regras)
              </h3>

              {config.validadores.map((validador, vIdx) => {
                const parametros = Object.entries(validador.parametros);

                return (
                  <div
                    key={validador.codigo}
                    className={`rounded-xl border p-4 transition-all ${
                      validador.ativo
                        ? "border-slate-200 bg-white shadow-2xs"
                        : "border-slate-200/60 bg-slate-50/70 opacity-70"
                    }`}
                  >
                    {/* Header da Regra com Toggle */}
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <div className="flex items-center gap-2">
                          <h4 className="text-xs font-bold text-slate-900">
                            {validador.codigo}
                          </h4>
                          <span
                            className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${
                              validador.ativo
                                ? "bg-emerald-100 text-emerald-800"
                                : "bg-slate-200 text-slate-600"
                            }`}
                          >
                            {validador.ativo ? "Ativa" : "Desativada"}
                          </span>
                        </div>
                      </div>

                      {/* Toggle Switch */}
                      <label className="relative inline-flex items-center cursor-pointer">
                        <input
                          type="checkbox"
                          checked={validador.ativo}
                          onChange={() => toggleValidador(vIdx)}
                          className="sr-only"
                        />
                        <div
                          className={`w-9 h-5 rounded-full transition-colors ${
                            validador.ativo ? "bg-emerald-600" : "bg-slate-300"
                          }`}
                        >
                          <div
                            className={`w-4 h-4 rounded-full bg-white transition-transform transform mt-0.5 ml-0.5 ${
                              validador.ativo ? "translate-x-4" : "translate-x-0"
                            }`}
                          />
                        </div>
                      </label>
                    </div>

                    {/* Inputs de Parâmetros Dinâmicos */}
                    {parametros.length > 0 && validador.ativo && (
                      <div className="mt-3 pt-3 border-t border-slate-100 space-y-2.5">
                        {parametros.map(([chave, valor]) => {
                          const metaParam = ROTULOS_PARAMETROS[chave] ?? {
                            label: chave.replace(/_/g, " "),
                            type: typeof valor === "number" ? "number" : Array.isArray(valor) ? "list" : "text",
                          };

                          const valorExibicao = Array.isArray(valor) ? valor.join(", ") : String(valor ?? "");

                          return (
                            <div key={chave}>
                              <label className="text-[11px] font-semibold text-slate-600 block mb-1">
                                {metaParam.label}
                              </label>
                              <div className="relative">
                                {metaParam.prefix && (
                                  <span className="absolute left-3 top-2.5 text-xs text-slate-400 font-medium">
                                    {metaParam.prefix}
                                  </span>
                                )}
                                <input
                                  type={metaParam.type === "number" ? "number" : "text"}
                                  step={metaParam.type === "number" ? "any" : undefined}
                                  value={valorExibicao}
                                  onChange={(e) =>
                                    atualizarParametro(vIdx, chave, e.target.value, metaParam.type)
                                  }
                                  className={`input-base text-xs ${
                                    metaParam.prefix ? "pl-8" : ""
                                  } ${metaParam.suffix ? "pr-10" : ""}`}
                                />
                                {metaParam.suffix && (
                                  <span className="absolute right-3 top-2.5 text-xs text-slate-400 font-medium">
                                    {metaParam.suffix}
                                  </span>
                                )}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Rodapé com Botões de Ação */}
          <div className="p-4 border-t border-slate-200 bg-slate-50 space-y-2">
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handleSimularWhatIf}
                disabled={salvando || carregando}
                className="btn btn-secondary flex-1 text-xs py-2.5"
                title="Testa o impacto no lote sem alterar permanentemente o validadores_antecipe.json"
              >
                <Play className="h-3.5 w-3.5 text-emerald-600" />
                <span>Simular What-If</span>
              </button>

              <button
                type="button"
                onClick={handleSalvarEPermutar}
                disabled={salvando || carregando}
                className="btn btn-emerald flex-2 text-xs py-2.5 shadow-md"
              >
                {sucesso ? (
                  <>
                    <Check className="h-3.5 w-3.5 text-white" />
                    <span>Regras Salvas e Lote Recalculado!</span>
                  </>
                ) : (
                  <>
                    <Save className="h-3.5 w-3.5 text-white" />
                    <span>Aplicar sem Deploy & Recalcular</span>
                  </>
                )}
              </button>
            </div>

            <p className="text-[11px] text-center text-slate-400">
              O motor recarrega as regras em memória atomicamente sem downtime.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
