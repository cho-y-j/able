"use client";

import { useState, useEffect, useCallback } from "react";
import api from "@/lib/api";
import { useI18n } from "@/i18n";
import { formatKRW } from "@/lib/charts";

interface RankingEntry {
  rank: number;
  stock_code: string;
  stock_name: string;
  price: number;
  change_pct: number;
  volume: number;
}

interface ThemeInfo {
  name: string;
  stock_count: number;
  stocks: { code: string; name: string }[];
}

interface InterestStock {
  stock_code: string;
  stock_name: string;
  price: number;
  change_pct: number;
  volume: number;
  score: number;
  reasons: string[];
  themes: string[];
}

const TABS = ["price", "volume", "themes", "interest"] as const;
type TabKey = (typeof TABS)[number];

export default function RankingsPage() {
  const { t } = useI18n();
  const [tab, setTab] = useState<TabKey>("price");
  const [direction, setDirection] = useState<"up" | "down">("up");
  const [priceRankings, setPriceRankings] = useState<RankingEntry[]>([]);
  const [volumeRankings, setVolumeRankings] = useState<RankingEntry[]>([]);
  const [themes, setThemes] = useState<ThemeInfo[]>([]);
  const [interestStocks, setInterestStocks] = useState<InterestStock[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [priceRes, volumeRes, themeRes, interestRes] = await Promise.allSettled([
        api.get(`/rankings/price?direction=${direction}&limit=30`),
        api.get("/rankings/volume?limit=30"),
        api.get("/rankings/themes"),
        api.get("/rankings/interest?limit=20"),
      ]);

      if (priceRes.status === "fulfilled") setPriceRankings(priceRes.value.data);
      if (volumeRes.status === "fulfilled") setVolumeRankings(volumeRes.value.data);
      if (themeRes.status === "fulfilled") setThemes(themeRes.value.data);
      if (interestRes.status === "fulfilled") setInterestStocks(interestRes.value.data);
    } catch {
      // Individual fetches handled by allSettled
    } finally {
      setLoading(false);
    }
  }, [direction]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const tabLabels: Record<TabKey, string> = {
    price: t.rankings.priceRanking,
    volume: t.rankings.volumeRanking,
    themes: t.rankings.themeClassification,
    interest: t.rankings.interestStocks,
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">{t.rankings.title}</h1>
        <button
          onClick={fetchData}
          className="text-sm text-gray-400 hover:text-white transition-colors"
        >
          {t.autoTrading.refresh}
        </button>
      </div>

      {/* Tab Navigation */}
      <div className="flex gap-1 bg-gray-800 p-1 rounded-xl">
        {TABS.map((key) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`flex-1 py-2.5 rounded-lg text-sm font-medium transition-colors ${
              tab === key
                ? "bg-blue-600 text-white"
                : "text-gray-400 hover:text-white"
            }`}
          >
            {tabLabels[key]}
          </button>
        ))}
      </div>

      {/* Content */}
      {loading ? (
        <div className="space-y-3 animate-pulse">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="h-12 bg-gray-800 rounded-lg" />
          ))}
        </div>
      ) : (
        <>
          {/* Price Rankings */}
          {tab === "price" && (
            <div className="space-y-4">
              <div className="flex gap-2">
                <button
                  onClick={() => setDirection("up")}
                  className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                    direction === "up"
                      ? "bg-green-600 text-white"
                      : "bg-gray-800 text-gray-400 hover:text-white"
                  }`}
                >
                  {t.rankings.gainers}
                </button>
                <button
                  onClick={() => setDirection("down")}
                  className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                    direction === "down"
                      ? "bg-red-600 text-white"
                      : "bg-gray-800 text-gray-400 hover:text-white"
                  }`}
                >
                  {t.rankings.losers}
                </button>
              </div>
              <RankingTable data={priceRankings} t={t} />
            </div>
          )}

          {/* Volume Rankings */}
          {tab === "volume" && (
            <RankingTable data={volumeRankings} t={t} />
          )}

          {/* Themes */}
          {tab === "themes" && (
            <div>
              {themes.length === 0 ? (
                <EmptyState message={t.rankings.noThemes} />
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                  {themes.map((theme) => (
                    <div
                      key={theme.name}
                      className="bg-gray-800 border border-gray-700 rounded-xl p-4 hover:border-blue-500/50 transition-colors"
                    >
                      <div className="flex items-center justify-between mb-3">
                        <h3 className="text-white font-semibold text-sm">{theme.name}</h3>
                        <span className="text-xs text-gray-500">
                          {theme.stock_count}{t.rankings.stockCount}
                        </span>
                      </div>
                      <div className="space-y-1">
                        {theme.stocks.map((s) => (
                          <div
                            key={s.code}
                            className="flex items-center justify-between bg-gray-900 rounded-lg px-3 py-1.5"
                          >
                            <span className="text-xs text-gray-300">{s.name}</span>
                            <span className="text-[10px] text-gray-500 font-mono">{s.code}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Interest Stocks */}
          {tab === "interest" && (
            <div>
              {interestStocks.length === 0 ? (
                <EmptyState message={t.rankings.noInterest} />
              ) : (
                <div className="space-y-3">
                  {interestStocks.map((stock) => (
                    <div
                      key={stock.stock_code}
                      className="bg-gray-800 border border-gray-700 rounded-xl p-4 hover:border-blue-500/50 transition-colors"
                    >
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-3">
                          <div className="bg-blue-600 text-white text-sm font-bold w-10 h-10 rounded-lg flex items-center justify-center">
                            {stock.score}
                          </div>
                          <div>
                            <p className="text-white font-semibold text-sm">
                              {stock.stock_name}
                              <span className="text-gray-500 font-mono text-xs ml-2">
                                {stock.stock_code}
                              </span>
                            </p>
                            <p className="text-xs text-gray-400">
                              {formatKRW(stock.price)}{" "}
                              <span
                                className={stock.change_pct >= 0 ? "text-green-400" : "text-red-400"}
                              >
                                {stock.change_pct >= 0 ? "+" : ""}
                                {stock.change_pct.toFixed(2)}%
                              </span>
                            </p>
                          </div>
                        </div>
                        <div className="flex gap-1 flex-wrap justify-end">
                          {stock.themes.map((t) => (
                            <span
                              key={t}
                              className="text-[10px] px-2 py-0.5 rounded-full bg-blue-900/40 text-blue-400"
                            >
                              {t}
                            </span>
                          ))}
                        </div>
                      </div>
                      <div className="flex gap-1 flex-wrap">
                        {stock.reasons.map((r, i) => (
                          <span
                            key={i}
                            className="text-[10px] px-2 py-0.5 rounded bg-gray-700 text-gray-300"
                          >
                            {r}
                          </span>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}

function RankingTable({
  data,
  t,
}: {
  data: RankingEntry[];
  t: ReturnType<typeof useI18n>["t"];
}) {
  if (data.length === 0) {
    return <EmptyState message={t.rankings.noData} />;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-gray-500 uppercase border-b border-gray-700 text-xs">
            <th className="text-left py-2 px-3">#</th>
            <th className="text-left py-2 px-3">{t.common.stock}</th>
            <th className="text-right py-2 px-3">{t.common.price}</th>
            <th className="text-right py-2 px-3">{t.rankings.changePct}</th>
            <th className="text-right py-2 px-3">{t.rankings.volume}</th>
          </tr>
        </thead>
        <tbody>
          {data.map((item) => (
            <tr
              key={item.stock_code}
              className="border-b border-gray-700/50 hover:bg-gray-700/30"
            >
              <td className="py-2.5 px-3 text-gray-400 font-mono">{item.rank}</td>
              <td className="py-2.5 px-3">
                <span className="text-white font-medium">{item.stock_name}</span>
                <span className="text-gray-500 font-mono text-xs ml-2">{item.stock_code}</span>
              </td>
              <td className="py-2.5 px-3 text-right text-gray-300 font-mono">
                {formatKRW(item.price)}
              </td>
              <td
                className={`py-2.5 px-3 text-right font-mono ${
                  item.change_pct >= 0 ? "text-green-400" : "text-red-400"
                }`}
              >
                {item.change_pct >= 0 ? "+" : ""}
                {item.change_pct.toFixed(2)}%
              </td>
              <td className="py-2.5 px-3 text-right text-gray-400 font-mono">
                {(item.volume / 1000).toFixed(0)}K
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function EmptyState({ message }: { message: string }) {
  return (
    <div className="text-center py-12 bg-gray-800/50 rounded-xl border border-gray-700 border-dashed">
      <p className="text-gray-400 text-sm">{message}</p>
    </div>
  );
}
