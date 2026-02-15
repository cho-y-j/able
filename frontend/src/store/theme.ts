import { create } from "zustand";
import { persist } from "zustand/middleware";

export type Theme = "dark" | "light" | "system";

interface ThemeState {
  theme: Theme;
  setTheme: (theme: Theme) => void;
  resolvedTheme: () => "dark" | "light";
}

export const useThemeStore = create<ThemeState>()(
  persist(
    (set, get) => ({
      theme: "dark",
      setTheme: (theme: Theme) => {
        set({ theme });
        applyTheme(theme);
      },
      resolvedTheme: () => {
        const { theme } = get();
        if (theme === "system") {
          if (typeof window !== "undefined") {
            return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
          }
          return "dark";
        }
        return theme;
      },
    }),
    {
      name: "able-theme",
    },
  ),
);

export function applyTheme(theme: Theme) {
  if (typeof document === "undefined") return;

  const resolved =
    theme === "system"
      ? window.matchMedia("(prefers-color-scheme: dark)").matches
        ? "dark"
        : "light"
      : theme;

  document.documentElement.classList.remove("dark", "light");
  document.documentElement.classList.add(resolved);
  document.documentElement.setAttribute("data-theme", resolved);
}
