"use client";

import { useState, useEffect, useCallback } from "react";
import api from "@/lib/api";
import {
  useTradingWebSocket,
  type OrderUpdateEvent,
  type RecipeSignalEvent,
} from "@/lib/useTradingWebSocket";

interface RecipeOrder {
  id: string;
  stock_code: string;
  stock_name: string | null;
  side: string;
  order_type: string;
  quantity: number;
  avg_fill_price: number | null;
  kis_order_id: string | null;
  status: string;
  execution_strategy: string | null;
  slippage_bps: number | null;
  error_message: string | null;
  created_at: string;
}

interface ExecutionPanelProps {
  recipeId: string | null;
  isActive: boolean;
  stockCodes: string[];
}

export default function ExecutionPanel({
  recipeId,
  isActive,
  stockCodes,
}: ExecutionPanelProps) {
  const [orders, setOrders] = useState<RecipeOrder[]>([]);
  const [loading, setLoading] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [execResult, setExecResult] = useState<{
    total_submitted: number;
    total_failed: number;
  } | null>(null);
  const [signal, setSignal] = useState<{
    signal_type: string;
    stock_code: string;
    recipe_name: string;
  } | null>(null);

  const fetchOrders = useCallback(async () => {
    if (!recipeId) return;
    setLoading(true);
    try {
      const { data } = await api.get(`/recipes/${recipeId}/orders?limit=50`);
      setOrders(data);
    } catch {
      // Orders endpoint may not have data yet
      setOrders([]);
    } finally {
      setLoading(false);
    }
  }, [recipeId]);

  useEffect(() => {
    fetchOrders();
  }, [fetchOrders]);

  // Live WebSocket updates
  const handleOrderUpdate = useCallback(
    (data: OrderUpdateEvent) => {
      if (data.recipe_id === recipeId) {
        fetchOrders();
      }
    },
    [recipeId, fetchOrders]
  );

  const handleRecipeSignal = useCallback(
    (data: RecipeSignalEvent) => {
      if (data.recipe_id === recipeId) {
        setSignal({
          signal_type: data.signal_type,
          stock_code: data.stock_code,
          recipe_name: data.recipe_name,
        });
        // Auto-dismiss after 10s
        setTimeout(() => setSignal(null), 10000);
      }
    },
    [recipeId]
  );

  useTradingWebSocket({
    onOrderUpdate: handleOrderUpdate,
    onRecipeSignal: handleRecipeSignal,
  });

  const handleExecute = async () => {
    if (!recipeId) return;
    setExecuting(true);
    setError(null);
    setExecResult(null);

    try {
      const { data } = await api.post(`/recipes/${recipeId}/execute`, {});
      setExecResult({
        total_submitted: data.total_submitted,
        total_failed: data.total_failed,
      });
      fetchOrders();
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail || "실행에 실패했습니다";
      setError(msg);
    } finally {
      setExecuting(false);
    }
  };

  const statusColor = (status: string) => {
    switch (status) {
      case "submitted":
      case "filled":
        return "text-green-400";
      case "failed":
      case "cancelled":
        return "text-red-400";
      case "pending":
        return "text-yellow-400";
      default:
        return "text-gray-400";
    }
  };

  const statusLabel = (status: string) => {
    const map: Record<string, string> = {
      pending: "대기",
      submitted: "제출됨",
      filled: "체결",
      failed: "실패",
      cancelled: "취소",
    };
    return map[status] || status;
  };

  const successCount = orders.filter(
    (o) => o.status === "submitted" || o.status === "filled"
  ).length;
  const failCount = orders.filter((o) => o.status === "failed").length;

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold text-white mb-1">실행 현황</h3>
        <p className="text-gray-400 text-sm">
          레시피의 실행 상태와 주문 내역을 확인하세요
        </p>
      </div>

      {/* Status + Execute Button */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium ${
              isActive
                ? "bg-green-500/20 text-green-400"
                : "bg-gray-700 text-gray-400"
            }`}
          >
            <span
              className={`w-2 h-2 rounded-full ${isActive ? "bg-green-400" : "bg-gray-500"}`}
            />
            {isActive ? "자동매매 활성" : "비활성"}
          </span>
          <span className="text-gray-500 text-xs">
            종목: {stockCodes.length}개
          </span>
        </div>
        <button
          onClick={handleExecute}
          disabled={executing || !recipeId}
          className="bg-orange-600 hover:bg-orange-700 disabled:bg-gray-700 disabled:text-gray-500 text-white px-5 py-2.5 rounded-lg text-sm font-medium transition-colors"
        >
          {executing ? "실행 중..." : "지금 실행"}
        </button>
      </div>

      {/* Execution Result */}
      {execResult && (
        <div className="bg-blue-500/10 border border-blue-500/30 rounded-xl p-4">
          <p className="text-blue-400 text-sm">
            실행 완료: {execResult.total_submitted}건 제출,{" "}
            {execResult.total_failed}건 실패
          </p>
        </div>
      )}

      {/* Signal Alert */}
      {signal && (
        <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-xl p-4 flex items-center justify-between">
          <p className="text-yellow-400 text-sm">
            {signal.signal_type === "entry" ? "매수" : "매도"} 신호 감지:{" "}
            <span className="font-mono">{signal.stock_code}</span>
          </p>
          <button
            onClick={() => setSignal(null)}
            className="text-yellow-500 hover:text-yellow-300 text-xs"
          >
            닫기
          </button>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4">
          <p className="text-red-400 text-sm">{error}</p>
        </div>
      )}

      {/* Stats */}
      {orders.length > 0 && (
        <div className="grid grid-cols-3 gap-4">
          <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
            <p className="text-xs text-gray-400">총 주문</p>
            <p className="text-2xl font-bold text-white mt-1">
              {orders.length}
            </p>
          </div>
          <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
            <p className="text-xs text-gray-400">성공</p>
            <p className="text-2xl font-bold text-green-400 mt-1">
              {successCount}
            </p>
          </div>
          <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
            <p className="text-xs text-gray-400">실패</p>
            <p className="text-2xl font-bold text-red-400 mt-1">{failCount}</p>
          </div>
        </div>
      )}

      {/* Orders Table */}
      {loading ? (
        <div className="animate-pulse space-y-2">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-12 bg-gray-800 rounded-lg" />
          ))}
        </div>
      ) : orders.length > 0 ? (
        <div className="overflow-x-auto max-h-[400px] overflow-y-auto">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-gray-800">
              <tr className="border-b border-gray-700 text-gray-400">
                <th className="text-left p-2.5">종목</th>
                <th className="text-left p-2.5">방향</th>
                <th className="text-right p-2.5">수량</th>
                <th className="text-right p-2.5">체결가</th>
                <th className="text-center p-2.5">상태</th>
                <th className="text-left p-2.5">전략</th>
                <th className="text-left p-2.5">시간</th>
              </tr>
            </thead>
            <tbody>
              {orders.map((order) => (
                <tr
                  key={order.id}
                  className="border-b border-gray-700/50 hover:bg-gray-700/30"
                >
                  <td className="p-2.5">
                    <p className="text-white text-xs font-medium">
                      {order.stock_name || order.stock_code}
                    </p>
                    {order.stock_name && (
                      <p className="text-gray-500 text-[10px] font-mono">{order.stock_code}</p>
                    )}
                  </td>
                  <td className="p-2.5">
                    <span
                      className={`text-xs font-medium ${order.side === "buy" ? "text-green-400" : "text-red-400"}`}
                    >
                      {order.side === "buy" ? "매수" : "매도"}
                    </span>
                  </td>
                  <td className="p-2.5 text-right font-mono text-gray-300">
                    {order.quantity.toLocaleString()}
                  </td>
                  <td className="p-2.5 text-right font-mono text-gray-300">
                    {order.avg_fill_price
                      ? `₩${order.avg_fill_price.toLocaleString()}`
                      : "-"}
                  </td>
                  <td className="p-2.5 text-center">
                    <span
                      className={`text-xs font-medium ${statusColor(order.status)}`}
                    >
                      {statusLabel(order.status)}
                    </span>
                  </td>
                  <td className="p-2.5 text-gray-400 text-xs">
                    {order.execution_strategy || "-"}
                  </td>
                  <td className="p-2.5 text-gray-400 text-xs">
                    {(() => {
                      const d = new Date(order.created_at);
                      return `${d.getHours().toString().padStart(2, "0")}:${d.getMinutes().toString().padStart(2, "0")}`;
                    })()}
                    <span className="text-gray-600 ml-1">
                      {order.created_at?.split("T")[0]?.slice(5)}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="text-center py-12 bg-gray-800/50 rounded-xl border border-gray-700 border-dashed">
          <p className="text-gray-400 text-lg mb-2">아직 실행 내역이 없습니다</p>
          <p className="text-gray-500 text-sm">
            &ldquo;지금 실행&rdquo; 버튼을 눌러 수동으로 실행하거나, 자동매매를 활성화하세요
          </p>
        </div>
      )}
    </div>
  );
}
