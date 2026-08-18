import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        border: "hsl(var(--edge) / <alpha-value>)",
        input: "hsl(var(--edge-strong) / <alpha-value>)",
        ring: "hsl(var(--accent) / <alpha-value>)",
        background: "hsl(var(--background) / <alpha-value>)",
        foreground: "hsl(var(--fg) / <alpha-value>)",
        surface: "hsl(var(--surface) / <alpha-value>)",
        card: {
          DEFAULT: "hsl(var(--card) / <alpha-value>)",
          foreground: "hsl(var(--fg) / <alpha-value>)",
        },
        elevated: "hsl(var(--elevated) / <alpha-value>)",
        edge: "hsl(var(--edge) / <alpha-value>)",
        "edge-strong": "hsl(var(--edge-strong) / <alpha-value>)",
        fg: "hsl(var(--fg) / <alpha-value>)",
        muted: {
          DEFAULT: "hsl(var(--surface) / <alpha-value>)",
          foreground: "hsl(var(--muted) / <alpha-value>)",
        },
        subtle: "hsl(var(--subtle) / <alpha-value>)",
        primary: {
          DEFAULT: "hsl(var(--accent) / <alpha-value>)",
          foreground: "hsl(var(--accent-fg) / <alpha-value>)",
        },
        secondary: {
          DEFAULT: "hsl(var(--elevated) / <alpha-value>)",
          foreground: "hsl(var(--fg) / <alpha-value>)",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive) / <alpha-value>)",
          foreground: "hsl(var(--destructive-fg) / <alpha-value>)",
        },
        accent: {
          DEFAULT: "hsl(var(--accent) / <alpha-value>)",
          hover: "hsl(var(--accent-hover) / <alpha-value>)",
          foreground: "hsl(var(--accent-fg) / <alpha-value>)",
        },
        mind: {
          DEFAULT: "hsl(var(--mind) / <alpha-value>)",
          foreground: "hsl(var(--mind-fg) / <alpha-value>)",
        },
        insight: "hsl(var(--insight) / <alpha-value>)",
      },
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "sans-serif"],
        display: ["var(--font-space)", "var(--font-inter)", "sans-serif"],
      },
      borderRadius: {
        xl: "0.875rem",
        "2xl": "1.125rem",
      },
      keyframes: {
        "fade-up": {
          from: { opacity: "0", transform: "translateY(8px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        "fade-up": "fade-up 0.4s ease-out both",
      },
    },
  },
  plugins: [],
};

export default config;
