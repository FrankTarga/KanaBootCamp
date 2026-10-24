import { useState } from "react";

import { StatusApi } from "./components/StatusApi";
import { ApiError, validarLote } from "./services/api";
import type { BatchValidationResponse } from "./types/api";

const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

export default function App() {
  const [resultado, setResultado] = useState<BatchValidationResponse | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(false);

  async function enviar(arquivo: File | undefined) {
    if (!arquivo) return;
    setCarregando(true);
    setErro(null);
    try {
      setResultado((await validarLote(arquivo)).dados);
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : String(e));
    } finally {
      setCarregando(false);
    }
  }

  return (
    <main className="mx-auto flex max-w-5xl flex-col gap-6 p-6">
      <header>
        <h1 className="text-2xl font-bold">ANTECIPE PRO</h1>
        <p className="text-slate-600">Antecipação de recebíveis com validação em tempo real no ANTECIPE FIDC.</p>
      </header>

      <section className="rounded-lg border border-slate-200 bg-white p-4">
        <StatusApi />
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-4">
        <label className="flex flex-col gap-2 text-sm font-medium">
          Lote de notas (CSV)
          <input
            type="file"
            accept=".csv,text/csv"
            disabled={carregando}
            onChange={(e) => enviar(e.target.files?.[0])}
            className="text-sm"
          />
        </label>
        {carregando && <p className="mt-2 text-sm text-slate-500">Validando…</p>}
        {erro && <p className="mt-2 text-sm text-red-700">{erro}</p>}
        {resultado && (
          <dl className="mt-4 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
            <div>
              <dt className="text-slate-500">Você recebe hoje</dt>
              <dd className="text-lg font-semibold">{brl.format(resultado.resumo.valor_liquido_receber)}</dd>
            </div>
            <div>
              <dt className="text-slate-500">Notas aprovadas</dt>
              <dd className="text-lg font-semibold">
                {resultado.resumo.qtd_aprovadas} de {resultado.resumo.total_notas}
              </dd>
            </div>
            <div>
              <dt className="text-slate-500">Ganho do otimizador</dt>
              <dd className="text-lg font-semibold">{brl.format(resultado.meta.ganho_otimizador_reais)}</dd>
            </div>
            <div>
              <dt className="text-slate-500">Alertas de fraude</dt>
              <dd className="text-lg font-semibold">{resultado.resumo.qtd_alertas_fraude}</dd>
            </div>
          </dl>
        )}
      </section>
    </main>
  );
}
