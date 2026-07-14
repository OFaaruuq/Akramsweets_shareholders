/*
Template Name: Dusty - Responsive Bootstrap 5 Admin Dashboard
Author: Zoyothemes
Version: 1.0.0
Website: https://zoyothemes.com/
File: Main Js File
*/

const ThemeManager = (() => {
  const CONFIG_KEY = "__CONFIG__";
  const defaultConfig = { theme: "light" };
  const savedConfig = localStorage.getItem(CONFIG_KEY);
  const config = Object.assign({}, defaultConfig, JSON.parse(savedConfig || "{}"));

  let themeColorToggle = null;

  const saveState = () => {
    localStorage.setItem(CONFIG_KEY, JSON.stringify(config));
  };

  const changeThemeMode = (theme) => {
    document.documentElement.setAttribute("data-bs-theme", theme);
    config.theme = theme;
    saveState();
  };

  const toggleThemeHandler = () => {
    changeThemeMode(config.theme === "light" ? "dark" : "light");
  };

  const initTheme = () => {
    themeColorToggle = document.getElementById("light-dark-mode");
    if (themeColorToggle) {
      themeColorToggle.addEventListener("click", toggleThemeHandler);
    }
  };

  const cleanupTheme = () => {
    if (themeColorToggle) {
      themeColorToggle.removeEventListener("click", toggleThemeHandler);
    }
  };

  const onWindowLoad = () => initTheme();

  return {
    init: () => {
      changeThemeMode(config.theme);
      window.addEventListener("load", onWindowLoad);
    },
    destroy: () => {
      window.removeEventListener("load", onWindowLoad);
      cleanupTheme();
    },
  };
})();

// Usage
ThemeManager.init();