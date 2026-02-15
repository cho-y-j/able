"use client";

import { useEffect, useRef } from "react";
import { createWSConnection } from "@/lib/ws";

export interface OrderUpdateEvent {
  type: "order_update";
  order_id: string;
  recipe_id: string;
  stock_code: string;
  side: string;
  status: string;
}

export interface PriceUpdateEvent {
  type: "price_update";
  stock_code: string;
  current_price: number;
  change: number;
  change_percent: number;
  volume: number;
}

export interface RecipeSignalEvent {
  type: "recipe_signal";
  recipe_id: string;
  recipe_name: string;
  stock_code: string;
  signal_type: "entry" | "exit";
  timestamp: string;
}

interface TradingWSHandlers {
  onOrderUpdate?: (data: OrderUpdateEvent) => void;
  onPriceUpdate?: (data: PriceUpdateEvent) => void;
  onRecipeSignal?: (data: RecipeSignalEvent) => void;
}

/**
 * Shared hook for subscribing to trading WebSocket events.
 * Connects to /ws/trading and routes events to provided handlers.
 */
export function useTradingWebSocket(handlers: TradingWSHandlers): void {
  const handlersRef = useRef(handlers);
  handlersRef.current = handlers;

  useEffect(() => {
    const token =
      typeof window !== "undefined"
        ? localStorage.getItem("access_token")
        : null;
    if (!token) return;

    const ws = createWSConnection("trading");
    ws.connect(token);

    const unsubs: (() => void)[] = [];

    unsubs.push(
      ws.on("order_update", (data) => {
        handlersRef.current.onOrderUpdate?.(data as OrderUpdateEvent);
      })
    );

    unsubs.push(
      ws.on("price_update", (data) => {
        handlersRef.current.onPriceUpdate?.(data as PriceUpdateEvent);
      })
    );

    unsubs.push(
      ws.on("recipe_signal", (data) => {
        handlersRef.current.onRecipeSignal?.(data as RecipeSignalEvent);
      })
    );

    return () => {
      unsubs.forEach((fn) => fn());
      ws.disconnect();
    };
  }, []);
}
