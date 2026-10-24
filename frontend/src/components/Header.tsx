import { Calendar, Percent, SlidersHorizontal, Sparkles, Wand2 } from "lucide-react";
import { formatarDataBRParaInput, formatarDataInputParaBR } from "../utils/formatters";

interface HeaderProps {
  dataBase: string; // dd/mm/aaaa
  onDataBaseChange: (novaData: string) => void;
  taxaMensalPercentual: number; // ex: 2.0 ou 2.5
  onTaxaMensalChange: (novaTaxa: number) => void;
  otimizarLote: boolean;
  onOtimizarLoteChange: (otimizar: boolean) => void;
  onCarregarDemo: () => void;
  onAbrirGestor: () => void;
  carregando: boolean;
  regrasAtivasCount?: number;
}

export function Header({
  dataBase,
  onDataBaseChange,
  taxaMensalPercentual,
  onTaxaMensalChange,
  otimizarLote,
  onOtimizarLoteChange,
  onCarregarDemo,
  onAbrirGestor,
  carregando,
  regrasAtivasCount = 7,
}: HeaderProps) {
  return (
    <header className="border-b border-slate-200 bg-white/95 backdrop-blur-md sticky top-0 z-30 transition-shadow">
      {/* Topo da barra de navegação */}
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="flex h-16 items-center justify-between gap-4">
          {/* Logo e Brand */}
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-tr from-emerald-600 to-teal-500 text-white shadow-md shadow-emerald-500/20">
              <span className="font-extrabold text-lg tracking-wider">A</span>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-lg font-bold tracking-tight text-slate-900">
                  ANTECIPE <span className="text-emerald-600 font-extrabold">PRO</span>
                </span>
                <span className="inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-600 border border-slate-200">
                  FIDC Engine
                </span>
              </div>
              <p className="text-xs text-slate-500 hidden sm:block">
                Elegibilidade, precificação e liquidez com Zero-Deploy
              </p>
            </div>
          </div>

          {/* Ações do Header */}
          <div className="flex items-center gap-2.5">
            <button
              type="button"
              onClick={onCarregarDemo}
              disabled={carregando}
              className="btn btn-secondary text-xs py-1.5 px-3 border-dashed hover:border-slate-400 group"
              title="Popula a interface com um lote completo de demonstração (22 notas com aprovações, recusas e limites)"
            >
              <Wand2 className="h-3.5 w-3.5 text-slate-500 group-hover:text-emerald-600 transition-colors" />
              <span className="hidden md:inline">Carregar</span> Simulação Demo
            </button>

            <button
              type="button"
              onClick={onAbrirGestor}
              className="btn bg-slate-900 text-white hover:bg-slate-800 text-xs py-1.5 px-3.5 shadow-sm relative group"
            >
              <SlidersHorizontal className="h-3.5 w-3.5 text-emerald-400 group-hover:rotate-180 transition-transform duration-300" />
              <span>Painel do Gestor</span>
              <span className="ml-1 inline-flex items-center justify-center rounded-full bg-emerald-500/20 text-emerald-300 px-1.5 py-0.2 text-[10px] font-mono">
                {regrasAtivasCount}
              </span>
            </button>
          </div>
        </div>
      </div>

      {/* Barra de Controles da Operação */}
      <div className="border-t border-slate-100 bg-slate-50/75 py-2.5 px-4 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-7xl flex flex-wrap items-center justify-between gap-4">
          <div className="flex flex-wrap items-center gap-4 text-xs">
            {/* Input Data-Base */}
            <div className="flex items-center gap-1.5 bg-white border border-slate-200 rounded-lg px-2.5 py-1.5 shadow-2xs">
              <Calendar className="h-3.5 w-3.5 text-slate-400" />
              <span className="text-slate-500 font-medium">Data-Base:</span>
              <input
                type="date"
                value={formatarDataBRParaInput(dataBase)}
                onChange={(e) => onDataBaseChange(formatarDataInputParaBR(e.target.value))}
                disabled={carregando}
                className="font-medium text-slate-800 outline-none text-xs bg-transparent cursor-pointer"
                title="Data de referência para cálculo do deságio e vencimentos (padrão: 22/10/2026)"
              />
            </div>

            {/* Input Taxa Mensal */}
            <div className="flex items-center gap-1.5 bg-white border border-slate-200 rounded-lg px-2.5 py-1.5 shadow-2xs">
              <Percent className="h-3.5 w-3.5 text-slate-400" />
              <span className="text-slate-500 font-medium">Taxa:</span>
              <div className="flex items-center gap-1">
                <input
                  type="number"
                  step="0.05"
                  min="0"
                  max="100"
                  value={taxaMensalPercentual}
                  onChange={(e) => onTaxaMensalChange(parseFloat(e.target.value) || 0)}
                  disabled={carregando}
                  className="w-12 font-medium text-slate-800 outline-none text-xs text-right bg-transparent money"
                />
                <span className="text-slate-600 font-medium">% a.m.</span>
              </div>
            </div>

            {/* Smart Batch Optimizer Toggle */}
            <label
              className={`flex items-center gap-2 cursor-pointer border rounded-lg px-3 py-1.5 transition-all select-none ${
                otimizarLote
                  ? "bg-emerald-50 border-emerald-300 text-emerald-900 shadow-2xs shadow-emerald-500/10"
                  : "bg-white border-slate-200 text-slate-600 hover:border-slate-300"
              }`}
              title="Executa o algoritmo quant para reordenar os títulos e maximizar o valor líquido liberado para a empresa"
            >
              <input
                type="checkbox"
                checked={otimizarLote}
                onChange={(e) => onOtimizarLoteChange(e.target.checked)}
                disabled={carregando}
                className="sr-only"
              />
              <div
                className={`relative inline-flex h-4 w-7 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out ${
                  otimizarLote ? "bg-emerald-600" : "bg-slate-300"
                }`}
              >
                <span
                  className={`inline-block h-3 w-3 transform rounded-full bg-white shadow transition duration-200 ease-in-out ${
                    otimizarLote ? "translate-x-3" : "translate-x-0"
                  }`}
                />
              </div>
              <div className="flex items-center gap-1 font-semibold text-xs">
                <Sparkles className={`h-3 w-3 ${otimizarLote ? "text-emerald-600" : "text-slate-400"}`} />
                <span>Smart Batch Optimizer</span>
              </div>
              {otimizarLote && (
                <span className="text-[10px] bg-emerald-200/80 text-emerald-900 font-bold px-1.5 py-0.2 rounded">
                  Max Caixa
                </span>
              )}
            </label>
          </div>

          <div className="text-[11px] text-slate-500 hidden lg:block">
            Quinta-feira de referência: <strong className="text-slate-700">22/10/2026</strong>
          </div>
        </div>
      </div>
    </header>
  );
}
