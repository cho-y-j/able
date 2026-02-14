"use client";

import { useState, useEffect } from "react";
import api from "@/lib/api";

const LLM_PROVIDERS = {
  openai: { name: "OpenAI", models: ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "o1", "o3-mini"] },
  anthropic: { name: "Anthropic", models: ["claude-opus-4-6", "claude-sonnet-4-5-20250929", "claude-haiku-4-5-20251001"] },
  google: { name: "Google", models: ["gemini-2.0-flash", "gemini-2.5-pro", "gemini-2.5-flash"] },
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
}

export default function SettingsPage() {
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

  const [message, setMessage] = useState("");

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
    setMessage("");
    try {
      await api.post("/keys/kis", {
        app_key: kisAppKey,
        app_secret: kisAppSecret,
        account_number: kisAccount,
        is_paper_trading: kisPaper,
      });
      setMessage("KIS credentials saved successfully!");
      setKisAppKey(""); setKisAppSecret(""); setKisAccount("");
      fetchKeys();
    } catch {
      setMessage("Failed to save KIS credentials");
    } finally {
      setKisLoading(false);
    }
  };

  const saveLLM = async (e: React.FormEvent) => {
    e.preventDefault();
    setLlmLoading(true);
    setMessage("");
    try {
      await api.post("/keys/llm", {
        provider_name: llmProvider,
        api_key: llmApiKey,
        model_name: llmModel,
      });
      setMessage("LLM API key saved successfully!");
      setLlmApiKey("");
      fetchKeys();
    } catch {
      setMessage("Failed to save LLM credentials");
    } finally {
      setLlmLoading(false);
    }
  };

  const validateKey = async (id: string) => {
    setMessage("");
    try {
      const { data } = await api.post(`/keys/${id}/validate`);
      setMessage(data.message);
      if (data.valid) fetchKeys();
    } catch {
      setMessage("Validation request failed");
    }
  };

  const deleteKey = async (id: string) => {
    await api.delete(`/keys/${id}`);
    fetchKeys();
  };

  const providerModels = LLM_PROVIDERS[llmProvider as keyof typeof LLM_PROVIDERS]?.models || [];

  return (
    <div className="max-w-3xl">
      <h2 className="text-2xl font-bold mb-6">Settings</h2>

      {message && (
        <div className={`mb-4 p-3 rounded-lg text-sm ${
          message.includes("success") ? "bg-green-900/30 text-green-400 border border-green-700" : "bg-red-900/30 text-red-400 border border-red-700"
        }`}>
          {message}
        </div>
      )}

      {/* Saved Keys */}
      {keys.length > 0 && (
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-6 mb-6">
          <h3 className="text-lg font-semibold mb-4">Saved API Keys</h3>
          <div className="space-y-3">
            {keys.map((key) => (
              <div key={key.id} className="flex items-center justify-between p-3 bg-gray-800 rounded-lg">
                <div>
                  <span className={`text-xs px-2 py-1 rounded mr-2 ${
                    key.service_type === "kis" ? "bg-orange-900/50 text-orange-400" : "bg-purple-900/50 text-purple-400"
                  }`}>
                    {key.service_type.toUpperCase()}
                  </span>
                  <span className="text-sm">{key.label}</span>
                  {key.model_name && <span className="text-xs text-gray-500 ml-2">{key.model_name}</span>}
                  <span className="text-xs text-gray-600 ml-2">{key.masked_key}</span>
                  {!key.is_active && <span className="text-xs text-gray-600 ml-2">(inactive)</span>}
                </div>
                <div className="flex items-center gap-2">
                  <button onClick={() => validateKey(key.id)} className="text-blue-400 hover:text-blue-300 text-sm">
                    Validate
                  </button>
                  <button onClick={() => deleteKey(key.id)} className="text-red-400 hover:text-red-300 text-sm">
                    Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* KIS API Configuration */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-6 mb-6">
        <h3 className="text-lg font-semibold mb-4">Korea Investment Securities API</h3>
        <p className="text-sm text-gray-500 mb-4">
          Enter your KIS Open API credentials. Get them from the KIS Developer Portal.
        </p>
        <form onSubmit={saveKIS} className="space-y-3">
          <input type="text" value={kisAppKey} onChange={(e) => setKisAppKey(e.target.value)}
            placeholder="App Key" className="w-full px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:border-blue-500" required />
          <input type="password" value={kisAppSecret} onChange={(e) => setKisAppSecret(e.target.value)}
            placeholder="App Secret" className="w-full px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:border-blue-500" required />
          <input type="text" value={kisAccount} onChange={(e) => setKisAccount(e.target.value)}
            placeholder="Account Number (e.g., 50123456-01)" className="w-full px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:border-blue-500" required />
          <label className="flex items-center gap-2 text-sm text-gray-400">
            <input type="checkbox" checked={kisPaper} onChange={(e) => setKisPaper(e.target.checked)}
              className="rounded bg-gray-800 border-gray-600" />
            Paper Trading (recommended for testing)
          </label>
          <button type="submit" disabled={kisLoading}
            className="px-6 py-2 bg-orange-600 hover:bg-orange-700 disabled:bg-gray-700 rounded-lg text-sm font-medium transition-colors">
            {kisLoading ? "Saving..." : "Save KIS Credentials"}
          </button>
        </form>
      </div>

      {/* LLM API Configuration */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
        <h3 className="text-lg font-semibold mb-4">LLM API Configuration</h3>
        <p className="text-sm text-gray-500 mb-4">
          Select your preferred AI model provider and enter your API key.
        </p>
        <form onSubmit={saveLLM} className="space-y-3">
          <div>
            <label className="block text-sm text-gray-400 mb-1">Provider</label>
            <select value={llmProvider} onChange={(e) => { setLlmProvider(e.target.value); setLlmModel(""); }}
              className="w-full px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:border-blue-500">
              {Object.entries(LLM_PROVIDERS).map(([key, val]) => (
                <option key={key} value={key}>{val.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Model</label>
            <select value={llmModel} onChange={(e) => setLlmModel(e.target.value)}
              className="w-full px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:border-blue-500">
              {providerModels.map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
          </div>
          <input type="password" value={llmApiKey} onChange={(e) => setLlmApiKey(e.target.value)}
            placeholder="API Key (e.g., sk-...)" className="w-full px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:border-blue-500" required />
          <button type="submit" disabled={llmLoading}
            className="px-6 py-2 bg-purple-600 hover:bg-purple-700 disabled:bg-gray-700 rounded-lg text-sm font-medium transition-colors">
            {llmLoading ? "Saving..." : "Save LLM API Key"}
          </button>
        </form>
      </div>
    </div>
  );
}
