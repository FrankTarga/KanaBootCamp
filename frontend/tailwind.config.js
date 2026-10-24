/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      // Paleta inspirada na Kanastra: verde-floresta e creme quente. Sobrescrever emerald/teal/slate
      // recolore de uma vez todos os componentes que já usam essas classes.
      colors: {
        emerald: {
          50: "#EEF5F0", 100: "#D6EADD", 200: "#AFD5BF", 300: "#80BC9C", 400: "#4FA077",
          500: "#2B875D", 600: "#18704B", 700: "#105A3D", 800: "#0D4934", 900: "#0A3A2A", 950: "#062219",
        },
        teal: {
          50: "#EDF5F2", 100: "#D3E8E0", 200: "#A9D2C3", 300: "#78B6A0", 400: "#47967C",
          500: "#2A7A61", 600: "#1B624E", 700: "#134E3F", 800: "#0F3F33", 900: "#0B3128", 950: "#061C17",
        },
        slate: {
          50: "#F7F3EA", 100: "#EFE9DC", 200: "#E2DACA", 300: "#CFC5B1", 400: "#A39A86",
          500: "#7B7464", 600: "#5E594C", 700: "#45443A", 800: "#2E322B", 900: "#1C2420", 950: "#0F1512",
        },
        floresta: { DEFAULT: "#0B3B2C", escura: "#06231A", painel: "#0E4A37", linha: "#1C5E49" },
        creme: { DEFAULT: "#F4EFE4", claro: "#FAF7F0", linha: "#E3DBC9" },
        broto: "#2FB36F",
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"],
        display: ["Outfit", "Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      boxShadow: {
        card: "0 1px 2px 0 rgb(15 23 42 / 0.04), 0 1px 3px 0 rgb(15 23 42 / 0.06)",
        elevated: "0 10px 30px -12px rgb(15 23 42 / 0.25), 0 4px 10px -6px rgb(15 23 42 / 0.12)",
        glow: "0 0 0 1px rgb(47 179 111 / 0.25), 0 10px 40px -10px rgb(16 90 61 / 0.55)",
        "glow-violet": "0 0 0 1px rgb(139 92 246 / 0.3), 0 8px 30px -8px rgb(139 92 246 / 0.6)",
      },
      keyframes: {
        "fade-in-up": {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "fade-in": {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        "slide-in-right": {
          "0%": { transform: "translateX(100%)" },
          "100%": { transform: "translateX(0)" },
        },
        "expand-down": {
          "0%": { opacity: "0", transform: "translateY(-4px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        "pulse-ring": {
          "0%": { boxShadow: "0 0 0 0 rgb(225 29 72 / 0.55)" },
          "70%": { boxShadow: "0 0 0 10px rgb(225 29 72 / 0)" },
          "100%": { boxShadow: "0 0 0 0 rgb(225 29 72 / 0)" },
        },
        "scan-line": {
          "0%": { transform: "translateX(-100%)" },
          "100%": { transform: "translateX(400%)" },
        },
      },
      animation: {
        "fade-in-up": "fade-in-up 0.45s cubic-bezier(0.16, 1, 0.3, 1) both",
        "fade-in": "fade-in 0.3s ease-out both",
        "slide-in-right": "slide-in-right 0.35s cubic-bezier(0.16, 1, 0.3, 1) both",
        "expand-down": "expand-down 0.25s ease-out both",
        shimmer: "shimmer 2.5s linear infinite",
        "pulse-ring": "pulse-ring 1.8s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "scan-line": "scan-line 1.4s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
