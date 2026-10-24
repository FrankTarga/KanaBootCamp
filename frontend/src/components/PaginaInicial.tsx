import { useEffect, useRef } from "react";
import { ArrowDown, CheckCircle2, FolderUp, Lightbulb, Receipt, XCircle } from "lucide-react";
import { Marca, type Tela } from "./MenuLateral";

interface PaginaInicialProps {
  /** desce para o painel; com tela, já abre nela */
  onEntrar: (tela?: Tela) => void;
}

const MENU: { rotulo: string; tela: Tela }[] = [
  { rotulo: "Enviar notas", tela: "envio" },
  { rotulo: "Resumo", tela: "resumo" },
  { rotulo: "Estatística", tela: "estatistica" },
  { rotulo: "Análise de perda", tela: "perda" },
  { rotulo: "Histórico", tela: "historico" },
];

const PASSOS = [
  { Icone: FolderUp, titulo: "Envie suas notas", texto: "Arraste a pasta com os arquivos CSV. Pode ser um arquivo só ou vários de uma vez." },
  { Icone: CheckCircle2, titulo: "Veja o que passou", texto: "Cada nota é conferida nas regras do fundo. As recusadas vêm com o motivo e o que fazer." },
  { Icone: Receipt, titulo: "Saiba quanto recebe", texto: "O valor que cai na conta hoje, já com o custo de antecipar cada nota." },
];

export function PaginaInicial({ onEntrar }: PaginaInicialProps) {
  const ref = useRef<HTMLElement>(null);

  // Rolar para baixo na página inicial desce direto para o painel (roda do mouse, toque ou teclado).
  // Só quando o fim da página inicial já está na tela, para quem tem tela pequena conseguir ler tudo.
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    let descendo = false;
    let toqueY: number | null = null;
    const noFim = () => {
      const r = el.getBoundingClientRect();
      return r.bottom > 0 && r.bottom <= window.innerHeight + 4;
    };
    const descer = (e: Event) => {
      if (descendo || !noFim()) return;
      e.preventDefault();
      descendo = true;
      onEntrar();
      window.setTimeout(() => { descendo = false; }, 900);
    };
    const roda = (e: WheelEvent) => { if (e.deltaY > 8) descer(e); };
    const inicioToque = (e: TouchEvent) => { toqueY = e.touches[0].clientY; };
    const moveToque = (e: TouchEvent) => {
      if (toqueY !== null && toqueY - e.touches[0].clientY > 40) { toqueY = null; descer(e); }
    };
    const tecla = (e: KeyboardEvent) => {
      const alvo = e.target as HTMLElement;
      if (alvo.closest("input, textarea, select")) return;
      if (["ArrowDown", "PageDown", " "].includes(e.key) && el.getBoundingClientRect().bottom > 0) descer(e);
    };
    el.addEventListener("wheel", roda, { passive: false });
    el.addEventListener("touchstart", inicioToque, { passive: true });
    el.addEventListener("touchmove", moveToque, { passive: false });
    window.addEventListener("keydown", tecla);
    return () => {
      el.removeEventListener("wheel", roda);
      el.removeEventListener("touchstart", inicioToque);
      el.removeEventListener("touchmove", moveToque);
      window.removeEventListener("keydown", tecla);
    };
  }, [onEntrar]);

  return (
    <section ref={ref} id="inicio" aria-label="Página inicial" className="relative isolate flex min-h-[100svh] flex-col overflow-hidden bg-creme">
      {/* faixas suaves ao fundo, só decoração */}
      <div aria-hidden="true" className="pointer-events-none absolute -right-40 -top-40 -z-10 h-[34rem] w-[34rem] rounded-full bg-broto/10 blur-3xl" />
      <div aria-hidden="true" className="pointer-events-none absolute -bottom-48 -left-40 -z-10 h-[30rem] w-[30rem] rounded-full bg-floresta/10 blur-3xl" />

      <header className="sticky top-0 z-20 border-b border-creme-linha/80 bg-creme/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center gap-4 px-5 py-3 sm:px-8">
          <button type="button" onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })} aria-label="Início"><Marca clara={false} /></button>
          {/* menu horizontal; no celular rola de lado dentro da própria barra */}
          <nav aria-label="Seções do site" className="ml-auto min-w-0 overflow-x-auto overscroll-x-contain">
            <ul className="flex w-max items-center gap-1 text-sm">
              {MENU.map((m) => (
                <li key={m.tela}>
                  <button type="button" onClick={() => onEntrar(m.tela)}
                    className="whitespace-nowrap rounded-full px-3 py-2 font-medium text-slate-700 hover:bg-creme-linha/60 hover:text-floresta focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-700">
                    {m.rotulo}
                  </button>
                </li>
              ))}
            </ul>
          </nav>
          <button type="button" onClick={() => onEntrar("envio")}
            className="hidden shrink-0 rounded-full bg-floresta px-4 py-2 text-sm font-semibold text-creme hover:bg-floresta-painel md:block">
            Começar
          </button>
        </div>
      </header>

      <div className="mx-auto grid w-full max-w-6xl flex-1 items-center gap-10 px-5 py-10 sm:px-8 lg:grid-cols-[1.1fr_0.9fr] lg:py-14">
        <div className="flex flex-col gap-6">
          <p className="eyebrow text-emerald-700">Antecipação de recebíveis · ANTECIPE FIDC</p>
          <h1 className="font-display text-4xl font-semibold leading-[1.05] tracking-tight text-floresta sm:text-5xl lg:text-6xl">
            Suas notas a receber viram dinheiro hoje. E você sabe na hora quais passam.
          </h1>
          <p className="max-w-xl text-lg leading-relaxed text-slate-600">
            O Antecipe confere cada nota nas regras do fundo, avisa o motivo de cada recusa em linguagem simples e mostra
            quanto cai na sua conta, já descontado o custo de esperar até o vencimento.
          </p>
          <div className="flex flex-wrap items-center gap-3">
            <button type="button" onClick={() => onEntrar("envio")}
              className="rounded-full bg-floresta px-6 py-3 text-base font-semibold text-creme shadow-card hover:bg-floresta-painel focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700">
              Enviar minhas notas
            </button>
            <button type="button" onClick={() => onEntrar("resumo")}
              className="rounded-full border border-floresta/20 px-6 py-3 text-base font-semibold text-floresta hover:border-floresta/50">
              Ver um exemplo
            </button>
          </div>
        </div>

        {/* exemplo do que a pessoa recebe: uma nota aprovada e uma recusada */}
        <div className="relative mx-auto w-full max-w-md" aria-label="Exemplo de resultado">
          <div className="absolute inset-0 -z-10 rotate-[4deg] rounded-3xl bg-floresta" aria-hidden="true" />
          <div className="flex flex-col gap-3 rounded-3xl border border-creme-linha bg-creme-claro p-5 shadow-elevated">
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Exemplo de resultado</p>
            <div className="rounded-2xl border border-emerald-200 bg-emerald-50/70 p-4">
              <p className="flex items-center justify-between gap-2 text-sm">
                <span className="font-semibold text-slate-900">Nota 000353104</span>
                <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-0.5 text-[11px] font-semibold text-emerald-800"><CheckCircle2 className="h-3 w-3" />Aprovada</span>
              </p>
              <p className="mt-1 text-xs text-slate-500">Duplicata · vence em 91 dias</p>
              <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
                <span><span className="block text-slate-500">Valor</span><strong className="tabular-nums text-slate-800">R$ 22.195,70</strong></span>
                <span><span className="block text-slate-500">Custo</span><strong className="tabular-nums text-rose-700">− R$ 1.346,54</strong></span>
                <span><span className="block text-slate-500">Recebe hoje</span><strong className="tabular-nums text-emerald-700">R$ 20.849,16</strong></span>
              </div>
            </div>
            <div className="rounded-2xl border border-amber-200 bg-amber-50/60 p-4">
              <p className="flex items-center justify-between gap-2 text-sm">
                <span className="font-semibold text-slate-900">Nota 000353122</span>
                <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-semibold text-amber-800"><XCircle className="h-3 w-3" />Recusada</span>
              </p>
              <p className="mt-1 text-xs text-slate-600">Cheque não é um tipo que o fundo compra, e 328 dias passa do prazo máximo de 180.</p>
              <p className="mt-2 flex items-start gap-1.5 text-xs text-emerald-900">
                <Lightbulb className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-700" />Envie duplicatas que vençam em até 180 dias.
              </p>
            </div>
          </div>
        </div>
      </div>

      <div className="mx-auto w-full max-w-6xl px-5 pb-6 sm:px-8">
        <ol className="grid gap-3 sm:grid-cols-3">
          {PASSOS.map(({ Icone, titulo, texto }, i) => (
            <li key={titulo} className="flex gap-3 rounded-2xl border border-creme-linha bg-creme-claro/80 p-4">
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-floresta text-broto"><Icone className="h-4 w-4" /></span>
              <span>
                <span className="block text-sm font-semibold text-slate-900">{i + 1}. {titulo}</span>
                <span className="block text-xs leading-relaxed text-slate-600">{texto}</span>
              </span>
            </li>
          ))}
        </ol>
        <button type="button" onClick={() => onEntrar()} className="mx-auto mt-5 flex flex-col items-center gap-1 text-xs font-medium text-slate-500 hover:text-floresta">
          Role para começar <ArrowDown className="h-4 w-4 animate-bounce motion-reduce:animate-none" />
        </button>
      </div>
    </section>
  );
}
