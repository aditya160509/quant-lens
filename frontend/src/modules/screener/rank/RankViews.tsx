"use client";

import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { Waterfall } from "@/charts/Waterfall";
import { DataTable, Empty } from "@/kit/DataTable";
import { useRuns } from "@/modules/research/api";
import { isNum, num, out } from "@/modules/research/format";
import { useStudies } from "@/modules/research/store";
import type { ViewProps } from "@/modules/research/outputs/types";
import type { FeatureResult } from "@/modules/research/types";
import { API_BASE_URL } from "@/lib/apiBase";

/** One name's composite as a waterfall: each factor's weighted share of the score. */
export function ScoreWaterfall({ result }: ViewProps) {
  const rows = out(result, "per_stock_score_decomposition");
  const items = rows.filter((r) => isNum(r.weighted_contribution)).map((r) => ({ label: String(r.component), value: r.weighted_contribution as number }));
  if (!items.length) return <Empty text="Unknown: no factor scores for this name." />;
  return (
    <div>
      <div className="stat-l">{String(rows[0].ticker)}</div>
      <Waterfall base={0} items={items} format={(v) => num(v, 1)} />
    </div>
  );
}

/** The rule-based composite rank beside the latest ML alpha model's rank for the same names. */
export function RankVsMl({ result, opts }: ViewProps) {
  const router = useRouter();
  const rules = out(result, "composite_score_universe_ranking");
  const run = useRuns((s) => s.runs.find((r) => r.featureId === "ml02" && r.status === "completed"));
  const ml = useQuery({
    queryKey: ["screener", "ml-rank", run?.jobId],
    queryFn: async () => (await (await fetch(`${API_BASE_URL}/ml/v2/jobs/${run?.jobId}`)).json()) as { result?: FeatureResult },
    enabled: Boolean(run), staleTime: Infinity, retry: false,
  });
  const learned = new Map(out(ml.data?.result ?? ({} as FeatureResult), "prediction_rank_table").map((r) => [String(r.ticker), r.rank]));
  if (!run) return <Empty text="Unknown" />;
  const rows = rules.map((r) => {
    const m = learned.get(String(r.ticker));
    return { ticker: r.ticker, rules_rank: r.rank, ml_rank: isNum(m) ? m : null, rank_gap: isNum(m) && isNum(r.rank) ? m - r.rank : null };
  });
  const train = () => {
    useStudies.setState((s) => ({ forms: { ...s.forms, ml02: { ...(s.forms.ml02 ?? {}), universe: rules.map((r) => String(r.ticker)).join(",") } } }));
    router.push("/ml/alpha");
  };
  return (
    <div>
      <button type="button" className="btn sm" onClick={train}>Train a ranker on this</button>
      <DataTable rows={rows} opts={{ ...opts, hatch: true }} />
    </div>
  );
}
