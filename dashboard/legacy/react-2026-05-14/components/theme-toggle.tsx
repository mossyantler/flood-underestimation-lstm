"use client";

import { Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";

const STORAGE_KEY = "camels-dashboard-theme-v1";

type Theme = "light" | "dark";

function applyTheme(theme: Theme) {
  document.documentElement.dataset.theme = theme;
  document.documentElement.style.colorScheme = theme;
  try {
    localStorage.setItem(STORAGE_KEY, theme);
  } catch (_) {}
}

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>("light");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const currentTheme =
      document.documentElement.dataset.theme === "dark" ? "dark" : "light";
    setTheme(currentTheme);
    setMounted(true);
  }, []);

  function toggleTheme() {
    const nextTheme = theme === "dark" ? "light" : "dark";
    applyTheme(nextTheme);
    setTheme(nextTheme);
  }

  const nextLabel = theme === "dark" ? "라이트" : "다크";

  return (
    <button
      type="button"
      className="theme-toggle"
      aria-label={`${nextLabel} 모드로 전환`}
      onClick={toggleTheme}
    >
      {theme === "dark" ? <Sun size={15} /> : <Moon size={15} />}
      <span>{mounted ? nextLabel : "테마"}</span>
    </button>
  );
}
