import type { Config } from "tailwindcss";

/**
 * LandTrust Connect design tokens.
 *
 * The palette is deliberately institutional rather than fashionable: deep navy for
 * structure, emerald for evidence, and a small set of status hues that mean exactly
 * one thing each throughout the product. A colour is never used decoratively — if
 * something is amber on this platform, it is amber because the evidence says so.
 */
const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        navy: {
          50: "#f2f5fa",
          100: "#e3e9f4",
          200: "#c5d1e6",
          300: "#9aaed2",
          400: "#6a85b8",
          500: "#48649d",
          600: "#354d81",
          700: "#2a3d68",
          800: "#1c2b4d",
          900: "#0f1c38",
          950: "#08122a",
        },
        emerald: {
          50: "#eefbf5",
          100: "#d5f5e6",
          200: "#aeead1",
          300: "#78d9b4",
          400: "#42c093",
          500: "#1fa678",
          600: "#128561",
          700: "#0f6a4f",
          800: "#105441",
          900: "#0f4637",
          950: "#052720",
        },
        canvas: {
          DEFAULT: "#f7f9fc",
          raised: "#ffffff",
          sunken: "#eef2f8",
          border: "#dde5f0",
          borderStrong: "#c3d0e2",
        },
        ink: {
          DEFAULT: "#0f1c38",
          muted: "#54627d",
          subtle: "#7f8ca5",
          inverse: "#f4f7fb",
        },
        // Status hues. One meaning each, product-wide.
        status: {
          verified: "#0f8a5f",
          verifiedBg: "#e7f7ef",
          partial: "#b7791f",
          partialBg: "#fdf5e3",
          conflicting: "#c62828",
          conflictingBg: "#fdecec",
          pending: "#5c6b85",
          pendingBg: "#eef1f7",
          expired: "#8a5a1f",
          expiredBg: "#f9efe2",
          owner: "#5b4bb8",
          ownerBg: "#efecfb",
          info: "#1f6fb2",
          infoBg: "#e8f2fb",
        },
        risk: {
          low: "#0f8a5f",
          lowBg: "#e7f7ef",
          moderate: "#b7791f",
          moderateBg: "#fdf5e3",
          high: "#d2691e",
          highBg: "#fdefe3",
          critical: "#c62828",
          criticalBg: "#fdecec",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "-apple-system", "Segoe UI",
               "Roboto", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "monospace"],
      },
      fontSize: {
        "2xs": ["0.6875rem", { lineHeight: "1rem", letterSpacing: "0.02em" }],
      },
      borderRadius: {
        xl: "0.875rem",
        "2xl": "1.125rem",
        "3xl": "1.5rem",
      },
      boxShadow: {
        card: "0 1px 2px rgba(15, 28, 56, 0.04), 0 4px 16px -6px rgba(15, 28, 56, 0.10)",
        raised: "0 2px 6px rgba(15, 28, 56, 0.06), 0 12px 32px -12px rgba(15, 28, 56, 0.18)",
        drawer: "-12px 0 48px -16px rgba(15, 28, 56, 0.28)",
        inset: "inset 0 1px 2px rgba(15, 28, 56, 0.05)",
      },
      backgroundImage: {
        "hero-grid":
          "linear-gradient(to right, rgba(255,255,255,0.045) 1px, transparent 1px), " +
          "linear-gradient(to bottom, rgba(255,255,255,0.045) 1px, transparent 1px)",
        "navy-fade": "linear-gradient(160deg, #0f1c38 0%, #16294b 45%, #0d2a3f 100%)",
      },
      keyframes: {
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(6px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "fade-in": { "0%": { opacity: "0" }, "100%": { opacity: "1" } },
        shimmer: {
          "0%": { backgroundPosition: "-600px 0" },
          "100%": { backgroundPosition: "600px 0" },
        },
        "pulse-ring": {
          "0%": { transform: "scale(0.9)", opacity: "0.7" },
          "70%": { transform: "scale(1.35)", opacity: "0" },
          "100%": { transform: "scale(1.35)", opacity: "0" },
        },
        "draw-line": { "0%": { strokeDashoffset: "1" }, "100%": { strokeDashoffset: "0" } },
      },
      animation: {
        "fade-up": "fade-up 0.35s cubic-bezier(0.22, 1, 0.36, 1) both",
        "fade-in": "fade-in 0.4s ease both",
        shimmer: "shimmer 1.6s linear infinite",
        "pulse-ring": "pulse-ring 2s cubic-bezier(0.4, 0, 0.6, 1) infinite",
      },
    },
  },
  plugins: [],
};

export default config;
