"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuthStore } from "@/store/auth";
import { useNotifications, Toast } from "@/lib/useNotifications";
import { useI18n, type Locale } from "@/i18n";

const navKeys = [
  { href: "/dashboard", key: "dashboard" as const, icon: "H" },
  { href: "/dashboard/market", key: "market" as const, icon: "M" },
  { href: "/dashboard/strategies", key: "strategies" as const, icon: "S" },
  { href: "/dashboard/recipes", key: "recipes" as const, icon: "F" },
  { href: "/dashboard/backtests", key: "backtests" as const, icon: "B" },
  { href: "/dashboard/trading", key: "trading" as const, icon: "T" },
  { href: "/dashboard/paper", key: "paper" as const, icon: "R" },
  { href: "/dashboard/portfolio", key: "portfolio" as const, icon: "P" },
  { href: "/dashboard/risk", key: "risk" as const, icon: "V" },
  { href: "/dashboard/agents", key: "agents" as const, icon: "A" },
  { href: "/dashboard/notifications", key: "notifications" as const, icon: "N" },
  { href: "/dashboard/settings", key: "settings" as const, icon: "G" },
];

const CATEGORY_COLORS: Record<string, string> = {
  trade: "bg-green-500",
  agent: "bg-blue-500",
  order: "bg-yellow-500",
  position: "bg-purple-500",
  system: "bg-gray-500",
  alert: "bg-red-500",
};

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout } = useAuthStore();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { unreadCount, toasts, dismissToast } = useNotifications();
  const { t, locale, setLocale } = useI18n();

  return (
    <div className="min-h-screen flex bg-gray-950 text-white">
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/60 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`
          fixed inset-y-0 left-0 z-40 w-64 bg-gray-900 border-r border-gray-800 flex flex-col
          transform transition-transform duration-200 ease-in-out
          lg:relative lg:translate-x-0
          ${sidebarOpen ? "translate-x-0" : "-translate-x-full"}
        `}
      >
        <div className="p-6 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-blue-400">{t.nav.platformName}</h1>
            <p className="text-xs text-gray-500 mt-1">{t.nav.platformSub}</p>
          </div>
          <button
            onClick={() => setSidebarOpen(false)}
            className="lg:hidden text-gray-400 hover:text-white p-1"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <nav className="flex-1 px-3 overflow-y-auto">
          {navKeys.map((item) => {
            const isActive = pathname === item.href ||
              (item.href !== "/dashboard" && pathname.startsWith(item.href));
            const isNotif = item.href === "/dashboard/notifications";
            const label = t.nav[item.key];
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setSidebarOpen(false)}
                className={`flex items-center gap-3 px-4 py-3 rounded-lg mb-1 text-sm transition-colors ${
                  isActive
                    ? "bg-blue-600/20 text-blue-400"
                    : "text-gray-400 hover:text-white hover:bg-gray-800"
                }`}
              >
                <span className="w-6 h-6 flex items-center justify-center bg-gray-800 rounded text-xs font-bold relative">
                  {item.icon}
                  {isNotif && unreadCount > 0 && (
                    <span className="absolute -top-1 -right-1 w-4 h-4 bg-red-500 rounded-full text-[10px] flex items-center justify-center text-white font-bold">
                      {unreadCount > 9 ? "9+" : unreadCount}
                    </span>
                  )}
                </span>
                {label}
                {isNotif && unreadCount > 0 && (
                  <span className="ml-auto bg-red-500/20 text-red-400 text-xs px-2 py-0.5 rounded-full">
                    {unreadCount}
                  </span>
                )}
              </Link>
            );
          })}
        </nav>

        {/* Language toggle + user */}
        <div className="p-4 border-t border-gray-800">
          <div className="flex items-center gap-1 mb-3">
            {(["ko", "en"] as Locale[]).map((lang) => (
              <button
                key={lang}
                onClick={() => setLocale(lang)}
                className={`flex-1 py-1 text-xs rounded transition-colors ${
                  locale === lang
                    ? "bg-blue-600 text-white"
                    : "bg-gray-800 text-gray-400 hover:text-white"
                }`}
              >
                {lang === "ko" ? "한국어" : "English"}
              </button>
            ))}
          </div>
          <div className="flex items-center justify-between">
            <div className="text-sm truncate mr-2">
              <p className="text-gray-300 truncate">{user?.display_name || user?.email}</p>
            </div>
            <button
              onClick={logout}
              className="text-xs text-gray-500 hover:text-red-400 transition-colors whitespace-nowrap"
            >
              {t.nav.logout}
            </button>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto min-w-0">
        {/* Mobile header */}
        <div className="lg:hidden sticky top-0 z-20 bg-gray-950 border-b border-gray-800 px-4 py-3 flex items-center gap-3">
          <button
            onClick={() => setSidebarOpen(true)}
            className="text-gray-400 hover:text-white p-1"
          >
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
          <span className="text-blue-400 font-bold">ABLE</span>
          <Link href="/dashboard/notifications" className="ml-auto relative p-1">
            <svg className="w-5 h-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
            </svg>
            {unreadCount > 0 && (
              <span className="absolute top-0 right-0 w-4 h-4 bg-red-500 rounded-full text-[10px] flex items-center justify-center text-white font-bold">
                {unreadCount > 9 ? "9+" : unreadCount}
              </span>
            )}
          </Link>
        </div>
        <div className="p-4 sm:p-6 lg:p-8">{children}</div>
      </main>

      {/* Toast notifications */}
      {toasts.length > 0 && (
        <div className="fixed top-4 right-4 z-50 flex flex-col gap-2 w-80">
          {toasts.map((toast) => (
            <ToastCard
              key={toast.id}
              toast={toast}
              onDismiss={() => dismissToast(toast.id)}
              onClick={() => {
                dismissToast(toast.id);
                if (toast.link) router.push(toast.link);
              }}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function ToastCard({
  toast,
  onDismiss,
  onClick,
}: {
  toast: Toast;
  onDismiss: () => void;
  onClick: () => void;
}) {
  return (
    <div
      className="bg-gray-900 border border-gray-700 rounded-xl p-4 shadow-2xl animate-slide-in cursor-pointer hover:border-gray-600 transition-colors"
      onClick={onClick}
    >
      <div className="flex items-start gap-3">
        <span
          className={`mt-0.5 w-2.5 h-2.5 rounded-full flex-shrink-0 ${
            CATEGORY_COLORS[toast.category] || "bg-gray-500"
          }`}
        />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-white truncate">{toast.title}</p>
          <p className="text-xs text-gray-400 mt-0.5 line-clamp-2">{toast.message}</p>
        </div>
        <button
          onClick={(e) => {
            e.stopPropagation();
            onDismiss();
          }}
          className="text-gray-500 hover:text-gray-300 flex-shrink-0"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
    </div>
  );
}
