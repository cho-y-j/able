"use client";

import { useState, useMemo } from "react";

interface Trade {
  entry_date: string;
  exit_date: string;
  entry_price: number;
  exit_price: number;
  pnl_percent: number;
  hold_days: number;
}

interface TradeLogTabProps {
  tradeLog: Trade[];
}

type SortField =
  | "index"
  | "entry_date"
  | "exit_date"
  | "entry_price"
  | "exit_price"
  | "pnl_percent"
  | "hold_days";
type SortDir = "asc" | "desc";

const PAGE_SIZE = 20;

export default function TradeLogTab({ tradeLog }: TradeLogTabProps) {
  const [sortField, setSortField] = useState<SortField>("index");
  const [sortDir, setSortDir] = useState<SortDir>("asc");
  const [page, setPage] = useState(0);

  // Summary statistics
  const stats = useMemo(() => {
    if (!tradeLog || tradeLog.length === 0) return null;
    const wins = tradeLog.filter((t) => t.pnl_percent >= 0);
    const losses = tradeLog.filter((t) => t.pnl_percent < 0);
    const avgWin =
      wins.length > 0
        ? wins.reduce((s, t) => s + t.pnl_percent, 0) / wins.length
        : 0;
    const avgLoss =
      losses.length > 0
        ? losses.reduce((s, t) => s + t.pnl_percent, 0) / losses.length
        : 0;
    const best = Math.max(...tradeLog.map((t) => t.pnl_percent));
    const worst = Math.min(...tradeLog.map((t) => t.pnl_percent));
    return {
      total: tradeLog.length,
      wins: wins.length,
      losses: losses.length,
      avgWin,
      avgLoss,
      best,
      worst,
      winRate: (wins.length / tradeLog.length) * 100,
    };
  }, [tradeLog]);

  // Sorted data
  const sortedTrades = useMemo(() => {
    if (!tradeLog) return [];
    const indexed = tradeLog.map((t, i) => ({ ...t, _index: i + 1 }));
    indexed.sort((a, b) => {
      let cmp = 0;
      switch (sortField) {
        case "index":
          cmp = a._index - b._index;
          break;
        case "entry_date":
          cmp = (a.entry_date || "").localeCompare(b.entry_date || "");
          break;
        case "exit_date":
          cmp = (a.exit_date || "").localeCompare(b.exit_date || "");
          break;
        case "entry_price":
          cmp = (a.entry_price || 0) - (b.entry_price || 0);
          break;
        case "exit_price":
          cmp = (a.exit_price || 0) - (b.exit_price || 0);
          break;
        case "pnl_percent":
          cmp = (a.pnl_percent || 0) - (b.pnl_percent || 0);
          break;
        case "hold_days":
          cmp = (a.hold_days || 0) - (b.hold_days || 0);
          break;
      }
      return sortDir === "asc" ? cmp : -cmp;
    });
    return indexed;
  }, [tradeLog, sortField, sortDir]);

  const totalPages = Math.ceil(sortedTrades.length / PAGE_SIZE);
  const pageTrades = sortedTrades.slice(
    page * PAGE_SIZE,
    (page + 1) * PAGE_SIZE
  );

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortField(field);
      setSortDir("asc");
    }
    setPage(0);
  };

  const sortIcon = (field: SortField) => {
    if (sortField !== field) return " \u2195";
    return sortDir === "asc" ? " \u2191" : " \u2193";
  };

  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
      <h3 className="text-lg font-semibold mb-4">
        거래 내역 ({tradeLog?.length || 0}건)
      </h3>

      {tradeLog && tradeLog.length > 0 ? (
        <>
          {/* Summary stats */}
          {stats && (
            <div className="mb-4 space-y-3">
              <div className="grid grid-cols-3 sm:grid-cols-7 gap-2">
                <div className="bg-gray-800 rounded-lg p-2.5 text-center">
                  <div className="text-[10px] text-gray-500">총 거래</div>
                  <div className="text-sm font-bold text-white">
                    {stats.total}
                  </div>
                </div>
                <div className="bg-gray-800 rounded-lg p-2.5 text-center">
                  <div className="text-[10px] text-gray-500">승</div>
                  <div className="text-sm font-bold text-green-400">
                    {stats.wins}
                  </div>
                </div>
                <div className="bg-gray-800 rounded-lg p-2.5 text-center">
                  <div className="text-[10px] text-gray-500">패</div>
                  <div className="text-sm font-bold text-red-400">
                    {stats.losses}
                  </div>
                </div>
                <div className="bg-gray-800 rounded-lg p-2.5 text-center">
                  <div className="text-[10px] text-gray-500">평균 수익</div>
                  <div className="text-sm font-bold text-green-400">
                    +{stats.avgWin.toFixed(2)}%
                  </div>
                </div>
                <div className="bg-gray-800 rounded-lg p-2.5 text-center">
                  <div className="text-[10px] text-gray-500">평균 손실</div>
                  <div className="text-sm font-bold text-red-400">
                    {stats.avgLoss.toFixed(2)}%
                  </div>
                </div>
                <div className="bg-gray-800 rounded-lg p-2.5 text-center">
                  <div className="text-[10px] text-gray-500">최고 거래</div>
                  <div className="text-sm font-bold text-green-400">
                    +{stats.best.toFixed(2)}%
                  </div>
                </div>
                <div className="bg-gray-800 rounded-lg p-2.5 text-center">
                  <div className="text-[10px] text-gray-500">최악 거래</div>
                  <div className="text-sm font-bold text-red-400">
                    {stats.worst.toFixed(2)}%
                  </div>
                </div>
              </div>

              {/* Win/loss distribution bar */}
              <div className="bg-gray-800 rounded-lg p-3">
                <div className="flex items-center justify-between text-xs text-gray-500 mb-1.5">
                  <span>
                    승률 {stats.winRate.toFixed(1)}% ({stats.wins}승)
                  </span>
                  <span>
                    패률 {(100 - stats.winRate).toFixed(1)}% ({stats.losses}패)
                  </span>
                </div>
                <div className="flex h-3 rounded-full overflow-hidden">
                  <div
                    className="bg-green-500 transition-all"
                    style={{ width: `${stats.winRate}%` }}
                  />
                  <div
                    className="bg-red-500 transition-all"
                    style={{ width: `${100 - stats.winRate}%` }}
                  />
                </div>
              </div>
            </div>
          )}

          {/* Table */}
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-gray-500 border-b border-gray-800">
                  <th
                    className="text-left py-2 px-3 cursor-pointer hover:text-gray-300 select-none"
                    onClick={() => handleSort("index")}
                  >
                    #{sortIcon("index")}
                  </th>
                  <th
                    className="text-left py-2 px-3 cursor-pointer hover:text-gray-300 select-none"
                    onClick={() => handleSort("entry_date")}
                  >
                    진입일{sortIcon("entry_date")}
                  </th>
                  <th
                    className="text-left py-2 px-3 cursor-pointer hover:text-gray-300 select-none"
                    onClick={() => handleSort("exit_date")}
                  >
                    청산일{sortIcon("exit_date")}
                  </th>
                  <th
                    className="text-right py-2 px-3 cursor-pointer hover:text-gray-300 select-none"
                    onClick={() => handleSort("entry_price")}
                  >
                    진입가{sortIcon("entry_price")}
                  </th>
                  <th
                    className="text-right py-2 px-3 cursor-pointer hover:text-gray-300 select-none"
                    onClick={() => handleSort("exit_price")}
                  >
                    청산가{sortIcon("exit_price")}
                  </th>
                  <th
                    className="text-right py-2 px-3 cursor-pointer hover:text-gray-300 select-none"
                    onClick={() => handleSort("pnl_percent")}
                  >
                    손익(%){sortIcon("pnl_percent")}
                  </th>
                  <th className="text-center py-2 px-3">결과</th>
                  <th
                    className="text-right py-2 px-3 cursor-pointer hover:text-gray-300 select-none"
                    onClick={() => handleSort("hold_days")}
                  >
                    보유일{sortIcon("hold_days")}
                  </th>
                </tr>
              </thead>
              <tbody>
                {pageTrades.map((trade) => (
                  <tr
                    key={trade._index}
                    className="border-b border-gray-800/50 hover:bg-gray-800/50 transition-colors"
                  >
                    <td className="py-2 px-3 text-gray-500">{trade._index}</td>
                    <td className="py-2 px-3">
                      {trade.entry_date?.split(" ")[0]}
                    </td>
                    <td className="py-2 px-3">
                      {trade.exit_date?.split(" ")[0]}
                    </td>
                    <td className="py-2 px-3 text-right font-mono">
                      {trade.entry_price?.toLocaleString()}
                    </td>
                    <td className="py-2 px-3 text-right font-mono">
                      {trade.exit_price?.toLocaleString()}
                    </td>
                    <td
                      className={`py-2 px-3 text-right font-mono font-bold ${trade.pnl_percent >= 0 ? "text-green-400" : "text-red-400"}`}
                    >
                      {trade.pnl_percent >= 0 ? "+" : ""}
                      {trade.pnl_percent?.toFixed(2)}%
                    </td>
                    <td className="py-2 px-3 text-center">
                      <span
                        className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-bold ${
                          trade.pnl_percent >= 0
                            ? "bg-green-500/20 text-green-400"
                            : "bg-red-500/20 text-red-400"
                        }`}
                      >
                        {trade.pnl_percent >= 0 ? "WIN" : "LOSS"}
                      </span>
                    </td>
                    <td className="py-2 px-3 text-right text-gray-400">
                      {trade.hold_days}일
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between mt-4">
              <span className="text-xs text-gray-500">
                {page * PAGE_SIZE + 1}-
                {Math.min((page + 1) * PAGE_SIZE, sortedTrades.length)} /{" "}
                {sortedTrades.length}건
              </span>
              <div className="flex gap-2">
                <button
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                  disabled={page === 0}
                  className="px-3 py-1.5 bg-gray-800 hover:bg-gray-700 disabled:bg-gray-800/50 disabled:text-gray-600 rounded text-xs font-medium transition-colors"
                >
                  이전
                </button>
                <span className="px-3 py-1.5 text-xs text-gray-400">
                  {page + 1} / {totalPages}
                </span>
                <button
                  onClick={() =>
                    setPage((p) => Math.min(totalPages - 1, p + 1))
                  }
                  disabled={page >= totalPages - 1}
                  className="px-3 py-1.5 bg-gray-800 hover:bg-gray-700 disabled:bg-gray-800/50 disabled:text-gray-600 rounded text-xs font-medium transition-colors"
                >
                  다음
                </button>
              </div>
            </div>
          )}
        </>
      ) : (
        <p className="text-gray-500">거래 내역이 없습니다.</p>
      )}
    </div>
  );
}
