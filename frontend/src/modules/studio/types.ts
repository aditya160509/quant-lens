import type { FeatureResult } from "@/modules/research/types";
import type { Freshness, Ledger } from "./api";

export type LimitRow = { limit: string; value: number | null; bound: number; pass: boolean | null; room: number | null; format: "pct" | "num" | "int" };
type Skipped = { status: "skipped"; reason: string };

/** `meta` of a Studio backtest result (backend/app/services/studio_v3/core/backtest.py). */
export type StudioMeta = FeatureResult["meta"] & {
  headline: string;
  verdict_chip: string;
  metrics: Record<string, number | null> & { trades: number };
  total_return: number;
  years: number;
  benchmark: string | null;
  costs_off: boolean;
  few_trades: boolean;
  open_trades: number;
  unfilled: number;
  costs: { total: number; share_of_gross: number | null; gross_return: number; net_return: number; turnover_per_year: number };
  exposure: { time_in_market: number; avg_gross: number; avg_net: number };
  start_dates: { positive: number; of: number; cagr_low: number | null; cagr_high: number | null; pass_share: number | null };
  survivorship: Skipped | { status: "ok"; with_delisted: number | null; survivors_only: number | null; delisted: number };
  fill_check: Skipped | { status: "ok"; hourly_names: number; with_hourly: number; daily_only: number };
  without_best_months: number | null;
  thirds_sharpe: number[];
  capacity: number | null;
  my_limits: { passed: number; of: number; closest: LimitRow | null };
  holdout_from: string | null;
  period: [string, string];
  freshness: Freshness;
  ledger: Ledger;
  strategy: { id: string | null; version: number | null; name: string };
  run_hash: string;
  result_hash: string;
  description: string;
};

export const metaOf = (r: FeatureResult) => r.meta as StudioMeta;
