"use client";

import { useEffect, useState, useCallback } from "react";
import api from "@/lib/api";

interface NotificationItem {
  id: string;
  category: string;
  title: string;
  message: string;
  is_read: boolean;
  data: Record<string, unknown> | null;
  link: string | null;
  created_at: string;
}

interface Preferences {
  in_app_enabled: boolean;
  email_enabled: boolean;
  trade_alerts: boolean;
  agent_alerts: boolean;
  order_alerts: boolean;
  position_alerts: boolean;
  system_alerts: boolean;
  email_address: string | null;
}

const CATEGORY_COLORS: Record<string, string> = {
  trade: "bg-green-900/30 text-green-400",
  agent: "bg-blue-900/30 text-blue-400",
  order: "bg-yellow-900/30 text-yellow-400",
  position: "bg-purple-900/30 text-purple-400",
  system: "bg-gray-800 text-gray-400",
  alert: "bg-red-900/30 text-red-400",
};

export default function NotificationsPage() {
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [total, setTotal] = useState(0);
  const [filter, setFilter] = useState<string | null>(null);
  const [showPrefs, setShowPrefs] = useState(false);
  const [prefs, setPrefs] = useState<Preferences | null>(null);
  const [loading, setLoading] = useState(true);

  const loadNotifications = useCallback(async () => {
    try {
      const params: Record<string, string> = { limit: "100" };
      if (filter) params.category = filter;
      const res = await api.get("/notifications", { params });
      setNotifications(res.data.notifications);
      setUnreadCount(res.data.unread_count);
      setTotal(res.data.total);
    } catch {
      // best effort
    }
    setLoading(false);
  }, [filter]);

  const loadPrefs = useCallback(async () => {
    try {
      const res = await api.get("/notifications/preferences");
      setPrefs(res.data);
    } catch {
      // best effort
    }
  }, []);

  useEffect(() => {
    loadNotifications();
  }, [loadNotifications]);

  const markRead = async (id: string) => {
    try {
      await api.post(`/notifications/${id}/read`);
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, is_read: true } : n))
      );
      setUnreadCount((c) => Math.max(0, c - 1));
    } catch {
      // error
    }
  };

  const markAllRead = async () => {
    try {
      await api.post("/notifications/read-all");
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
      setUnreadCount(0);
    } catch {
      // error
    }
  };

  const savePrefs = async (updates: Partial<Preferences>) => {
    try {
      const res = await api.put("/notifications/preferences", updates);
      setPrefs(res.data);
    } catch {
      // error
    }
  };

  const categories = ["trade", "agent", "order", "position", "system", "alert"];

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold">Notifications</h2>
          <p className="text-sm text-gray-500 mt-1">
            {unreadCount > 0 ? `${unreadCount} unread` : "All caught up"} &middot; {total} total
          </p>
        </div>
        <div className="flex gap-2">
          {unreadCount > 0 && (
            <button
              onClick={markAllRead}
              className="px-4 py-2 text-sm bg-gray-800 text-gray-300 rounded-lg hover:bg-gray-700 border border-gray-700"
            >
              Mark All Read
            </button>
          )}
          <button
            onClick={() => { setShowPrefs(!showPrefs); if (!prefs) loadPrefs(); }}
            className="px-4 py-2 text-sm bg-gray-800 text-gray-300 rounded-lg hover:bg-gray-700 border border-gray-700"
          >
            Preferences
          </button>
        </div>
      </div>

      {/* Preferences Panel */}
      {showPrefs && prefs && (
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-6 mb-6">
          <h3 className="text-lg font-semibold mb-4">Notification Preferences</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <PrefToggle
              label="In-app Notifications"
              checked={prefs.in_app_enabled}
              onChange={(v) => savePrefs({ in_app_enabled: v })}
            />
            <PrefToggle
              label="Email Notifications"
              checked={prefs.email_enabled}
              onChange={(v) => savePrefs({ email_enabled: v })}
            />
            <PrefToggle
              label="Trade Alerts"
              checked={prefs.trade_alerts}
              onChange={(v) => savePrefs({ trade_alerts: v })}
            />
            <PrefToggle
              label="Agent Alerts"
              checked={prefs.agent_alerts}
              onChange={(v) => savePrefs({ agent_alerts: v })}
            />
            <PrefToggle
              label="Order Alerts"
              checked={prefs.order_alerts}
              onChange={(v) => savePrefs({ order_alerts: v })}
            />
            <PrefToggle
              label="Position Alerts"
              checked={prefs.position_alerts}
              onChange={(v) => savePrefs({ position_alerts: v })}
            />
            <PrefToggle
              label="System Alerts"
              checked={prefs.system_alerts}
              onChange={(v) => savePrefs({ system_alerts: v })}
            />
          </div>
        </div>
      )}

      {/* Category Filters */}
      <div className="flex gap-2 mb-4 overflow-x-auto pb-2">
        <button
          onClick={() => setFilter(null)}
          className={`px-3 py-1.5 rounded-lg text-xs whitespace-nowrap border transition-colors ${
            !filter ? "bg-blue-600/20 border-blue-500 text-blue-400" : "bg-gray-900 border-gray-800 text-gray-500"
          }`}
        >
          All
        </button>
        {categories.map((cat) => (
          <button
            key={cat}
            onClick={() => setFilter(cat)}
            className={`px-3 py-1.5 rounded-lg text-xs capitalize whitespace-nowrap border transition-colors ${
              filter === cat ? "bg-blue-600/20 border-blue-500 text-blue-400" : "bg-gray-900 border-gray-800 text-gray-500"
            }`}
          >
            {cat}
          </button>
        ))}
      </div>

      {/* Notification List */}
      <div className="space-y-2">
        {loading ? (
          <div className="bg-gray-900 rounded-xl border border-gray-800 p-12 text-center">
            <p className="text-gray-500">Loading notifications...</p>
          </div>
        ) : notifications.length === 0 ? (
          <div className="bg-gray-900 rounded-xl border border-gray-800 p-12 text-center">
            <p className="text-gray-500">No notifications yet.</p>
          </div>
        ) : (
          notifications.map((n) => (
            <div
              key={n.id}
              onClick={() => !n.is_read && markRead(n.id)}
              className={`bg-gray-900 rounded-xl border p-4 cursor-pointer transition-colors ${
                n.is_read
                  ? "border-gray-800/50 opacity-60"
                  : "border-gray-700 hover:border-gray-600"
              }`}
            >
              <div className="flex items-start gap-3">
                {!n.is_read && (
                  <span className="mt-1.5 w-2 h-2 bg-blue-400 rounded-full flex-shrink-0" />
                )}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`px-2 py-0.5 rounded text-xs ${CATEGORY_COLORS[n.category] || "bg-gray-800 text-gray-400"}`}>
                      {n.category}
                    </span>
                    <span className="text-xs text-gray-500">
                      {formatTime(n.created_at)}
                    </span>
                  </div>
                  <p className="font-medium text-sm">{n.title}</p>
                  <p className="text-sm text-gray-400 mt-0.5">{n.message}</p>
                  {n.link && (
                    <a
                      href={n.link}
                      className="text-xs text-blue-400 hover:underline mt-1 inline-block"
                      onClick={(e) => e.stopPropagation()}
                    >
                      View Details
                    </a>
                  )}
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function PrefToggle({
  label, checked, onChange,
}: {
  label: string; checked: boolean; onChange: (v: boolean) => void;
}) {
  return (
    <label className="flex items-center gap-2 cursor-pointer">
      <div
        onClick={() => onChange(!checked)}
        className={`w-10 h-5 rounded-full relative transition-colors ${checked ? "bg-blue-600" : "bg-gray-700"}`}
      >
        <div
          className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform ${
            checked ? "translate-x-5" : "translate-x-0.5"
          }`}
        />
      </div>
      <span className="text-sm text-gray-300">{label}</span>
    </label>
  );
}

function formatTime(iso: string): string {
  try {
    const d = new Date(iso);
    const now = new Date();
    const diff = now.getTime() - d.getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return "Just now";
    if (mins < 60) return `${mins}m ago`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    if (days < 7) return `${days}d ago`;
    return d.toLocaleDateString("ko-KR", { month: "short", day: "numeric" });
  } catch {
    return "";
  }
}
