"use client";

import { useState } from "react";
import toast from "react-hot-toast";
import { isNum, pct } from "@/modules/research/format";
import type { ViewProps } from "@/modules/research/outputs/types";
import { studio } from "../api";
import { Skipped } from "./BacktestViews";

type Forward = { status: string; from: string; backdated: boolean; reason?: string; days?: number; return?: number; expected?: number; band?: number; drift?: boolean; drift_from?: string | null;
  live_sharpe?: number | null; backtest_sharpe?: number; drawdown_odds?: { at_backtest: number; at_half: number } };
type LiveMeta = { as_of: string; stale: boolean; stale_days: number; orders: string; forward: Forward | null; channels: string[]; strategy?: { id: string | null; version: number | null; name: string };
  reconcile: { matched?: number; model?: number; real?: number; same_share?: number | null; avg_fill_bps?: number | null; skipped?: number; extra?: number } };
const meta = (r: ViewProps["result"]) => r.meta as unknown as LiveMeta;

/** Today's orders as plain text to paste into a broker. */
export function Orders({ result }: ViewProps) {
  const m = meta(result);
  if (!m.orders) return <Skipped reason={`no entries or exits on ${m.as_of}`} />;
  return (
    <div style={{ display: "grid", gap: 8 }}>
      {m.stale ? <span className="chip down">data {m.stale_days} days old</span> : null}
      <pre className="bd-code" style={{ margin: 0 }}>{m.orders}</pre>
      <button className="btn sm" style={{ justifySelf: "start" }} onClick={() => void navigator.clipboard.writeText(m.orders).then(() => toast.success("Copied"))}>Copy orders</button>
    </div>
  );
}

/** Freeze a version to paper; paper since the freeze against the backtest's band. */
export function Paper({ result }: ViewProps) {
  const m = meta(result);
  const f = m.forward;
  const [from, setFrom] = useState("");
  const [busy, setBusy] = useState(false);
  const sid = m.strategy?.id;
  const freeze = () => {
    if (!sid) return;
    setBusy(true);
    void studio("POST", `/strategies/${sid}/freeze`, { version: m.strategy?.version, as_of: from || null })
      .then(() => toast.success("Frozen. Run again to see paper."), (e) => toast.error(e instanceof Error ? e.message : "Failed")).finally(() => setBusy(false));
  };
  return (
    <div style={{ display: "grid", gap: 10 }}>
      {f?.status === "ok" ? (
        <>
          <div className="st-fig"><b style={{ color: f.drift ? "var(--down)" : undefined }}>{pct(f.return, 1)}</b><span>paper since {f.from}{f.backdated ? " (backdated)" : ""} · expected {pct(f.expected, 1)} ± {pct(f.band, 1)}{f.drift ? ` · outside the band from ${f.drift_from}` : ""}</span></div>
          <p className="bd-find"><b>Sharpe</b>{isNum(f.live_sharpe) ? f.live_sharpe.toFixed(2) : "—"} live vs {isNum(f.backtest_sharpe) ? f.backtest_sharpe.toFixed(2) : "—"} backtest</p>
          {f.drawdown_odds ? <p className="bd-find"><b>This drawdown</b>{pct(f.drawdown_odds.at_backtest, 0)} likely if the backtest is right, {pct(f.drawdown_odds.at_half, 0)} if the edge is half</p> : null}
        </>
      ) : f ? <Skipped reason={f.reason ?? "waiting"} /> : <Skipped reason="not frozen to paper" />}
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <input className="input" type="date" aria-label="Backdate start" value={from} onChange={(e) => setFrom(e.target.value)} />
        <button className="btn" disabled={busy || !sid} onClick={freeze}>{busy ? "Freezing…" : `Freeze v${m.strategy?.version ?? ""} to paper`}</button>
      </div>
    </div>
  );
}

/** Alert channels (Apprise URLs: mailto://, tgram://, ntfy://, json://) and a test send. */
export function Alerts({ result }: ViewProps) {
  const m = meta(result);
  const sid = m.strategy?.id;
  const [urls, setUrls] = useState("");
  const save = () => sid && void studio("PUT", `/strategies/${sid}/channels`, { urls: urls.split(/\s+/) }).then(() => toast.success("Saved"), (e) => toast.error(e instanceof Error ? e.message : "Failed"));
  const test = () => sid && void studio<{ sent: { channel: string; ok: boolean; error: string | null }[] }>("POST", `/strategies/${sid}/test-alert`)
    .then((r) => r.sent.length ? r.sent.forEach((s) => (s.ok ? toast.success(`${s.channel} sent`) : toast.error(`${s.channel}: ${s.error}`))) : toast.error("No channels"), (e) => toast.error(e instanceof Error ? e.message : "Failed"));
  return (
    <div style={{ display: "grid", gap: 8 }}>
      <p className="bd-find"><b>Channels</b>{m.channels.length ? m.channels.join(", ") : "none"}</p>
      <textarea className="input" rows={2} aria-label="Channel URLs" placeholder="tgram://bot/chat  mailto://user:pass@gmail.com" value={urls} onChange={(e) => setUrls(e.target.value)} />
      <div style={{ display: "flex", gap: 8 }}>
        <button className="btn sm" disabled={!sid || !urls.trim()} onClick={save}>Save channels</button>
        <button className="btn sm" disabled={!sid} onClick={test}>Send test</button>
      </div>
    </div>
  );
}

/** Real trades against the strategy's. */
export function Reconcile({ result }: ViewProps) {
  const r = meta(result).reconcile;
  if (!r?.real) return <Skipped reason="paste real trades (date,symbol,side,price) in settings" />;
  return <div className="st-fig"><b>{pct(r.same_share ?? 0, 0)}</b><span>{r.matched} of {r.model} strategy trades taken · {r.skipped} skipped · {r.extra} extra · fills {isNum(r.avg_fill_bps) ? `${r.avg_fill_bps.toFixed(0)} bps` : "—"} vs model</span></div>;
}
