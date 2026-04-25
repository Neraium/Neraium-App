/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        mono: ["JetBrains Mono", "Fira Code", "ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      colors: {
        ink: { 950: "#050505", 900: "#0A0A0A", 800: "#121212", 700: "#1c1c1c" },
      },
      animation: {
        "fade-in": "fadeIn 240ms ease-out both",
        "pulse-soft": "pulseSoft 2s cubic-bezier(.4,0,.6,1) infinite",
      },
      keyframes: {
        fadeIn: { "0%": { opacity: 0, transform: "translateY(4px)" }, "100%": { opacity: 1, transform: "none" } },
        pulseSoft: { "0%,100%": { opacity: 1 }, "50%": { opacity: 0.55 } },
      },
    },
  },
  plugins: [],
};
