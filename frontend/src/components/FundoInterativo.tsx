import { useEffect, useRef } from "react";

// Linhas de duna em canvas, por cima do vídeo: ondulam devagar, abrem caminho para o cursor
// e se acendem enquanto a pessoa arrasta a pasta (prop `aceso`).
export function FundoInterativo({ aceso }: { aceso: boolean }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const acesoRef = useRef(aceso);
  acesoRef.current = aceso;

  useEffect(() => {
    const el = canvas.current;
    const ctx = el?.getContext("2d");
    if (!el || !ctx) return;
    const parado = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const cursor = { x: -9999, y: -9999, alvoX: -9999, alvoY: -9999 };
    let w = 0, h = 0, quadro = 0, visivel = true, energia = 0;

    const redimensionar = () => {
      const r = el.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      w = r.width; h = r.height;
      el.width = Math.round(w * dpr); el.height = Math.round(h * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      if (parado) desenhar(0);
    };

    const desenhar = (t: number) => {
      ctx.clearRect(0, 0, w, h);
      energia += ((acesoRef.current ? 1 : 0) - energia) * 0.06;
      cursor.x += (cursor.alvoX - cursor.x) * 0.12;
      cursor.y += (cursor.alvoY - cursor.y) * 0.12;
      const raio = 150 + energia * 120;
      const LINHAS = 26, PASSO = 14;
      for (let i = 0; i < LINHAS; i++) {
        const p = i / (LINHAS - 1);
        const base = h * (0.34 + 0.66 * Math.pow(p, 1.5)); // mais espaçadas perto da "câmera"
        const amp = 5 + 20 * p;
        ctx.beginPath();
        for (let x = -PASSO; x <= w + PASSO; x += PASSO) {
          let y = base + Math.sin(x * 0.004 + t * 0.00035 + i * 0.7) * amp + Math.sin(x * 0.011 - t * 0.0002 + i) * amp * 0.35;
          const dx = x - cursor.x, dy = y - cursor.y, d = Math.hypot(dx, dy);
          if (d < raio) y += Math.sign(dy || 1) * Math.pow(1 - d / raio, 2) * (36 + energia * 30);
          if (x === -PASSO) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        }
        ctx.strokeStyle = `rgba(${i % 4 === 0 ? "244,239,228" : "47,179,111"},${0.05 + 0.16 * p + energia * 0.18})`;
        ctx.lineWidth = 1 + p * 0.6;
        ctx.stroke();
      }
      if (cursor.x > -999) { // brilho que segue o cursor
        const g = ctx.createRadialGradient(cursor.x, cursor.y, 0, cursor.x, cursor.y, raio * 1.4);
        g.addColorStop(0, `rgba(47,179,111,${0.10 + energia * 0.12})`);
        g.addColorStop(1, "rgba(47,179,111,0)");
        ctx.fillStyle = g;
        ctx.fillRect(cursor.x - raio * 1.4, cursor.y - raio * 1.4, raio * 2.8, raio * 2.8);
      }
    };

    const laco = (t: number) => {
      if (visivel && !document.hidden) desenhar(t);
      quadro = requestAnimationFrame(laco);
    };
    const mover = (e: PointerEvent | DragEvent) => {
      const r = el.getBoundingClientRect();
      cursor.alvoX = e.clientX - r.left; cursor.alvoY = e.clientY - r.top;
    };
    const sair = () => { cursor.alvoX = -9999; cursor.alvoY = -9999; };

    const ro = new ResizeObserver(redimensionar);
    ro.observe(el);
    const io = new IntersectionObserver(([e]) => { visivel = e.isIntersecting; });
    io.observe(el);
    redimensionar();
    if (!parado) {
      const pai = el.parentElement!;
      pai.addEventListener("pointermove", mover);
      pai.addEventListener("dragover", mover);
      pai.addEventListener("pointerleave", sair);
      quadro = requestAnimationFrame(laco);
      return () => {
        cancelAnimationFrame(quadro); ro.disconnect(); io.disconnect();
        pai.removeEventListener("pointermove", mover); pai.removeEventListener("dragover", mover); pai.removeEventListener("pointerleave", sair);
      };
    }
    return () => { ro.disconnect(); io.disconnect(); };
  }, []);

  return <canvas ref={canvas} className="pointer-events-none absolute inset-0 -z-10 h-full w-full" aria-hidden="true" />;
}
