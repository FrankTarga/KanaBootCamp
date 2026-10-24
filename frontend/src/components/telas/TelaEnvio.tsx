import { useEffect, useRef, useState } from "react";
import { Calendar, CheckCircle2, FileSpreadsheet, FolderUp, Loader2, Percent, Sparkles, X } from "lucide-react";
import { FundoInterativo } from "../FundoInterativo";
import { csvsDaLista, csvsDoDrop, juntarCsvs } from "../../utils/pastaNotas";
import { formatarDataBRParaInput, formatarDataInputParaBR } from "../../utils/formatters";
import type { ModoValidacao } from "../../types/api";

interface TelaEnvioProps {
  onLote: (arquivo: File, qtdArquivos: number) => void;
  onVerResumo: () => void;
  carregando: boolean;
  loteAtual: { nome: string; qtdArquivos: number } | null;
  motorDesligado: boolean;
  erro: string | null;
  onErro: (mensagem: string | null) => void;
  modo: ModoValidacao;
  onModo: (m: ModoValidacao) => void;
  dataBase: string;
  onDataBaseChange: (v: string) => void;
  taxaMensalPercentual: number;
  onTaxaMensalChange: (v: number) => void;
  otimizarLote: boolean;
  onOtimizarLoteChange: (v: boolean) => void;
}

const PASSOS = ["Solte a pasta com os CSVs", "O fundo confere cada nota contra as regras e a carteira", "Você vê quanto recebe hoje e o que fazer com as recusadas"];

export function TelaEnvio(p: TelaEnvioProps) {
  const [arrastando, setArrastando] = useState(false);
  const profundidade = useRef(0); // dragenter/leave disparam em cada filho: conta para não piscar
  const inputPasta = useRef<HTMLInputElement>(null);
  const inputArquivos = useRef<HTMLInputElement>(null);
  const video = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    inputPasta.current?.setAttribute("webkitdirectory", ""); // não existe nos tipos do React
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) video.current?.pause();
  }, []);

  async function receber(arquivos: Promise<File[]> | File[]) {
    p.onErro(null);
    try {
      const lista = await arquivos;
      p.onLote(await juntarCsvs(lista), lista.length);
    } catch (e) {
      p.onErro(e instanceof Error ? e.message : "Não foi possível ler os arquivos.");
    }
  }

  return (
    <div className="p-3 lg:p-4">
      <section
        aria-labelledby="titulo-envio"
        onDragEnter={(e) => { e.preventDefault(); profundidade.current += 1; setArrastando(true); }}
        onDragOver={(e) => e.preventDefault()}
        onDragLeave={() => { profundidade.current -= 1; if (profundidade.current <= 0) setArrastando(false); }}
        onDrop={(e) => {
          e.preventDefault(); profundidade.current = 0; setArrastando(false);
          if (!p.carregando) receber(csvsDoDrop(e.dataTransfer));
        }}
        className="relative isolate overflow-hidden rounded-[28px] bg-floresta-escura text-creme lg:min-h-[calc(100svh-2rem)]"
      >
        <video ref={video} className="absolute inset-0 -z-20 h-full w-full object-cover opacity-70" src="/hero-floresta.mp4"
          poster="/hero-floresta.jpg" autoPlay muted loop playsInline aria-hidden="true" />
        <div className="absolute inset-0 -z-20 bg-gradient-to-r from-floresta-escura via-floresta-escura/70 to-floresta-escura/20" />
        <FundoInterativo aceso={arrastando} />

        <div className="grid gap-10 px-6 py-12 sm:px-10 lg:min-h-[calc(100svh-2rem)] lg:grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)] lg:items-center lg:gap-14 lg:px-14">
          <div>
            <p className="eyebrow text-broto">ANTECIPE FIDC · antecipação de recebíveis</p>
            <h1 id="titulo-envio" className="mt-4 font-display text-5xl font-semibold leading-[1.02] tracking-tight [text-wrap:balance] sm:text-6xl">
              Arraste a pasta de notas.
            </h1>
            <p className="mt-5 max-w-xl text-lg text-creme/80">Sem planilha para montar e sem cadastro: o sistema lê os CSVs da pasta e mostra o resultado em segundos.</p>
            <ol className="mt-8 flex flex-col gap-3">
              {PASSOS.map((t, i) => (
                <li key={t} className="flex items-start gap-3 text-creme/85">
                  <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-broto/60 text-xs font-bold text-broto">{i + 1}</span>
                  {t}
                </li>
              ))}
            </ol>
          </div>

          <div className="flex flex-col gap-4">
            {/* O que é o arquivo: muda as regras que a API aplica */}
            <div role="radiogroup" aria-label="Tipo de arquivo" className="vidro grid grid-cols-2 gap-1 rounded-2xl p-1 text-sm">
              {([["lote", "Notas para antecipar", "lote novo da empresa"], ["carteira", "Carteira do fundo", "estoque, regras do gabarito"]] as const).map(([m, rotulo, dica]) => (
                <button key={m} type="button" role="radio" aria-checked={p.modo === m} onClick={() => p.onModo(m)} disabled={p.carregando}
                  className={`rounded-xl px-3 py-2 text-left transition-colors ${p.modo === m ? "bg-creme text-floresta" : "text-creme/80 hover:bg-white/[0.06]"}`}>
                  <span className="block font-semibold">{rotulo}</span>
                  <span className={`block text-xs ${p.modo === m ? "text-emerald-800/70" : "text-creme/50"}`}>{dica}</span>
                </button>
              ))}
            </div>

            <div className={`vidro rounded-3xl border-2 border-dashed p-8 text-center transition-all ${arrastando ? "scale-[1.02] border-broto bg-broto/15" : "border-creme/30"}`}>
              {p.carregando ? (
                <div className="flex flex-col items-center gap-3 py-4" role="status">
                  <Loader2 className="h-10 w-10 animate-spin text-broto" />
                  <p className="text-lg font-semibold">Analisando suas notas…</p>
                  <p className="text-sm text-creme/70">Regras do fundo, duplicidades e o preço de cada nota.</p>
                </div>
              ) : (
                <div className="flex flex-col items-center gap-4">
                  <FolderUp className={`h-11 w-11 ${arrastando ? "text-broto" : "text-creme/80"}`} />
                  <div>
                    <p className="text-lg font-semibold">{arrastando ? "Pode soltar" : "Solte a pasta aqui"}</p>
                    <p className="mt-1 text-sm text-creme/70">ou um ou vários arquivos .csv</p>
                  </div>
                  <div className="flex flex-wrap justify-center gap-2">
                    <button type="button" onClick={() => inputPasta.current?.click()} className="btn bg-creme text-floresta hover:bg-white focus-visible:ring-creme/40">
                      <FolderUp className="h-4 w-4" /> Escolher pasta
                    </button>
                    <button type="button" onClick={() => inputArquivos.current?.click()} className="btn border border-creme/40 text-creme hover:bg-creme/10 focus-visible:ring-creme/30">
                      <FileSpreadsheet className="h-4 w-4" /> Escolher arquivos
                    </button>
                  </div>
                </div>
              )}
              <input ref={inputPasta} type="file" className="sr-only" tabIndex={-1} aria-hidden="true"
                onChange={(e) => { receber(csvsDaLista(e.target.files)); e.target.value = ""; }} />
              <input ref={inputArquivos} type="file" accept=".csv,text/csv" multiple className="sr-only" tabIndex={-1} aria-hidden="true"
                onChange={(e) => { receber(csvsDaLista(e.target.files)); e.target.value = ""; }} />
            </div>

            {p.loteAtual && !p.carregando && (
              <button type="button" onClick={p.onVerResumo}
                className={`flex items-center justify-between gap-3 rounded-2xl px-4 py-3 text-left text-sm ${p.motorDesligado ? "bg-rose-500/20 hover:bg-rose-500/30" : "bg-broto/20 hover:bg-broto/30"}`}>
                <span className="flex min-w-0 items-center gap-2">
                  {p.motorDesligado ? <X className="h-4 w-4 shrink-0 text-rose-300" /> : <CheckCircle2 className="h-4 w-4 shrink-0 text-broto" />}
                  <span className="truncate">
                    {p.motorDesligado ? `Motor desligado: ${p.loteAtual.nome} não foi analisado`
                      : p.loteAtual.qtdArquivos > 1 ? `${p.loteAtual.qtdArquivos} arquivos analisados` : `${p.loteAtual.nome} analisado`}
                  </span>
                </span>
                <span className="shrink-0 font-semibold">{p.motorDesligado ? "Ver aviso →" : "Ver resumo →"}</span>
              </button>
            )}

            {p.erro && (
              <div role="alert" className="flex items-start justify-between gap-3 rounded-2xl border border-rose-300/40 bg-rose-950/50 px-4 py-3 text-sm text-rose-100">
                <span>{p.erro}</span>
                <button type="button" onClick={() => p.onErro(null)} aria-label="Fechar aviso" className="shrink-0 text-rose-200 hover:text-white"><X className="h-4 w-4" /></button>
              </div>
            )}

            <div className="flex flex-wrap gap-2 text-sm">
              <label className="vidro flex items-center gap-2 rounded-full px-3 py-1.5">
                <Calendar className="h-4 w-4 text-creme/70" /><span className="text-creme/70">Operação</span>
                <input type="date" value={formatarDataBRParaInput(p.dataBase)} disabled={p.carregando}
                  onChange={(e) => e.target.value && p.onDataBaseChange(formatarDataInputParaBR(e.target.value))}
                  className="bg-transparent font-medium text-creme outline-none [color-scheme:dark]" />
              </label>
              <label className="vidro flex items-center gap-2 rounded-full px-3 py-1.5">
                <Percent className="h-4 w-4 text-creme/70" /><span className="text-creme/70">Taxa</span>
                <input type="number" step="0.05" min="0" max="100" value={p.taxaMensalPercentual} disabled={p.carregando}
                  onChange={(e) => p.onTaxaMensalChange(parseFloat(e.target.value) || 0)}
                  className="w-12 bg-transparent text-right font-medium tabular-nums text-creme outline-none" />
                <span className="text-creme/70">% a.m.</span>
              </label>
              <label className="vidro flex cursor-pointer items-center gap-2 rounded-full px-3 py-1.5" title="Reordena as notas para aproveitar melhor o limite de cada cliente">
                <input type="checkbox" className="peer sr-only" checked={p.otimizarLote} disabled={p.carregando} onChange={(e) => p.onOtimizarLoteChange(e.target.checked)} />
                <span className={`relative h-4 w-7 rounded-full transition-colors peer-focus-visible:ring-2 peer-focus-visible:ring-creme ${p.otimizarLote ? "bg-broto" : "bg-creme/30"}`}>
                  <span className={`absolute top-0.5 h-3 w-3 rounded-full bg-creme transition-transform ${p.otimizarLote ? "translate-x-3.5" : "translate-x-0.5"}`} />
                </span>
                <Sparkles className="h-4 w-4 text-creme/70" /><span className="font-medium">Otimizar</span>
              </label>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
