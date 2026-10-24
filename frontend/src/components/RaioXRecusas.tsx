import { AlertCircle, Filter, FilterX } from "lucide-react";
import type { ContagemMotivo } from "../types/api";
import { formatarMoeda } from "../utils/formatters";

interface RaioXRecusasProps {
  motivos: ContagemMotivo[];
  motivoSelecionado: string | null;
  onSelecionarMotivo: (codigo: string | null) => void;
}

export function RaioXRecusas({
  motivos,
  motivoSelecionado,
  onSelecionarMotivo,
}: RaioXRecusasProps) {
  if (!motivos || motivos.length === 0) return null;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <AlertCircle className="h-4 w-4 text-amber-600" />
          <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-700">
            Raio-X das Recusas & Motivos de Inelegibilidade
          </h2>
          <span className="text-[11px] text-slate-400">
            (Clique em um card para filtrar as notas na tabela)
          </span>
        </div>

        {motivoSelecionado && (
          <button
            type="button"
            onClick={() => onSelecionarMotivo(null)}
            className="flex items-center gap-1 text-xs text-slate-500 hover:text-slate-800 bg-slate-100 hover:bg-slate-200 px-2.5 py-1 rounded-md transition-colors"
          >
            <FilterX className="h-3 w-3" />
            <span>Limpar filtro de motivo</span>
          </button>
        )}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
        {motivos.map((motivo) => {
          const isAtivo = motivoSelecionado === motivo.codigo;
          const isFraude = motivo.codigo === "FRAUDE_OUTRO_FUNDO";
          const isDuplicidade = motivo.codigo.startsWith("DUPLICIDADE_");

          let corBadge = "bg-amber-100 text-amber-800 border-amber-200";
          if (isFraude) {
            corBadge = "bg-rose-100 text-rose-800 border-rose-200";
          } else if (isDuplicidade) {
            corBadge = "bg-purple-100 text-purple-800 border-purple-200";
          }

          return (
            <div
              key={motivo.codigo}
              onClick={() => onSelecionarMotivo(isAtivo ? null : motivo.codigo)}
              className={`cursor-pointer rounded-xl border p-3.5 transition-all relative ${
                isAtivo
                  ? "border-emerald-500 bg-emerald-50/40 ring-2 ring-emerald-500/20 shadow-md"
                  : "border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50/50 shadow-2xs"
              }`}
            >
              {isAtivo && (
                <div className="absolute top-2 right-2 flex items-center gap-1 text-[10px] font-semibold text-emerald-700 bg-emerald-100/90 px-1.5 py-0.5 rounded">
                  <Filter className="h-2.5 w-2.5" />
                  Filtrando
                </div>
              )}

              <div className="flex items-start justify-between gap-2 mb-2">
                <span
                  className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold border ${corBadge}`}
                >
                  {isFraude ? "Alerta Crítico" : isDuplicidade ? "Duplicidade" : "Regra de Risco"}
                </span>

                <span className="text-xs font-bold text-slate-700 bg-slate-100 px-2 py-0.5 rounded-full">
                  {motivo.quantidade} {motivo.quantidade === 1 ? "nota" : "notas"}
                </span>
              </div>

              <h3 className="text-xs font-bold text-slate-800 line-clamp-2 leading-snug">
                {motivo.titulo_amigavel}
              </h3>

              <div className="mt-3 pt-2.5 border-t border-slate-100 flex items-center justify-between text-xs">
                <span className="text-slate-500">Valor travado:</span>
                <span className="font-bold text-slate-900 money">
                  {formatarMoeda(motivo.valor_impactado)}
                </span>
              </div>

              <div className="mt-1 text-[10px] font-mono text-slate-400 truncate">
                {motivo.codigo}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
