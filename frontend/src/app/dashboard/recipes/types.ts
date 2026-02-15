export interface SignalEntry {
  type: string;
  strategy_type?: string;
  params: Record<string, unknown>;
  weight: number;
}

export type Combinator = "AND" | "OR" | "MIN_AGREE";

export interface Recipe {
  id: string;
  name: string;
  description?: string | null;
  signal_config: {
    combinator: Combinator;
    min_agree?: number;
    signals: SignalEntry[];
  };
  custom_filters: Record<string, unknown>;
  stock_codes: string[];
  risk_config: Record<string, number>;
  is_active: boolean;
  is_template: boolean;
  created_at: string;
  updated_at: string;
}
