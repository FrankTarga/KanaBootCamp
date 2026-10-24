import { useState, useEffect } from "react";
import {
  Check,
  Eye,
  EyeOff,
  KeyRound,
  Play,
  Save,
  Sliders,
  Sparkles,
  TrendingDown,
  TrendingUp,
  X,
} from "lucide-react";
import { ApiError, obterValidadores } from "../services/api";
import type {
  ComparativoRegras,
  ValidadoresConfig,
} from "../types/api";
import { formatarMoeda } from "../utils/formatters";
import { NOMES_REGRAS, OPCOES_PARAMETRO, nomeRegra } from "../utils/nomes";

interface GavetaGestorProps {
  aberto: boolean;
  onFechar: () => void;
  onAplicarRegras: (config: ValidadoresConfig, chaveGestor: string) => Promise<void>;
  onSimularWhatIf: (config: ValidadoresConfig) => Promise<void>;
  carregando: boolean;
  comparativo: ComparativoRegras | null;
}

// Rótulos em português comum para os parâmetros do JSON do fundo
const ROTULOS_PARAMETROS: Record<string, { label: string; prefix?: string; suffix?: string; type: "number" | "text" | "list" | "escolha" }> = {
  valor_minimo: { label: "Valor mínimo", prefix: "R$", type: "number" },
  valor_maximo: { label: "Valor máximo", prefix: "R$", type: "number" },
  prazo_minimo_dias: { label: "Prazo mínimo", suffix: "dias", type: "number" },
  prazo_maximo_dias: { label: "Prazo máximo", suffix: "dias", type: "number" },
  percentual_maximo: { label: "Parte máxima do fundo", suffix: "%", type: "number" },
  agrupamento: { label: "Como somar o cliente", type: "escolha" },
  tipos_aceitos: { label: "Tipos aceitos", type: "list" },
  situacoes_aceitas: { label: "Situações aceitas", type: "list" },
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
  const [erroSalvar, setErroSalvar] = useState<string | null>(null);
  const [mostrarChave, setMostrarChave] = useState(false);
  // chave do gestor (ADMIN_API_KEY do servidor): só nesta aba, some ao fechar o navegador
  const [chaveGestor, setChaveGestor] = useState<string>(() => {
    try { return sessionStorage.getItem("admin_api_key") ?? ""; } catch { return ""; }
  });
  const mudarChave = (v: string) => {
    setChaveGestor(v);
    setErroSalvar(null);
    try { if (v.trim()) sessionStorage.setItem("admin_api_key", v.trim()); else sessionStorage.removeItem("admin_api_key"); } catch { /* armazenamento bloqueado: segue só em memória */ }
  };

  useEffect(() => {
    if (aberto) {
      setErroSalvar(null);
      obterValidadores().then((res) => {
        setConfig(JSON.parse(JSON.stringify(res.dados)));
      });
    }
  }, [aberto]);

  // com a gaveta aberta, a página de trás não rola e Esc fecha
  useEffect(() => {
    if (!aberto) return;
    const anterior = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const aoTeclar = (e: KeyboardEvent) => { if (e.key === "Escape") onFechar(); };
    window.addEventListener("keydown", aoTeclar);
    return () => { document.body.style.overflow = anterior; window.removeEventListener("keydown", aoTeclar); };
  }, [aberto, onFechar]);

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
    tipo: "number" | "text" | "list" | "escolha"
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

  const alternarOpcao = (validadorIdx: number, chave: string, opcao: string) => {
    setConfig((prev) => {
      if (!prev) return prev;
      const novo = JSON.parse(JSON.stringify(prev)) as ValidadoresConfig;
      const atual = (novo.validadores[validadorIdx].parametros[chave] as string[] | null) ?? [];
      novo.validadores[validadorIdx].parametros[chave] = atual.includes(opcao) ? atual.filter((v) => v !== opcao) : [...atual, opcao];
      return novo;
    });
  };

  const atualizarPrecificacao = (campo: "taxa_mensal_percentual" | "base_dias" | "prazo_minimo_cobranca_dias", valor: number) => {
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
    setErroSalvar(null);
    try {
      await onAplicarRegras(config, chaveGestor.trim());
      setSucesso(true);
      setTimeout(() => setSucesso(false), 3000);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) setErroSalvar("Chave do gestor errada ou em branco. As regras não foram salvas.");
      else if (e instanceof ApiError && e.status === 403) setErroSalvar("O servidor ainda não tem uma chave do gestor configurada, então não aceita salvar. Você pode usar \"Testar sem salvar\".");
      else setErroSalvar(e instanceof Error ? e.message : "Não foi possível salvar as regras.");
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
    <div className="fixed inset-0 z-50 overflow-hidden" role="dialog" aria-modal="true" aria-labelledby="gaveta-titulo">
      <div onClick={onFechar} className="absolute inset-0 bg-slate-900/40 backdrop-blur-xs animate-fade-in" />

      <div className="fixed inset-y-0 right-0 flex max-w-full sm:pl-10">
        <div className="flex h-full w-screen max-w-xl flex-col bg-creme-claro shadow-2xl animate-slide-in-right">
          <div className="flex items-center justify-between gap-3 bg-floresta p-5 text-creme sm:p-6">
            <div className="flex min-w-0 items-center gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-broto/30 bg-broto/15 text-broto">
                <Sliders className="h-5 w-5" />
              </div>
              <div className="min-w-0">
                <h2 id="gaveta-titulo" className="font-display text-lg font-semibold">Regras do fundo</h2>
                <p className="text-xs text-creme/70">Mude o que o {config.fundo.nome} aceita. Vale na hora, sem reiniciar nada.</p>
              </div>
            </div>
            <button type="button" onClick={onFechar} aria-label="Fechar" className="rounded-lg p-2 text-creme/70 hover:bg-white/10 hover:text-creme">
              <X className="h-5 w-5" />
            </button>
          </div>

          {comparativo && (
            <div className="border-b border-emerald-200 bg-emerald-50 p-4">
              <div className="mb-1 flex flex-wrap items-center justify-between gap-2">
                <span className="flex items-center gap-1.5 text-xs font-semibold text-emerald-950">
                  <Sparkles className="h-3.5 w-3.5 text-emerald-600" /> Efeito da mudança neste lote
                </span>
                <span className="rounded-full bg-emerald-200/80 px-2 py-0.5 text-[11px] font-semibold text-emerald-900">
                  {comparativo.tipo === "aplicado" ? "Regras salvas" : "Só um teste"}
                </span>
              </div>
              <div className="mt-2 grid grid-cols-2 gap-2">
                <div className="rounded-lg border border-emerald-200 bg-white p-2.5">
                  <span className="block text-[11px] text-slate-500">Dinheiro liberado</span>
                  <div className="flex items-center gap-1 text-sm font-bold tabular-nums">
                    {comparativo.liquidoDepois >= comparativo.liquidoAntes ? (
                      <><TrendingUp className="h-4 w-4 text-emerald-600" /><span className="text-emerald-700">+ {formatarMoeda(comparativo.liquidoDepois - comparativo.liquidoAntes)}</span></>
                    ) : (
                      <><TrendingDown className="h-4 w-4 text-rose-600" /><span className="text-rose-700">− {formatarMoeda(comparativo.liquidoAntes - comparativo.liquidoDepois)}</span></>
                    )}
                  </div>
                </div>
                <div className="rounded-lg border border-emerald-200 bg-white p-2.5">
                  <span className="block text-[11px] text-slate-500">Notas aprovadas</span>
                  <span className="text-sm font-bold tabular-nums text-slate-800">
                    {comparativo.aprovadasDepois} de {comparativo.totalNotas}{" "}
                    <span className="text-xs font-normal text-slate-500">
                      ({comparativo.aprovadasDepois - comparativo.aprovadasAntes >= 0 ? "+" : ""}{comparativo.aprovadasDepois - comparativo.aprovadasAntes})
                    </span>
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* só esta parte rola; a rolagem não passa para a página de trás */}
          <div className="min-h-0 flex-1 space-y-6 overflow-y-auto overscroll-contain p-5 sm:p-6">
            {config.precificacao && (
              <div className="space-y-3 rounded-2xl border border-creme-linha bg-creme p-4">
                <div>
                  <h3 className="text-sm font-semibold text-slate-800">Preço da antecipação</h3>
                  <p className="text-xs text-slate-500">Desconto simples: o custo cresce em linha reta com os dias até o vencimento.</p>
                </div>
                <div className="grid gap-3 sm:grid-cols-3">
                  <label className="block text-xs font-medium text-slate-600">
                    Taxa ao mês
                    <span className="relative mt-1 block">
                      <input type="number" step="0.1" value={config.precificacao.taxa_mensal_percentual ?? 2.0}
                        onChange={(e) => atualizarPrecificacao("taxa_mensal_percentual", parseFloat(e.target.value) || 0)} className="input-base pr-8 text-sm tabular-nums" />
                      <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-slate-400">%</span>
                    </span>
                  </label>
                  <label className="block text-xs font-medium text-slate-600">
                    Dias em um mês
                    <input type="number" value={config.precificacao.base_dias}
                      onChange={(e) => atualizarPrecificacao("base_dias", parseInt(e.target.value, 10) || 30)} className="input-base mt-1 text-sm tabular-nums" />
                  </label>
                  {config.precificacao.prazo_minimo_cobranca_dias !== undefined && (
                    <label className="block text-xs font-medium text-slate-600">
                      Cobrar no mínimo
                      <span className="relative mt-1 block">
                        <input type="number" min="0" value={config.precificacao.prazo_minimo_cobranca_dias}
                          onChange={(e) => atualizarPrecificacao("prazo_minimo_cobranca_dias", Math.max(0, parseInt(e.target.value, 10) || 0))} className="input-base pr-12 text-sm tabular-nums" />
                        <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-slate-400">dias</span>
                      </span>
                    </label>
                  )}
                </div>
              </div>
            )}

            <div className="space-y-3">
              <h3 className="text-sm font-semibold text-slate-800">
                O que o fundo aceita <span className="font-normal text-slate-500">· {config.validadores.filter((v) => v.ativo).length} de {config.validadores.length} regras ligadas</span>
              </h3>

              {config.validadores.map((validador, vIdx) => {
                const parametros = Object.entries(validador.parametros);
                const info = NOMES_REGRAS[validador.codigo];
                return (
                  <div key={validador.codigo}
                    className={`rounded-2xl border p-4 transition-colors ${validador.ativo ? "border-creme-linha bg-white" : "border-creme-linha/70 bg-creme/60"}`}>
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <h4 className={`text-sm font-semibold ${validador.ativo ? "text-slate-900" : "text-slate-500"}`}>{nomeRegra(validador.codigo)}</h4>
                        {info && <p className="mt-0.5 text-xs text-slate-500">{info.explica}</p>}
                      </div>
                      <label className="relative inline-flex shrink-0 cursor-pointer items-center gap-2">
                        <span className={`text-[11px] font-semibold ${validador.ativo ? "text-emerald-700" : "text-slate-500"}`}>{validador.ativo ? "Ligada" : "Desligada"}</span>
                        <input type="checkbox" checked={validador.ativo} onChange={() => toggleValidador(vIdx)} className="peer sr-only"
                          aria-label={`${nomeRegra(validador.codigo)}: ${validador.ativo ? "ligada" : "desligada"}`} />
                        <span className={`h-5 w-9 rounded-full transition-colors peer-focus-visible:outline peer-focus-visible:outline-2 peer-focus-visible:outline-emerald-700 ${validador.ativo ? "bg-emerald-600" : "bg-slate-300"}`}>
                          <span className={`mt-0.5 ml-0.5 block h-4 w-4 rounded-full bg-white transition-transform ${validador.ativo ? "translate-x-4" : ""}`} />
                        </span>
                      </label>
                    </div>

                    {parametros.length > 0 && validador.ativo && (
                      <div className="mt-3 space-y-3 border-t border-creme-linha pt-3">
                        {parametros.map(([chave, valor]) => {
                          const meta = ROTULOS_PARAMETROS[chave] ?? {
                            label: chave.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase()),
                            type: typeof valor === "number" ? "number" : Array.isArray(valor) ? "list" : "text",
                          };
                          const opcoes = OPCOES_PARAMETRO[chave];

                          if (meta.type === "list" && opcoes) {
                            const marcados = (Array.isArray(valor) ? valor : []).map(String);
                            // valores que o JSON tem mas a lista não conhece continuam aparecendo
                            const todas = [...opcoes, ...marcados.filter((m) => !opcoes.some((o) => o.valor === m)).map((m) => ({ valor: m, rotulo: m }))];
                            return (
                              <fieldset key={chave}>
                                <legend className="mb-1.5 text-xs font-medium text-slate-600">{meta.label}</legend>
                                <div className="flex flex-wrap gap-2">
                                  {todas.map((o) => {
                                    const on = marcados.includes(o.valor);
                                    return (
                                      <label key={o.valor} className={`cursor-pointer rounded-full border px-3 py-1 text-xs font-medium transition-colors has-[:focus-visible]:outline has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-emerald-700 ${on ? "border-emerald-600 bg-emerald-600 text-white" : "border-creme-linha bg-creme text-slate-600 hover:border-emerald-400"}`}>
                                        <input type="checkbox" className="sr-only" checked={on} onChange={() => alternarOpcao(vIdx, chave, o.valor)} />
                                        {on && <Check className="-ml-0.5 mr-1 inline h-3 w-3" />}{o.rotulo}
                                      </label>
                                    );
                                  })}
                                </div>
                              </fieldset>
                            );
                          }

                          if (meta.type === "escolha" && opcoes) {
                            return (
                              <label key={chave} className="block text-xs font-medium text-slate-600">
                                {meta.label}
                                <select value={String(valor ?? "")} onChange={(e) => atualizarParametro(vIdx, chave, e.target.value, "text")} className="input-base mt-1 text-sm">
                                  {opcoes.map((o) => <option key={o.valor} value={o.valor}>{o.rotulo}</option>)}
                                </select>
                              </label>
                            );
                          }

                          const valorExibicao = Array.isArray(valor) ? valor.join(", ") : String(valor ?? "");
                          return (
                            <label key={chave} className="block text-xs font-medium text-slate-600">
                              {meta.label}
                              <span className="relative mt-1 block">
                                {meta.prefix && <span className="absolute left-3 top-1/2 -translate-y-1/2 text-xs text-slate-400">{meta.prefix}</span>}
                                <input type={meta.type === "number" ? "number" : "text"} step={meta.type === "number" ? "any" : undefined} value={valorExibicao}
                                  onChange={(e) => atualizarParametro(vIdx, chave, e.target.value, meta.type)}
                                  className={`input-base text-sm tabular-nums ${meta.prefix ? "pl-9" : ""} ${meta.suffix ? "pr-12" : ""}`} />
                                {meta.suffix && <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-slate-400">{meta.suffix}</span>}
                              </span>
                            </label>
                          );
                        })}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          <div className="space-y-2 border-t border-creme-linha bg-creme p-4">
            <label className="flex items-center gap-2 rounded-xl border border-creme-linha bg-white px-3 py-2 text-xs text-slate-600">
              <KeyRound className="h-3.5 w-3.5 shrink-0 text-emerald-700" />
              <span className="shrink-0">Chave do gestor</span>
              <input id="chave-gestor" type={mostrarChave ? "text" : "password"} autoComplete="off" value={chaveGestor} onChange={(e) => mudarChave(e.target.value)}
                placeholder="precisa só para salvar" className="min-w-0 flex-1 bg-transparent text-slate-900 outline-none placeholder:text-slate-400" />
              <button type="button" onClick={() => setMostrarChave(!mostrarChave)} aria-label={mostrarChave ? "Esconder chave" : "Mostrar chave"}
                className="shrink-0 rounded p-0.5 text-slate-400 hover:text-slate-700">
                {mostrarChave ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
              </button>
            </label>
            {erroSalvar && <p role="alert" className="rounded-xl bg-rose-50 px-3 py-2 text-xs text-rose-800">{erroSalvar}</p>}
            <div className="flex flex-col gap-2 sm:flex-row">
              <button type="button" onClick={handleSimularWhatIf} disabled={salvando || carregando} className="btn btn-secondary flex-1 py-2.5 text-xs"
                title="Mostra o efeito no lote aberto sem mudar as regras do fundo">
                <Play className="h-3.5 w-3.5 text-emerald-600" /><span>Testar sem salvar</span>
              </button>
              <button type="button" onClick={handleSalvarEPermutar} disabled={salvando || carregando} className="btn btn-emerald flex-1 py-2.5 text-xs shadow-md">
                {sucesso ? <><Check className="h-3.5 w-3.5 text-white" /><span>Regras salvas e lote recalculado</span></>
                  : <><Save className="h-3.5 w-3.5 text-white" /><span>Salvar e recalcular</span></>}
              </button>
            </div>
            <p className="text-center text-[11px] text-slate-500">As novas regras passam a valer na hora para todas as próximas notas.</p>
          </div>
        </div>
      </div>
    </div>
  );
}
