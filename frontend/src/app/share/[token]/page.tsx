"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { DataTable, Empty } from "@/kit/DataTable";
import { KpiStrip } from "@/kit/KpiStrip";
import { isNum, num, out } from "@/modules/research/format";
import type { FeatureResult } from "@/modules/research/types";
import { SCREENER_BASE } from "@/modules/screener/base";
import { RESULT_BARS, RESULT_COLUMNS, RESULT_HIDDEN } from "@/modules/screener/screenerLab";
import "@/workspace/workspace.css";
import "./share.css";

type Shared = { name: string; payload: Record<string, unknown>; latest_run: { as_of_date: string; result: FeatureResult } | null };

/** A saved screen anyone with the link can read; `?embed=1` drops the header for an iframe. */
function SharedScreen() {
  const { token } = useParams<{ token: string }>();
  const embed = useSearchParams().get("embed") === "1";
  const q = useQuery({
    queryKey: ["share", token],
    queryFn: async () => {
      const res = await fetch(`${SCREENER_BASE}/shared/${encodeURIComponent(token)}`);
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(typeof body.detail === "string" ? body.detail : "This link no longer works.");
      return body as Shared;
    },
    retry: false,
  });
  const run = q.data?.latest_run;
  const rows = run ? out(run.result, "ranked_screener_table") : [];
  const open = q.data ? `/screener/screen?form=${encodeURIComponent(JSON.stringify(q.data.payload))}` : "/screener";
  return (
    <div className={`ws-tokens share${embed ? " embed" : ""}`}>
      {embed ? null : (
        <header className="share-top">
          <Link href="/" className="share-brand">ATLAS</Link>
          <Link className="btn sm" href={open}>Open in ATLAS</Link>
        </header>
      )}
      <main className="share-main">
        {q.isLoading ? <div className="share-skel" aria-busy="true"><i className="skel" /><i className="skel" /><i className="skel-card" /></div> : q.error ? <Empty text={(q.error as Error).message} /> : (
          <>
            <div className="share-head">
              <h1>{q.data?.name}</h1>
              <p className="num">{run ? `${rows.length.toLocaleString()} names as of ${run.as_of_date}` : "Not run yet"}</p>
            </div>
            {run?.result.summary_cards?.length ? <KpiStrip items={run.result.summary_cards.slice(0, 5).map((c) => ({ label: c.label, value: isNum(c.value) ? num(c.value, Number.isInteger(c.value) ? 0 : 2) : String(c.value ?? "–") }))} /> : null}
            {rows.length ? <div className="share-table"><DataTable rows={rows} opts={{ max: 5000, maxHeight: embed ? 480 : 720, columns: RESULT_COLUMNS, bars: RESULT_BARS, hide: RESULT_HIDDEN, lead: ["rank", "ticker", "company_name"], freeze: ["rank", "ticker", "company_name"] }} /></div> : run ? <Empty text="No names pass this screen." /> : null}
          </>
        )}
      </main>
    </div>
  );
}

export default function SharePage() {
  return <Suspense><SharedScreen /></Suspense>;
}
