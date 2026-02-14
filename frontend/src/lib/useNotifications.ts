"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { createWSConnection } from "@/lib/ws";
import api from "@/lib/api";

export interface Toast {
  id: string;
  category: string;
  title: string;
  message: string;
  link?: string;
  timestamp: number;
}

interface UseNotificationsReturn {
  unreadCount: number;
  toasts: Toast[];
  dismissToast: (id: string) => void;
  clearToasts: () => void;
  refreshCount: () => Promise<void>;
}

const TOAST_DURATION = 6000;

export function useNotifications(): UseNotificationsReturn {
  const [unreadCount, setUnreadCount] = useState(0);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const wsRef = useRef<ReturnType<typeof createWSConnection> | null>(null);
  const cleanupRef = useRef<(() => void) | null>(null);

  const refreshCount = useCallback(async () => {
    try {
      const res = await api.get("/notifications/unread-count");
      setUnreadCount(res.data.unread_count || 0);
    } catch {
      // best effort
    }
  }, []);

  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const clearToasts = useCallback(() => {
    setToasts([]);
  }, []);

  useEffect(() => {
    // Initial fetch
    refreshCount();

    // WebSocket connection
    const token =
      typeof window !== "undefined"
        ? localStorage.getItem("access_token")
        : null;
    if (!token) return;

    const ws = createWSConnection("trading");
    wsRef.current = ws;
    ws.connect(token);

    // Listen for notification events
    const unsub = ws.on("notification", (data: unknown) => {
      const d = data as {
        category?: string;
        title?: string;
        message?: string;
        link?: string;
      };
      const id = `toast-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;

      // Increment unread count
      setUnreadCount((c) => c + 1);

      // Add toast
      const toast: Toast = {
        id,
        category: d.category || "system",
        title: d.title || "Notification",
        message: d.message || "",
        link: d.link || undefined,
        timestamp: Date.now(),
      };
      setToasts((prev) => [toast, ...prev].slice(0, 5));

      // Auto-dismiss after duration
      setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== id));
      }, TOAST_DURATION);
    });

    cleanupRef.current = unsub;

    // Fallback polling (60s) in case WebSocket disconnects
    const interval = setInterval(refreshCount, 60000);

    return () => {
      unsub();
      ws.disconnect();
      clearInterval(interval);
    };
  }, [refreshCount]);

  return { unreadCount, toasts, dismissToast, clearToasts, refreshCount };
}
