import { useState, useEffect, useRef } from "react";
import api from "@/lib/api";

export interface StockResult {
  code: string;
  name: string;
  market: string;
  sector: string;
}

export function useStockSearch(
  query: string,
  market: string = "kr",
  delay: number = 300
) {
  const [results, setResults] = useState<StockResult[]>([]);
  const [loading, setLoading] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!query || query.trim().length < 1) {
      setResults([]);
      return;
    }

    const timer = setTimeout(async () => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      setLoading(true);
      try {
        const { data } = await api.get("/market/stock-search", {
          params: { q: query.trim(), market, limit: 15 },
          signal: controller.signal,
        });
        if (!controller.signal.aborted) {
          setResults(data.results || []);
        }
      } catch {
        if (!controller.signal.aborted) {
          setResults([]);
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    }, delay);

    return () => clearTimeout(timer);
  }, [query, market, delay]);

  return { results, loading };
}
