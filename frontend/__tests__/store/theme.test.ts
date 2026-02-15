import { useThemeStore, applyTheme } from "@/store/theme";
import { act } from "@testing-library/react";

// Mock matchMedia for jsdom
Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: jest.fn().mockImplementation((query: string) => ({
    matches: query === "(prefers-color-scheme: dark)",
    media: query,
    onchange: null,
    addListener: jest.fn(),
    removeListener: jest.fn(),
    addEventListener: jest.fn(),
    removeEventListener: jest.fn(),
    dispatchEvent: jest.fn(),
  })),
});

describe("useThemeStore", () => {
  beforeEach(() => {
    act(() => {
      useThemeStore.setState({ theme: "dark" });
    });
    document.documentElement.classList.remove("dark", "light");
    document.documentElement.removeAttribute("data-theme");
  });

  it("defaults to dark theme", () => {
    expect(useThemeStore.getState().theme).toBe("dark");
  });

  it("sets theme to light", () => {
    act(() => {
      useThemeStore.getState().setTheme("light");
    });
    expect(useThemeStore.getState().theme).toBe("light");
  });

  it("sets theme to system", () => {
    act(() => {
      useThemeStore.getState().setTheme("system");
    });
    expect(useThemeStore.getState().theme).toBe("system");
  });

  it("resolves dark theme", () => {
    act(() => {
      useThemeStore.setState({ theme: "dark" });
    });
    expect(useThemeStore.getState().resolvedTheme()).toBe("dark");
  });

  it("resolves light theme", () => {
    act(() => {
      useThemeStore.setState({ theme: "light" });
    });
    expect(useThemeStore.getState().resolvedTheme()).toBe("light");
  });
});

describe("applyTheme", () => {
  beforeEach(() => {
    document.documentElement.classList.remove("dark", "light");
    document.documentElement.removeAttribute("data-theme");
  });

  it("applies dark class to document", () => {
    applyTheme("dark");
    expect(document.documentElement.classList.contains("dark")).toBe(true);
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
  });

  it("applies light class to document", () => {
    applyTheme("light");
    expect(document.documentElement.classList.contains("light")).toBe(true);
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
  });

  it("removes previous theme class when switching", () => {
    applyTheme("dark");
    expect(document.documentElement.classList.contains("dark")).toBe(true);

    applyTheme("light");
    expect(document.documentElement.classList.contains("dark")).toBe(false);
    expect(document.documentElement.classList.contains("light")).toBe(true);
  });
});
