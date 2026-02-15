"use client";

import { useState, useEffect } from "react";
import api from "@/lib/api";
import { useI18n } from "@/i18n";

const LLM_PROVIDERS = {
  openai: { name: "OpenAI", models: ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "o1", "o3-mini"] },
  anthropic: { name: "Anthropic", models: ["claude-opus-4-6", "claude-sonnet-4-5-20250929", "claude-haiku-4-5-20251001"] },
  google: { name: "Google", models: ["gemini-2.0-flash", "gemini-2.5-pro", "gemini-2.5-flash"] },
  deepseek: { name: "DeepSeek", models: ["deepseek-chat", "deepseek-reasoner"] },
};

interface ApiKey {
  id: string;
  service_type: string;
  provider_name: string;
  label: string | null;
  model_name: string | null;
  is_active: boolean;
  is_paper_trading: boolean;
  masked_key: string;
  last_validated_at: string | null;
  account_number: string | null;
}

type MessageType = { text: string; type: "success" | "error" } | null;

function formatRelativeTime(ts: string): string {
  const diff = Date.now() - new Date(ts).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export default function SettingsPage() {
  const { t } = useI18n();
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [loading, setLoading] = useState(true);

  // KIS form
  const [kisAppKey, setKisAppKey] = useState("");
  const [kisAppSecret, setKisAppSecret] = useState("");
  const [kisAccount, setKisAccount] = useState("");
  const [kisPaper, setKisPaper] = useState(true);
  const [kisLoading, setKisLoading] = useState(false);

  // LLM form
  const [llmProvider, setLlmProvider] = useState("openai");
  const [llmApiKey, setLlmApiKey] = useState("");
  const [llmModel, setLlmModel] = useState("gpt-4o");
  const [llmLoading, setLlmLoading] = useState(false);

  const [message, setMessage] = useState<MessageType>(null);
  const [validatingId, setValidatingId] = useState<string | null>(null);

  const showSuccess = (text: string) => {
    setMessage({ text, type: "success" });
    setTimeout(() => setMessage(null), 5000);
  };

  const showError = (text: string) => {
    setMessage({ text, type: "error" });
    setTimeout(() => setMessage(null), 8000);
  };

  const getErrorDetail = (err: unknown): string => {
    const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
    return detail || "Unknown error";
  };

  const fetchKeys = async () => {
    try {
      const { data } = await api.get("/keys");
      setKeys(data.keys);
    } catch {
      // handle error
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchKeys(); }, []);

  const saveKIS = async (e: React.FormEvent) => {
    e.preventDefault();
    setKisLoading(true);
    setMessage(null);
    try {
      await api.post("/keys/kis", {
        app_key: kisAppKey,
        app_secret: kisAppSecret,
        account_number: kisAccount,
        is_paper_trading: kisPaper,
      });
      showSuccess(t.settings.kisSaved);
      setKisAppKey(""); setKisAppSecret(""); setKisAccount("");
      fetchKeys();
    } catch (err) {
      showError(`${t.settings.kisFailed}: ${getErrorDetail(err)}`);
    } finally {
      setKisLoading(false);
    }
  };

  const saveLLM = async (e: React.FormEvent) => {
    e.preventDefault();
    setLlmLoading(true);
    setMessage(null);
    try {
      await api.post("/keys/llm", {
        provider_name: llmProvider,
        api_key: llmApiKey,
        model_name: llmModel,
      });
      showSuccess(t.settings.llmSaved);
      setLlmApiKey("");
      fetchKeys();
    } catch (err) {
      showError(`${t.settings.llmFailed}: ${getErrorDetail(err)}`);
    } finally {
      setLlmLoading(false);
    }
  };

  const validateKey = async (id: string) => {
    setMessage(null);
    setValidatingId(id);
    try {
      const { data } = await api.post(`/keys/${id}/validate`);
      if (data.valid) {
        showSuccess(t.settings.validateSuccess);
        fetchKeys();
      } else {
        showError(`${t.settings.validateFailed}: ${data.message || "Invalid key"}`);
      }
    } catch (err) {
      showError(`${t.settings.validateFailed}: ${getErrorDetail(err)}`);
    } finally {
      setValidatingId(null);
    }
  };

  const deleteKey = async (id: string) => {
    if (!confirm(t.settings.deleteConfirm)) return;
    try {
      await api.delete(`/keys/${id}`);
      showSuccess(t.settings.deleteSuccess);
      fetchKeys();
    } catch (err) {
      showError(`${t.settings.deleteFailed}: ${getErrorDetail(err)}`);
    }
  };

  const providerModels = LLM_PROVIDERS[llmProvider as keyof typeof LLM_PROVIDERS]?.models || [];

  return (
    <div className="max-w-3xl">
      <h2 className="text-2xl font-bold mb-6">{t.settings.title}</h2>

      {/* Toast message */}
      {message && (
        <div className={`mb-4 p-4 rounded-lg text-sm font-medium flex items-center gap-2 ${
          message.type === "success"
            ? "bg-green-900/40 text-green-400 border border-green-700"
            : "bg-red-900/40 text-red-400 border border-red-700"
        }`}>
          <span className="text-lg">{message.type === "success" ? "\u2713" : "\u2715"}</span>
          {message.text}
        </div>
      )}

      {/* Saved Keys */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-6 mb-6">
        <h3 className="text-lg font-semibold mb-4">{t.settings.savedKeys}</h3>
        {loading ? (
          <p className="text-gray-500 text-sm">{t.common.loading}</p>
        ) : keys.length > 0 ? (
          <div className="space-y-3">
            {keys.map((key) => (
              <div key={key.id} className="p-4 bg-gray-800 rounded-lg">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className={`text-xs px-2 py-1 rounded ${
                      key.service_type === "kis" ? "bg-orange-900/50 text-orange-400" : "bg-purple-900/50 text-purple-400"
                    }`}>
                      {key.service_type.toUpperCase()}
                    </span>
                    <span className="text-sm text-gray-200">{key.label || key.provider_name}</span>
                    {key.model_name && <span className="text-xs text-gray-500">{key.model_name}</span>}
                    {key.is_active ? (
                      <span className="text-xs text-green-500">Active</span>
                    ) : (
                      <span className="text-xs text-gray-600">{t.settings.inactive}</span>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => validateKey(key.id)}
                      disabled={validatingId === key.id}
                      className="text-blue-400 hover:text-blue-300 text-sm disabled:text-gray-600"
                    >
                      {validatingId === key.id ? t.settings.testing : t.settings.testConnection}
                    </button>
                    <button onClick={() => deleteKey(key.id)} className="text-red-400 hover:text-red-300 text-sm">
                      {t.common.delete}
                    </button>
                  </div>
                </div>
                <div className="flex items-center gap-3 mt-2 text-xs">
                  <span className="text-gray-500">{key.masked_key}</span>
                  {key.service_type === "kis" && key.account_number && (
                    <span className="text-gray-500">{t.settings.account}: {key.account_number}</span>
                  )}
                  {key.last_validated_at ? (
                    <span className="flex items-center gap-1 text-green-500">
                      <span className="w-1.5 h-1.5 rounded-full bg-green-500" />
                      {t.settings.verified} · {formatRelativeTime(key.last_validated_at)}
                    </span>
                  ) : (
                    <span className="flex items-center gap-1 text-yellow-500">
                      <span className="w-1.5 h-1.5 rounded-full bg-yellow-500" />
                      {t.settings.notVerified}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-gray-500 text-sm">{t.settings.noKeys}</p>
        )}
      </div>

      {/* KIS API Configuration */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-6 mb-6">
        <h3 className="text-lg font-semibold mb-2">{t.settings.kisTitle}</h3>
        <p className="text-sm text-gray-500 mb-4">
          {t.settings.kisDesc}
        </p>
        <form onSubmit={saveKIS} className="space-y-3">
          <div>
            <label htmlFor="kis-app-key" className="block text-sm text-gray-400 mb-1">{t.settings.appKey}</label>
            <input id="kis-app-key" type="text" value={kisAppKey} onChange={(e) => setKisAppKey(e.target.value)}
              placeholder={t.settings.kisAppKeyPlaceholder}
              className="w-full px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:border-blue-500" required />
          </div>
          <div>
            <label htmlFor="kis-app-secret" className="block text-sm text-gray-400 mb-1">{t.settings.appSecret}</label>
            <input id="kis-app-secret" type="password" value={kisAppSecret} onChange={(e) => setKisAppSecret(e.target.value)}
              placeholder={t.settings.kisAppSecretPlaceholder}
              className="w-full px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:border-blue-500" required />
          </div>
          <div>
            <label htmlFor="kis-account" className="block text-sm text-gray-400 mb-1">{t.settings.accountNumber}</label>
            <input id="kis-account" type="text" value={kisAccount} onChange={(e) => setKisAccount(e.target.value)}
              placeholder={t.settings.accountPlaceholder}
              className="w-full px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:border-blue-500" required />
          </div>
          <label className="flex items-center gap-2 text-sm text-gray-400">
            <input type="checkbox" checked={kisPaper} onChange={(e) => setKisPaper(e.target.checked)}
              className="rounded bg-gray-800 border-gray-600" />
            {t.settings.paperTrading}
          </label>
          <button type="submit" disabled={kisLoading}
            className="w-full py-3 bg-orange-600 hover:bg-orange-700 disabled:bg-gray-700 rounded-lg text-sm font-bold transition-colors">
            {kisLoading ? t.settings.saving : t.settings.saveKis}
          </button>
        </form>
      </div>

      {/* LLM API Configuration */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
        <h3 className="text-lg font-semibold mb-2">{t.settings.llmTitle}</h3>
        <p className="text-sm text-gray-500 mb-4">
          {t.settings.llmDesc}
        </p>
        <form onSubmit={saveLLM} className="space-y-3">
          <div>
            <label htmlFor="llm-provider" className="block text-sm text-gray-400 mb-1">{t.settings.provider}</label>
            <select id="llm-provider" value={llmProvider} onChange={(e) => {
              setLlmProvider(e.target.value);
              const models = LLM_PROVIDERS[e.target.value as keyof typeof LLM_PROVIDERS]?.models || [];
              setLlmModel(models[0] || "");
            }}
              className="w-full px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:border-blue-500">
              {Object.entries(LLM_PROVIDERS).map(([key, val]) => (
                <option key={key} value={key}>{val.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="llm-model" className="block text-sm text-gray-400 mb-1">{t.settings.model}</label>
            <select id="llm-model" value={llmModel} onChange={(e) => setLlmModel(e.target.value)}
              className="w-full px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:border-blue-500">
              {providerModels.map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="llm-api-key" className="block text-sm text-gray-400 mb-1">{t.settings.apiKeyPlaceholder}</label>
            <input id="llm-api-key" type="password" value={llmApiKey} onChange={(e) => setLlmApiKey(e.target.value)}
              placeholder={t.settings.llmApiKeyPlaceholder}
              className="w-full px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:border-blue-500" required />
          </div>
          <button type="submit" disabled={llmLoading}
            className="w-full py-3 bg-purple-600 hover:bg-purple-700 disabled:bg-gray-700 rounded-lg text-sm font-bold transition-colors">
            {llmLoading ? t.settings.saving : t.settings.saveLlm}
          </button>
        </form>
      </div>
    </div>
  );
}
