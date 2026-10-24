import { useEffect, useState } from "react";

import { API_URL, ApiError, USAR_MOCK, obterHealth } from "../services/api";
import type { HealthResponse } from "../types/api";

const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

export function StatusApi() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    if (USAR_MOCK) return;
    obterHealth()
      .then(setHealth)
      .catch((e: unknown) => setErro(e instanceof ApiError ? e.message : String(e)));
  }, []);

  if (USAR_MOCK) {
    return <p className="text-sm text-amber-700">Modo mock ativo (VITE_USE_MOCK=true).</p>;
  }
  if (erro) {
    return <p className="text-sm text-red-700">{erro}</p>;
  }
  if (!health) {
    return <p className="text-sm text-slate-500">Conectando a {API_URL}…</p>;
  }
  return (
    <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
      <div>
        <dt className="text-slate-500">Data-base</dt>
        <dd className="font-semibold">{health.data_base_padrao}</dd>
      </div>
      <div>
        <dt className="text-slate-500">Patrimônio ANTECIPE</dt>
        <dd className="font-semibold">{brl.format(health.patrimonio_antecipe_fidc)}</dd>
      </div>
      <div>
        <dt className="text-slate-500">Estoque monitorado</dt>
        <dd className="font-semibold">
          {health.estoque_total_linhas.toLocaleString("pt-BR")} títulos · {health.fundos_monitorados} fundos
        </dd>
      </div>
      <div>
        <dt className="text-slate-500">Regras ativas</dt>
        <dd className="font-semibold">{health.regras_ativas_count}</dd>
      </div>
    </dl>
  );
}
