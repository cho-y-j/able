import { create } from 'zustand';
import api from '@/lib/api';

export interface Position {
  id: string;
  stock_code: string;
  stock_name: string | null;
  quantity: number;
  avg_cost_price: number;
  current_price: number | null;
  unrealized_pnl: number | null;
  realized_pnl: number;
}

export interface Order {
  id: string;
  stock_code: string;
  stock_name: string | null;
  side: string;
  order_type: string;
  quantity: number;
  limit_price: number | null;
  filled_quantity: number;
  avg_fill_price: number | null;
  status: string;
  submitted_at: string | null;
  filled_at: string | null;
  created_at: string;
}

export interface PortfolioStats {
  portfolio_value: number;
  total_invested: number;
  unrealized_pnl: number;
  realized_pnl: number;
  total_pnl: number;
  total_pnl_pct: number;
  position_count: number;
  trade_stats: {
    total_trades: number;
    win_rate: number;
    profit_factor: number;
    winning_trades: number;
    losing_trades: number;
  };
}

interface TradingState {
  positions: Position[];
  orders: Order[];
  portfolioStats: PortfolioStats | null;
  selectedStock: string | null;
  isLoading: boolean;
  lastUpdated: number | null;
  fetchPositions: () => Promise<void>;
  fetchOrders: () => Promise<void>;
  fetchPortfolioStats: () => Promise<void>;
  setSelectedStock: (code: string | null) => void;
  updatePositionPrice: (stockCode: string, price: number) => void;
}

export const useTradingStore = create<TradingState>((set, get) => ({
  positions: [],
  orders: [],
  portfolioStats: null,
  selectedStock: null,
  isLoading: false,
  lastUpdated: null,

  fetchPositions: async () => {
    set({ isLoading: true });
    try {
      const { data } = await api.get('/trading/positions');
      set({ positions: data, lastUpdated: Date.now() });
    } finally {
      set({ isLoading: false });
    }
  },

  fetchOrders: async () => {
    try {
      const { data } = await api.get('/trading/orders');
      set({ orders: data });
    } catch {
      // handle error
    }
  },

  fetchPortfolioStats: async () => {
    try {
      const { data } = await api.get('/trading/portfolio/analytics');
      set({ portfolioStats: data });
    } catch {
      // handle error
    }
  },

  setSelectedStock: (code) => set({ selectedStock: code }),

  updatePositionPrice: (stockCode, price) => {
    const { positions } = get();
    const updated = positions.map((p) => {
      if (p.stock_code !== stockCode) return p;
      const unrealized = (price - p.avg_cost_price) * p.quantity;
      return { ...p, current_price: price, unrealized_pnl: unrealized };
    });
    set({ positions: updated, lastUpdated: Date.now() });
  },
}));
