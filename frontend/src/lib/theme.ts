import type { Theme } from "./api/types";

export const THEME_KEY = "pv-theme";

/** Inline script run before paint so the theme never flashes. Keep dependency-free. */
export const THEME_INIT_SCRIPT = `(function(){try{var t=localStorage.getItem(${JSON.stringify(THEME_KEY)});if(t==="light"||t==="dark"){document.documentElement.setAttribute("data-theme",t);}else{document.documentElement.removeAttribute("data-theme");}}catch(e){}})();`;

export function applyTheme(theme: Theme): void {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  if (theme === "light" || theme === "dark") root.setAttribute("data-theme", theme);
  else root.removeAttribute("data-theme");
  try {
    if (theme === "system") localStorage.removeItem(THEME_KEY);
    else localStorage.setItem(THEME_KEY, theme);
  } catch {
    /* storage unavailable */
  }
}
