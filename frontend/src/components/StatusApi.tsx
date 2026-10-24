import { useEffect, useState } from "react";
import { Activity, Database, ShieldCheck, Zap } from "lucide-react";
import { obterHealth } from "../services/api";
import type { FonteDados, HealthResponse } from "../types/api";
import { formatarMoeda } from "../utils/formatters";

interface StatusApiProps {
  tempoProcessamentoMs?: number;
  dataBase?: string;
}

export function StatusApi({ tempoProcessamentoMs, dataBase }: StatusApiProps) {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [fonte, setFonte] = useState<FonteDados>("demo");
  const [carregando, setCarregando] = useState(true);

  useEffect(() => {
    let ativo = true;
    obterHealth()
      .then((res) => {
        if (ativo) {
          setHealth(res.dados);
          setFonte(res.fonte);
          setCarregando(false);
        }
      })
      .catch(() => {
        if (ativo) setCarregando(false);
      });

    return () => {
      ativo = false;
    };
  }, []);

  if (carregando) {
    return (
      <div className="flex items-center gap-2 text-xs text-slate-500 animate-pulse">
        <Activity className="h-3.5 w-3.5 text-slate-400" />
        <span>Verificando a conexão…</span>
      </div>
    );
  }

  const isReal = fonte === "api";

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-slate-600 bg-slate-50 border border-slate-200/80 rounded-xl px-3.5 py-2">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
        <div className="flex items-center gap-1.5 font-medium">
          <span className="relative flex h-2 w-2">
            <span
              className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${
                isReal ? "bg-emerald-400" : "bg-amber-400"
              }`}
            />
            <span
              className={`relative inline-flex rounded-full h-2 w-2 ${
                isReal ? "bg-emerald-500" : "bg-amber-500"
              }`}
            />
          </span>
          <span className={isReal ? "text-emerald-800 font-semibold" : "text-amber-800 font-semibold"}>
            {isReal ? "Análise ligada" : "Modo demonstração"}
          </span>
        </div>

        <div className="flex items-center gap-1.5 text-slate-600">
          <Database className="h-3.5 w-3.5 text-slate-400" />
          <span>
            <strong className="text-slate-800 money">
              {health ? health.estoque_total_linhas.toLocaleString("pt-BR") : "100.554"}
            </strong>{" "}
            notas já compradas por {health ? health.fundos_monitorados : 18} fundos (usadas para checar repetição e fraude)
          </span>
        </div>

        <div className="flex items-center gap-1.5 text-slate-600">
          <ShieldCheck className="h-3.5 w-3.5 text-slate-400" />
          <span>
            Patrimônio do fundo:{" "}
            <strong className="text-slate-800 money">
              {formatarMoeda(health?.patrimonio_antecipe_fidc ?? 18540230)}
            </strong>
          </span>
        </div>
      </div>

      <div className="flex items-center gap-3 text-slate-500 text-[11px]">
        {tempoProcessamentoMs !== undefined && (
          <div className="flex items-center gap-1 text-slate-700 bg-white border border-slate-200 px-2 py-0.5 rounded shadow-2xs" title="Tempo que o servidor levou para analisar o lote">
            <Zap className="h-3 w-3 text-amber-500" />
            <span className="tabular-nums">analisado em {tempoProcessamentoMs < 1000 ? `${Math.max(1, Math.round(tempoProcessamentoMs))} ms` : `${(tempoProcessamentoMs / 1000).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} s`}</span>
          </div>
        )}
        <span>Data-base: <strong className="text-slate-700">{dataBase || health?.data_base_padrao || "22/10/2026"}</strong></span>
      </div>
    </div>
  );
}
