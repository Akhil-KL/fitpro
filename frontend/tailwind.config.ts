import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: "#EDF0F3",
        surface: "#FFFFFF",
        ink: { DEFAULT: "#15213B", soft: "#4A5672", faint: "#8792A8" },
        line: "#D6DCE4",
        protein: "#2F5BEA",
        carbs: "#D99A1E",
        fat: "#2E9C86",
        water: "#3E8ED0",
        danger: "#C2412D",
      },
      fontFamily: {
        display: ["var(--font-display)", "system-ui", "sans-serif"],
        sans: ["var(--font-body)", "system-ui", "sans-serif"],
      },
      borderRadius: {
        bubble: "1.125rem",
      },
    },
  },
  plugins: [],
};

export default config;
