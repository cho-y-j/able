"use client";

import { useEffect, useRef, useState, useCallback } from "react";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000/api/v1/ws";

export interface PriceTick {
  stock_code: string;
  current_price: number;
  change: number;
  change_percent: number;
  volume: number;
  high: number;
  low: number;
  timestamp: string;
}

interface UseRealtimePriceReturn {
  tick: PriceTick | null;
  isConnected: boolean;
  error: string | null;
  subscribe: (stockCode: string) => void;
}

export function useRealtimePrice(stockCode: string | null): UseRealtimePriceReturn {
  const [tick, setTick] = useState<PriceTick | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const currentCodeRef = useRef(stockCode);

  const cleanup = useCallback(() => {
    if (reconnectRef.current) {
      clearTimeout(reconnectRef.current);
      reconnectRef.current = null;
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setIsConnected(false);
  }, []);

  const connect = useCallback(
    (code: string) => {
      cleanup();
      setError(null);
      setTick(null);

      const token =
        typeof window !== "undefined"
          ? localStorage.getItem("access_token")
          : null;
      if (!token || !code) return;

      const ws = new WebSocket(`${WS_URL}/market/${code}?token=${token}`);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
        setError(null);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === "price_update") {
            setTick({
              stock_code: data.stock_code,
              current_price: data.current_price,
              change: data.change,
              change_percent: data.change_percent,
              volume: data.volume,
              high: data.high,
              low: data.low,
              timestamp: data.timestamp,
            });
          } else if (data.type === "price_error") {
            setError(data.message);
          }
        } catch {
          // ignore parse errors
        }
      };

      ws.onclose = () => {
        setIsConnected(false);
        // Reconnect after 5 seconds if still subscribed
        if (currentCodeRef.current) {
          reconnectRef.current = setTimeout(() => {
            if (currentCodeRef.current) {
              connect(currentCodeRef.current);
            }
          }, 5000);
        }
      };

      ws.onerror = () => {
        setError("WebSocket connection failed");
        ws.close();
      };
    },
    [cleanup],
  );

  const subscribe = useCallback(
    (newCode: string) => {
      currentCodeRef.current = newCode;
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        // Send subscribe message to switch stocks without reconnecting
        wsRef.current.send(
          JSON.stringify({ type: "subscribe", stock_code: newCode }),
        );
        setTick(null);
      } else {
        connect(newCode);
      }
    },
    [connect],
  );

  useEffect(() => {
    currentCodeRef.current = stockCode;
    if (stockCode) {
      connect(stockCode);
    } else {
      cleanup();
    }
    return cleanup;
  }, [stockCode, connect, cleanup]);

  return { tick, isConnected, error, subscribe };
}
