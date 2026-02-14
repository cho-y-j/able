import "@testing-library/jest-dom";

// Mock i18n — always return English translations in tests
jest.mock("@/i18n", () => {
  const en = jest.requireActual("@/i18n/locales/en").default;
  return {
    __esModule: true,
    useI18n: () => ({ locale: "en" as const, setLocale: jest.fn(), t: en }),
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    I18nProvider: ({ children }: any) => children,
  };
});

// Mock next/navigation
jest.mock("next/navigation", () => ({
  useRouter: () => ({
    push: jest.fn(),
    replace: jest.fn(),
    back: jest.fn(),
    prefetch: jest.fn(),
  }),
  usePathname: () => "/dashboard",
  useSearchParams: () => new URLSearchParams(),
}));

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: jest.fn((key: string) => store[key] ?? null),
    setItem: jest.fn((key: string, value: string) => {
      store[key] = value;
    }),
    removeItem: jest.fn((key: string) => {
      delete store[key];
    }),
    clear: jest.fn(() => {
      store = {};
    }),
  };
})();

Object.defineProperty(window, "localStorage", { value: localStorageMock });
