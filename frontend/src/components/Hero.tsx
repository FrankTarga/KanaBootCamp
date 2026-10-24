import { useEffect, useRef, useState } from "react";
import { ArrowDown, Calendar, CheckCircle2, FileSpreadsheet, FolderUp, Loader2, Percent, Sparkles, X } from "lucide-react";
import { csvsDaLista, csvsDoDrop, juntarCsvs } from "../utils/pastaNotas";
import { formatarDataBRParaInput, formatarDataInputParaBR } from "../utils/formatters";

interface HeroProps {
  onLote: (arquivo: File, qtdArquivos: number) => void;
  carregando: boolean;
  loteAtual: { nome: string; qtdArquivos: number } | null;
  erro: string | null;
  onErro: (mensagem: string | null) => void;
  dataBase: string;
  onDataBaseChange: (v: string) => void;
  taxaMensalPercentual: number;
  onTaxaMensalChange: (v: number) => void;
  otimizarLote: boolean;
  onOtimizarLoteChange: (v: boolean) => void;
}

export function Hero({
  onLote, carregando, loteAtual, erro, onErro,
  dataBase, onDataBaseChange, taxaMensalPercentual, onTaxaMensalChange, otimizarLote, onOtimizarLoteChange,
}: HeroProps) {
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
    onErro(null);
    try {
      const lista = await arquivos;
      onLote(await juntarCsvs(lista), lista.length);
    } catch (e) {
      onErro(e instanceof Error ? e.message : "Não foi possível ler os arquivos.");
    }
  }

  return (
    <section id="inicio" className="bg-creme p-2 sm:p-3">
      <div
        onDragEnter={(e) => { e.preventDefault(); profundidade.current += 1; setArrastando(true); }}
        onDragOver={(e) => e.preventDefault()}
        onDragLeave={() => { profundidade.current -= 1; if (profundidade.current <= 0) setArrastando(false); }}
        onDrop={(e) => {
          e.preventDefault(); profundidade.current = 0; setArrastando(false);
          if (!carregando) receber(csvsDoDrop(e.dataTransfer));
        }}
        className="relative isolate flex min-h-[calc(100svh-1rem)] flex-col overflow-hidden rounded-[28px] bg-floresta-escura text-creme sm:min-h-[calc(100svh-1.5rem)]"
      >
        <video
          ref={video}
          className="absolute inset-0 -z-20 h-full w-full object-cover"
          src="/hero-floresta.mp4"
          poster="/hero-floresta.jpg"
          autoPlay muted loop playsInline aria-hidden="true"
        />
        <div className="absolute inset-0 -z-10 bg-[radial-gradient(ellipse_at_center,rgba(6,34,25,0.15)_0%,rgba(6,34,25,0.65)_75%)]" />
        <div className="absolute inset-x-0 bottom-0 -z-10 h-1/3 bg-gradient-to-t from-floresta-escura/80 to-transparent" />

        <div className="mx-auto flex w-full max-w-5xl flex-1 flex-col items-center justify-center px-5 pb-16 pt-28 text-center sm:pt-32">
          <p className="eyebrow text-creme/70">Antecipação de recebíveis · ANTECIPE FIDC</p>
          <h1 className="mt-5 font-display text-5xl font-bold leading-[0.95] tracking-tight sm:text-7xl lg:text-[5.5rem] [text-wrap:balance]">
            Arraste a pasta de notas
          </h1>
          <p className="mt-6 max-w-2xl text-lg text-creme/85 sm:text-xl">
            Solte aqui a pasta com suas notas em CSV. Em segundos você vê quanto recebe hoje e por que alguma nota ficou de fora.
          </p>

          {/* Área de soltar: a tela inteira aceita o drop, esta caixa mostra onde */}
          <div
            className={`vidro mt-10 w-full max-w-2xl rounded-3xl border-2 border-dashed p-6 transition-all sm:p-8 ${
              arrastando ? "scale-[1.02] border-broto bg-broto/15" : "border-creme/30"
            }`}
          >
            {carregando ? (
              <div className="flex flex-col items-center gap-3 py-2" role="status">
                <Loader2 className="h-9 w-9 animate-spin text-broto" />
                <p className="text-lg font-semibold">Analisando suas notas…</p>
                <p className="text-sm text-creme/70">Conferindo regras do fundo, duplicidades e o preço de cada nota.</p>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-4">
                <FolderUp className={`h-10 w-10 ${arrastando ? "text-broto" : "text-creme/80"}`} />
                <div>
                  <p className="text-lg font-semibold">{arrastando ? "Pode soltar" : "Solte a pasta aqui"}</p>
                  <p className="mt-1 text-sm text-creme/70">Também aceita um ou vários arquivos .csv</p>
                </div>
                <div className="flex flex-wrap items-center justify-center gap-2">
                  <button type="button" onClick={() => inputPasta.current?.click()}
                    className="btn bg-creme text-floresta hover:bg-white focus-visible:ring-creme/40">
                    <FolderUp className="h-4 w-4" /> Escolher pasta
                  </button>
                  <button type="button" onClick={() => inputArquivos.current?.click()}
                    className="btn border border-creme/40 text-creme hover:bg-creme/10 focus-visible:ring-creme/30">
                    <FileSpreadsheet className="h-4 w-4" /> Escolher arquivos
                  </button>
                </div>
                {loteAtual && (
                  <a href="#resultado" className="inline-flex items-center gap-2 rounded-full bg-broto/20 px-3 py-1 text-sm text-creme hover:bg-broto/30">
                    <CheckCircle2 className="h-4 w-4 text-broto" />
                    {loteAtual.qtdArquivos > 1 ? `${loteAtual.qtdArquivos} arquivos analisados` : loteAtual.nome}
                    <span className="font-semibold">· ver resultado</span>
                  </a>
                )}
              </div>
            )}
            <input ref={inputPasta} type="file" className="sr-only" tabIndex={-1} aria-hidden="true"
              onChange={(e) => { receber(csvsDaLista(e.target.files)); e.target.value = ""; }} />
            <input ref={inputArquivos} type="file" accept=".csv,text/csv" multiple className="sr-only" tabIndex={-1} aria-hidden="true"
              onChange={(e) => { receber(csvsDaLista(e.target.files)); e.target.value = ""; }} />
          </div>

          {erro && (
            <div role="alert" className="mt-4 flex w-full max-w-2xl items-start justify-between gap-3 rounded-2xl border border-rose-300/40 bg-rose-950/50 px-4 py-3 text-left text-sm text-rose-100">
              <span>{erro}</span>
              <button type="button" onClick={() => onErro(null)} aria-label="Fechar aviso" className="shrink-0 text-rose-200 hover:text-white">
                <X className="h-4 w-4" />
              </button>
            </div>
          )}

          {/* Parâmetros da operação */}
          <div className="mt-6 flex flex-wrap items-center justify-center gap-2 text-sm">
            <label className="vidro flex items-center gap-2 rounded-full px-3 py-1.5">
              <Calendar className="h-4 w-4 text-creme/70" />
              <span className="text-creme/70">Data da operação</span>
              <input type="date" value={formatarDataBRParaInput(dataBase)} disabled={carregando}
                onChange={(e) => e.target.value && onDataBaseChange(formatarDataInputParaBR(e.target.value))}
                className="bg-transparent font-medium text-creme outline-none [color-scheme:dark]" />
            </label>
            <label className="vidro flex items-center gap-2 rounded-full px-3 py-1.5">
              <Percent className="h-4 w-4 text-creme/70" />
              <span className="text-creme/70">Taxa</span>
              <input type="number" step="0.05" min="0" max="100" value={taxaMensalPercentual} disabled={carregando}
                onChange={(e) => onTaxaMensalChange(parseFloat(e.target.value) || 0)}
                className="w-12 bg-transparent text-right font-medium tabular-nums text-creme outline-none" />
              <span className="text-creme/70">% a.m.</span>
            </label>
            <label className="vidro flex cursor-pointer items-center gap-2 rounded-full px-3 py-1.5"
              title="Reordena as notas para aproveitar melhor o limite de cada cliente e liberar mais dinheiro">
              <input type="checkbox" className="peer sr-only" checked={otimizarLote} disabled={carregando}
                onChange={(e) => onOtimizarLoteChange(e.target.checked)} />
              <span className={`relative h-4 w-7 rounded-full transition-colors peer-focus-visible:ring-2 peer-focus-visible:ring-creme ${otimizarLote ? "bg-broto" : "bg-creme/30"}`}>
                <span className={`absolute top-0.5 h-3 w-3 rounded-full bg-creme transition-transform ${otimizarLote ? "translate-x-3.5" : "translate-x-0.5"}`} />
              </span>
              <Sparkles className="h-4 w-4 text-creme/70" />
              <span className="font-medium">Otimizar para receber mais</span>
            </label>
          </div>
        </div>

        <a href="#resultado" className="absolute bottom-5 left-1/2 flex -translate-x-1/2 flex-col items-center gap-1 text-xs text-creme/70 hover:text-creme">
          Role para ver a análise
          <ArrowDown className="h-4 w-4 motion-safe:animate-bounce" />
        </a>
      </div>
    </section>
  );
}
