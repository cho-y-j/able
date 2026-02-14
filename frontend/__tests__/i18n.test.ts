import en from "@/i18n/locales/en";
import ko from "@/i18n/locales/ko";
import type { Translations } from "@/i18n/locales/en";

function getAllKeys(obj: Record<string, unknown>, prefix = ""): string[] {
  const keys: string[] = [];
  for (const key of Object.keys(obj)) {
    const fullKey = prefix ? `${prefix}.${key}` : key;
    const value = obj[key];
    if (typeof value === "object" && value !== null) {
      keys.push(...getAllKeys(value as Record<string, unknown>, fullKey));
    } else {
      keys.push(fullKey);
    }
  }
  return keys;
}

describe("i18n translations", () => {
  it("en and ko have the same keys", () => {
    const enKeys = getAllKeys(en as unknown as Record<string, unknown>).sort();
    const koKeys = getAllKeys(ko as unknown as Record<string, unknown>).sort();
    expect(enKeys).toEqual(koKeys);
  });

  it("no empty translation values in en", () => {
    const enKeys = getAllKeys(en as unknown as Record<string, unknown>);
    for (const key of enKeys) {
      const value = key.split(".").reduce(
        (o: Record<string, unknown>, k) => (o as Record<string, unknown>)[k] as Record<string, unknown>,
        en as unknown as Record<string, unknown>
      );
      expect(value).toBeTruthy();
    }
  });

  it("no empty translation values in ko", () => {
    const koKeys = getAllKeys(ko as unknown as Record<string, unknown>);
    for (const key of koKeys) {
      const value = key.split(".").reduce(
        (o: Record<string, unknown>, k) => (o as Record<string, unknown>)[k] as Record<string, unknown>,
        ko as unknown as Record<string, unknown>
      );
      expect(value).toBeTruthy();
    }
  });

  it("has all required namespaces", () => {
    const namespaces: (keyof Translations)[] = [
      "common", "nav", "auth", "dashboard", "market", "strategies",
      "backtests", "trading", "paper", "portfolio", "risk", "agents",
      "notifications", "settings",
    ];
    for (const ns of namespaces) {
      expect(en[ns]).toBeDefined();
      expect(ko[ns]).toBeDefined();
    }
  });

  it("translations have significant content", () => {
    const enKeys = getAllKeys(en as unknown as Record<string, unknown>);
    expect(enKeys.length).toBeGreaterThan(200);

    const koKeys = getAllKeys(ko as unknown as Record<string, unknown>);
    expect(koKeys.length).toBeGreaterThan(200);
  });

  it("ko translations contain Korean characters", () => {
    const koreanRegex = /[\uAC00-\uD7AF]/;
    expect(koreanRegex.test(ko.auth.login)).toBe(true);
    expect(koreanRegex.test(ko.dashboard.welcome)).toBe(true);
    expect(koreanRegex.test(ko.nav.dashboard)).toBe(true);
    expect(koreanRegex.test(ko.settings.title)).toBe(true);
  });
});
