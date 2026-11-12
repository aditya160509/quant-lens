"use client";

import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useMemo, useState, useSyncExternalStore } from "react";
import { Bookmark, ClipboardCheck, FlaskConical, GitCompare, History, LayoutGrid, Trash2, X } from "lucide-react";
import { Group, Panel, Separator, useDefaultLayout } from "react-resizable-panels";
import { create } from "zustand";
import { useLayout } from "@/workspace/layout";
import { useRegionPanel } from "@/workspace/panels";
import { useWorkspace } from "@/workspace/WorkspaceShell";
import { Dot } from "@/workspace/ui";
import { ApiError, cancelJob, latestRun, metricsOf, studyPart, useActiveSignal, useLibrary, useBackgroundRuns, useJob, useManifest, useRuns, useSubmitJob } from "./api";
import { featureHref, idFromSlug, metaFor, pageHref, pageOf, specialPage } from "./catalog";
import { lab, owns, setLab, type LabConfig } from "./lab";
import { RESEARCH_LAB } from "./researchLab";
import { SignalPage } from "./SignalPage";
import { ReportCardPage } from "./ReportCard";
import { SharedView } from "./SharedView";
import { ProjectSwitcher } from "./Projects";
import { Dock } from "./Dock";
import { FeatureView } from "./FeatureView";
import { Inspector, OverviewInspector } from "./Inspector";
import { verdictFor } from "./layouts";
import { Overview } from "./Overview";
import { sweepValues, useStudies, useSweeps } from "./store";
import { useViews } from "@/workspace/views";
import { decodeSettings, defaultsFor, toPayload, validate, type FormState } from "./StudyForm";
import type { FeatureSpec, RunRecord } from "./types";

/** Panel sizes persist per device; reads are safe during server rendering and in private windows. */
const panelStorage = {
  getItem: (key: string) => { try { return typeof window === "undefined" ? null : window.localStorage.getItem(key); } catch { return null; } },
  setItem: (key: string, value: string) => { try { window.localStorage.setItem(key, value); } catch { /* storage unavailable */ } },
};

const noopSubscribe = () => () => {};

/**
 * Panel sizes come from this device's storage, so the panel layout renders on the client only;
 * a server render would hydrate with different flex sizes that React does not patch.
 */
export function ResearchApp({ config = RESEARCH_LAB }: { config?: LabConfig }) {
  // The lab is set before any child renders; every shared component reads it through lab().
  setLab(config);
  const mounted = useSyncExternalStore(noopSubscribe, () => true, () => false);
  return mounted ? <ResearchPanels key={config.id} /> : <div className="island" style={{ height: "100%" }} />;
}

function ResearchPanels() {
  const L = lab();
  const params = useParams<{ feature?: string; token?: string }>();
  const featureId = idFromSlug(params?.feature);
  const special = specialPage(params?.feature);
  const sharedToken = (params as { token?: string } | null)?.token ?? null;
  const verifiedId = (params as { id?: string } | null)?.id ?? null;
  const Special = verifiedId ? L.specials?.verified : special ? L.specials?.[special.id] : undefined;
  const embed = useSearchParams()?.get("embed") === "1";
  useEffect(() => {
    if (!embed) return;
    document.documentElement.dataset.embed = "1";
    return () => { delete document.documentElement.dataset.embed; };
  }, [embed]);
  const manifest = useManifest();
  const feature = manifest.data?.find((f) => f.id === featureId) ?? null;
  const { setCrumb, registerPalette } = useWorkspace();
  const router = useRouter();
  const allRuns = useRuns((s) => s.runs);
  const runs = useMemo(() => allRuns.filter((r) => owns(r.featureId)), [allRuns]);
  const animate = useLayout((s) => s.animate);
  const narrow = useSyncExternalStore(subscribeNarrow, () => window.matchMedia("(max-width: 760px)").matches, () => false);
  const shownJob = useSearchParams()?.get("run") ?? (featureId ? runs.find((r) => r.featureId === featureId)?.jobId ?? null : null);
  useBackgroundRuns(manifest.data, shownJob, verdictFor);
  useDoneInTitle(runs);

  // Some pages start with the inspector shut; it opens on demand for advanced settings.
  useEffect(() => { if (featureId && L.inspectorClosed?.includes(featureId)) useLayout.getState().set("right", false); }, [featureId, L.inspectorClosed]);

  useEffect(() => setCrumb(verifiedId ? "Verified result" : special ? special.label : sharedToken ? "Shared run" : feature ? metaFor(feature.id, feature.name).name : "Overview"), [feature, special, sharedToken, verifiedId, setCrumb]);

  useEffect(() => {
    if (!animate) return;
    const id = setTimeout(() => useLayout.setState({ animate: false }), 320);
    return () => clearTimeout(id);
  }, [animate]);

  const views = useViews((s) => s.views);
  useEffect(() => {
    registerPalette("views", [
      { id: "view-save", group: "Workspaces", icon: Bookmark, label: "Save current workspace as view…", run: () => {
        const name = window.prompt("Name this workspace view")?.trim();
        if (!name) return;
        const fid = featureId;
        useViews.getState().save({ name, featureId: fid, open: useLayout.getState().open, form: fid ? useStudies.getState().forms[fid] ?? {} : {} });
      } },
      ...views.flatMap((v) => [
        { id: `view-open-${v.id}`, group: "Workspaces", icon: Bookmark, label: `Open view: ${v.name}`, meta: v.featureId ? metaFor(v.featureId, v.featureId).name : "Overview", run: () => {
          const l = useLayout.getState();
          (["left", "right", "bottom"] as const).forEach((r) => l.set(r, v.open[r], true));
          if (v.featureId) {
            const f = v.form;
            useStudies.setState((s) => ({ forms: { ...s.forms, [v.featureId as string]: f } }));
            router.push(featureHref(v.featureId));
          } else router.push(L.root);
        } },
        { id: `view-del-${v.id}`, group: "Workspaces", icon: Trash2, label: `Delete view: ${v.name}`, run: () => useViews.getState().remove(v.id) },
      ]),
    ]);
  }, [views, featureId, registerPalette, router, L.root]);

  useEffect(() => {
    if (!manifest.data) return;
    registerPalette(L.id, [
      { id: `${L.id}-overview`, group: L.title, label: "Overview", icon: LayoutGrid, run: () => router.push(L.root) },
      ...manifest.data.map((f) => {
        const m = metaFor(f.id, f.name);
        return { id: `feature-${f.id}`, group: L.title, icon: m.icon, label: m.name, keywords: [f.name, f.description, m.question], meta: latestRun(runs, f.id)?.headline?.split(".")[0], run: () => router.push(featureHref(f.id)) };
      }),
      ...runs.slice(0, 8).map((r) => ({
        id: `run-${r.jobId}`, group: "Recent runs", icon: History, label: `${metaFor(r.featureId, r.featureName).name}${r.signal ? ` · ${r.signal}` : ""}`,
        meta: new Date(r.startedAt).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }),
        run: () => router.push(`${featureHref(r.featureId)}?run=${r.jobId}`),
      })),
    ]);
  }, [manifest.data, runs, registerPalette, router, L]);

  // Actions: pages, the active signal, report card, comparisons; the library as one-step signal loads.
  const library = useLibrary(L.signal);
  useEffect(() => {
    const go = (href: string) => () => router.push(href);
    const done = runs.filter((r) => r.status === "completed");
    registerPalette(`${L.id}-actions`, [
      ...L.pages.map((p) => ({ id: `page-${p.id}`, group: "Pages", icon: p.icon, label: p.label, keywords: [p.question], run: go(pageHref(p)) })),
      ...(L.signal ? [
        { id: "act-report", group: "Actions", icon: ClipboardCheck, label: "Run the report card on the active signal", run: go(`${L.root}/report`) },
        { id: "act-clear-signal", group: "Actions", icon: X, label: "Use each page's built-in signal (clear formula)", run: () => useActiveSignal.getState().set({ expr: null, name: null }) },
      ] : []),
      ...(done.length >= 2 ? [{ id: "act-compare", group: "Actions", icon: GitCompare, label: "Compare the last two runs", run: () => { useLayout.getState().set("bottom", true, true); window.dispatchEvent(new CustomEvent("research:compare", { detail: [done[0].jobId, done[1].jobId] })); } }] : []),
      { id: "act-dock", group: "Actions", icon: History, label: "Show runs and log", run: () => useLayout.getState().set("bottom", true, true) },
      ...(library.data ?? []).map((s) => ({ id: `lib-${s.id}`, group: "Published anomalies", icon: FlaskConical, label: `Test ${s.name}`, meta: s.citation, keywords: [s.category, s.formula], run: () => { useActiveSignal.getState().set({ expr: s.formula, name: s.name }); router.push(`${L.root}/signal`); } })),
    ]);
  }, [runs, library.data, registerPalette, router, L]);

  const outer = useDefaultLayout({ id: `${L.id}-columns-v2`, storage: panelStorage });
  const inner = useDefaultLayout({ id: `${L.id}-rows-v2`, storage: panelStorage });
  const left = useRegionPanel("left");
  const right = useRegionPanel("right");
  const bottom = useRegionPanel("bottom");

  const center = (
            <>{manifest.isError ? (
              <ErrorState message={(manifest.error as Error).message} busy={manifest.error instanceof ApiError && manifest.error.status === 429} onRetry={() => manifest.refetch()} />
            ) : sharedToken ? (
              <SharedView token={sharedToken} features={manifest.data ?? []} />
            ) : Special ? (
              <Special features={manifest.data ?? []} id={verifiedId ?? undefined} />
            ) : special?.id === "signal" && L.signal ? (
              <SignalPage />
            ) : special?.id === "report" && L.signal ? (
              <ReportCardPage features={manifest.data ?? []} />
            ) : feature ? (
              <FeatureWorkspace key={feature.id} feature={feature} />
            ) : (
              <Overview features={manifest.data ?? []} loading={manifest.isLoading} runs={runs} />
            )}</>
  );
  // Embedded share: the content alone, no workspace chrome, for an iframe on another site.
  if (sharedToken && embed) return <div style={{ height: "100%", display: "flex" }}>{center}</div>;
  if (narrow) {
    return (
      <div className="ws-mobile">
        <select className="input" aria-label="Page" value={special ? pageHref(special) : feature ? featureHref(feature.id) : L.root} onChange={(e) => router.push(e.target.value)}>
          <option value={L.root}>Overview</option>
          {L.pages.map((p) => <option key={p.id} value={pageHref(p)}>{p.label}</option>)}
        </select>
        <div style={{ flex: 1, minHeight: 0, display: "flex" }}>{center}</div>
      </div>
    );
  }

  return (
    <Group orientation="horizontal" id={`${L.id}-columns-v2`} className={animate ? "ws-animate" : undefined} defaultLayout={outer.defaultLayout} onLayoutChanged={outer.onLayoutChanged} style={{ height: "100%" }}>
      <Panel id="nav" panelRef={left.panelRef} onResize={left.onResize} defaultSize={left.defaultOpen ? 236 : 0} minSize={196} maxSize={340} collapsible collapsedSize={52}>
        <FeatureNav features={manifest.data ?? []} loading={manifest.isLoading} activeId={featureId} activePage={special?.id ?? pageOf(featureId)?.id ?? null} runs={runs} />
      </Panel>
      <Separator className="ws-sep" />
      <Panel id="center" minSize={460}>
        <Group orientation="vertical" id={`${L.id}-rows-v2`} className={animate ? "ws-animate" : undefined} defaultLayout={inner.defaultLayout} onLayoutChanged={inner.onLayoutChanged}>
          <Panel id="results" minSize={260}>
            <div style={{ position: "relative", height: "100%", display: "flex" }}>{center}<RunsPill runs={runs} /></div>
          </Panel>
          <Separator className="ws-sep h" />
          <Panel id="dock" panelRef={bottom.panelRef} onResize={bottom.onResize} defaultSize={bottom.defaultOpen ? 220 : 0} minSize={120} maxSize="85%" collapsible collapsedSize={0}>
            <Dock runs={runs} activeFeature={featureId} onMaximize={(on) => bottom.panelRef.current?.resize(on ? "75%" : 220)} />
          </Panel>
        </Group>
      </Panel>
      <Separator className="ws-sep" />
      <Panel id="inspector" panelRef={right.panelRef} onResize={right.onResize} defaultSize={right.defaultOpen ? 340 : 0} minSize={280} maxSize={560} collapsible collapsedSize={0}>
        {feature ? <InspectorHost feature={feature} /> : <OverviewInspector runs={runs} />}
      </Panel>
    </Group>
  );
}

function FeatureNav({ features, loading, activeId, activePage, runs }: { features: FeatureSpec[]; loading: boolean; activeId: string | null; activePage: string | null; runs: RunRecord[] }) {
  const have = new Set(features.map((f) => f.id));
  const L = lab();
  return (
    <nav className="island" aria-label={`${L.title} features`}>
      <div className="nav-h"><span>{L.title}</span></div>
      {L.signal ? <ProjectSwitcher /> : null}
      <div style={{ flex: 1, overflowY: "auto", paddingBottom: 8 }}>
        <Link href={L.root} className="nav-item" title="Overview" aria-current={activeId === null && activePage === null ? "page" : undefined}>
          <LayoutGrid size={15} strokeWidth={1.7} />
          <span className="label">Overview</span>
        </Link>
        <div style={{ height: 1, margin: "6px 16px", background: "var(--line)" }} />
        {loading ? Array.from({ length: 6 }, (_, i) => (
          <div key={i} className="nav-item"><span className="skel" style={{ width: 15, height: 15 }} /><span className="skel" style={{ width: 90 + ((i * 37) % 60), height: 10 }} /></div>
        )) : L.pages.filter((p) => !p.features.length || p.features.some((id) => have.has(id))).map((p) => {
          const Icon = p.icon;
          const ids = p.features.filter((id) => have.has(id));
          const live = runs.some((r) => ids.includes(r.featureId) && (r.status === "queued" || r.status === "running"));
          const tones = ids.map((id) => latestRun(runs, id)?.tone).filter(Boolean);
          const tone = tones.includes("down") ? "down" : tones.includes("warn") ? "warn" : tones.includes("up") ? "up" : null;
          const open = activePage === p.id;
          return (
            <div key={p.id}>
              <Link href={pageHref(p)} className="nav-item" aria-current={open && (p.slug || ids.length < 2) ? "page" : undefined} title={p.label}>
                <Icon size={15} strokeWidth={1.7} />
                <span className="label">{p.label}</span>
                <Dot live={live} tone={tone as RunRecord["tone"] ?? null} />
              </Link>
              {open && ids.length > 1 ? ids.map((id) => (
                <Link key={id} href={featureHref(id)} className="nav-item sub" aria-current={activeId === id ? "page" : undefined}>
                  <span className="label">{metaFor(id).name}</span>
                  <Dot tone={latestRun(runs, id)?.tone ?? null} />
                </Link>
              )) : null}
            </div>
          );
        })}
      </div>
    </nav>
  );
}

/** Owns the study state for one feature and connects the form, the job and the results. */
function useFeatureRun(feature: FeatureSpec) {
  const router = useRouter();
  const search = useSearchParams();
  const runs = useRuns((s) => s.runs);
  const addRun = useRuns((s) => s.add);
  const updateRun = useRuns((s) => s.update);
  const logRun = useRuns((s) => s.log);
  const defaults = useMemo(() => defaultsFor(feature), [feature]);
  const form = useStudies((s) => s.forms[feature.id]) ?? defaults;
  const setFormStore = useStudies((s) => s.setForm);
  const resetForm = useStudies((s) => s.resetForm);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const submit = useSubmitJob(feature.id);

  const jobId = search?.get("run") ?? runs.find((r) => r.featureId === feature.id)?.jobId ?? null;
  const job = useJob(jobId);
  const record = runs.find((r) => r.jobId === jobId);

  useEffect(() => {
    const data = job.data;
    if (!data || !jobId || !record || record.status === data.status) return;
    if (data.status === "completed" && data.result) {
      const v = verdictFor(feature, data.result);
      const secs = ((Date.now() - record.startedAt) / 1000).toFixed(1);
      updateRun(jobId, { status: "completed", headline: v.headline ?? undefined, tone: v.tone ?? undefined, metrics: metricsOf(data.result) });
      logRun(jobId, `Completed in ${secs}s`, "up");
      for (const c of data.result.meta.research_caveats ?? []) logRun(jobId, c, "warn");
    } else {
      updateRun(jobId, { status: data.status });
      logRun(jobId, data.status === "failed" ? `Failed: ${data.error ?? "unknown error"}` : `Status: ${data.status}`, data.status === "failed" ? "down" : undefined);
    }
  }, [job.data, jobId, feature, record, updateRun, logRun]);

  // Undo and redo over form edits; a burst of edits within 600 ms (typing, dragging) is one step.
  const past = useRef<FormState[]>([]);
  const future = useRef<FormState[]>([]);
  const lastEdit = useRef(0);
  const current = useCallback(() => useStudies.getState().forms[feature.id] ?? defaults, [feature.id, defaults]);
  const setForm = useCallback((updater: (cur: FormState) => FormState) => {
    const now = Date.now();
    if (now - lastEdit.current > 600) { past.current = [...past.current.slice(-49), current()]; future.current = []; }
    lastEdit.current = now;
    setFormStore(feature.id, updater, defaults);
  }, [feature.id, defaults, setFormStore, current]);
  const step = useCallback((from: typeof past, to: typeof past) => {
    const prev = from.current.at(-1);
    if (!prev) return false;
    from.current = from.current.slice(0, -1);
    to.current = [...to.current, current()];
    setFormStore(feature.id, () => prev, defaults);
    return true;
  }, [feature.id, defaults, setFormStore, current]);
  const undo = useCallback(() => step(past, future), [step]);
  const redo = useCallback(() => step(future, past), [step]);

  // A shared link carries its settings in ?s=; apply them once, then drop the parameter.
  const shared = search?.get("s");
  useEffect(() => {
    if (!shared) return;
    const v = decodeSettings(shared);
    if (v) setForm(() => ({ ...defaults, ...v }));
    const u = new URL(window.location.href); u.searchParams.delete("s"); router.replace(u.pathname + u.search, { scroll: false });
  }, [shared, setForm, defaults, router]);

  const run = useCallback(() => {
    const errs = validate(feature, form);
    setErrors(errs);
    if (Object.keys(errs).length) return;
    const active = useActiveSignal.getState();
    const context = lab().signal ? { ...(active.expr ? { signal_expr: active.expr } : {}), ...(active.projectId ? { project_id: active.projectId } : {}) } : {};
    const base: Record<string, unknown> = { ...toPayload(feature, form), ...context };
    const sweep = Object.entries(useSweeps.getState().sweeps[feature.id] ?? {}).map(([k, list]) => [k, sweepValues(list)] as const).filter(([, v]) => v.length);
    // One job per swept value (first swept field); the last submitted job is shown, all appear in the dock.
    const [sweepKey, sweepVals] = sweep[0] ?? [null, [null]];
    void (async () => {
      let lastId = "";
      const group = `${feature.id}:${sweepKey ?? ""}:${Date.now()}`;
      for (const v of sweepVals) {
        const payload = sweepKey ? { ...base, [sweepKey]: v } : base;
        try {
          const res = await submit.mutateAsync(payload);
          lastId = res.job_id;
          addRun({
            jobId: res.job_id, featureId: feature.id, featureName: feature.name, startedAt: Date.now(), status: res.status,
            signal: typeof payload.signal === "string" ? payload.signal : undefined, payload,
            sweep: sweepKey && typeof v === "number" ? { key: sweepKey, value: v, group } : undefined,
            log: [{ t: Date.now(), text: sweepKey ? `Sweep ${sweepKey} = ${String(v)}` : `Submitted with ${Object.keys(payload).length} settings` }],
          });
        } catch { break; }
      }
      if (lastId) router.replace(`${featureHref(feature.id)}?run=${lastId}`, { scroll: false });
      if (sweepKey && lastId) useLayout.getState().set("bottom", true, true);
    })();
  }, [feature, form, submit, addRun, router]);

  const cancel = useCallback(() => { if (jobId) void cancelJob(jobId).then(() => job.refetch()); }, [jobId, job]);
  const restore = useCallback(() => {
    if (record?.payload) setForm(() => ({ ...defaults, ...record.payload }));
  }, [record, setForm, defaults]);

  const stale = Boolean(record?.payload) && (() => { try { return JSON.stringify(studyPart(toPayload(feature, form))) !== JSON.stringify(studyPart(toPayload(feature, { ...defaults, ...record?.payload }))); } catch { return true; } })();
  const status = submit.isPending ? "submitting" : job.data?.status ?? (jobId && job.isLoading ? "loading" : "idle");
  return {
    form, setForm, undo, redo, errors, run, stale, cancel, status, record, restore, jobId, progress: job.data?.progress,
    reset: () => { resetForm(feature.id); setErrors({}); },
    result: job.data?.status === "completed" ? job.data.result ?? null : null,
    error: submit.error?.message ?? (job.error as Error | null)?.message ?? (job.data?.status === "failed" ? job.data.error ?? "The run failed." : null),
    startedAt: record?.startedAt ?? (job.data?.created_at ? Date.parse(job.data.created_at) : null),
  };
}

export type FeatureRun = ReturnType<typeof useFeatureRun>;

/** The center and the inspector share one run; a small store keeps them in sync across panels. */
const useActiveRun = create<{ run: FeatureRun | null; set: (r: FeatureRun | null) => void }>()((set) => ({ run: null, set: (run) => set({ run }) }));

function FeatureWorkspace({ feature }: { feature: FeatureSpec }) {
  const run = useFeatureRun(feature);
  const publish = useActiveRun((s) => s.set);
  useEffect(() => { publish(run); }, [run, publish]);
  useEffect(() => () => publish(null), [publish]);

  const router = useRouter();
  const go = useSearchParams()?.get("go") === "1";
  const fired = useRef(false);
  // Links from the overview arrive with ?go=1: run once with the settings they set, then drop the flag.
  useEffect(() => {
    if (!go || fired.current) return;
    fired.current = true;
    run.run();
    const u = new URL(window.location.href); u.searchParams.delete("go"); router.replace(u.pathname + u.search, { scroll: false });
  }, [go, run, router]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "Enter") { e.preventDefault(); run.run(); return; }
      const t = e.target as HTMLElement;
      // Form undo; a text field keeps its own.
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "z" && !t.isContentEditable && !/^(INPUT|TEXTAREA)$/.test(t.tagName)) {
        if (e.shiftKey ? run.redo() : run.undo()) e.preventDefault();
        return;
      }
      if (e.metaKey || e.ctrlKey || e.altKey || e.defaultPrevented || t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName) || document.querySelector("[role='dialog'], [role='menu']")) return;
      if (e.key === "[" || e.key === "]") {
        const pages = lab().pages;
        const i = pages.findIndex((p) => p.id === pageOf(feature.id)?.id);
        const next = pages[(i + (e.key === "]" ? 1 : -1) + pages.length) % pages.length];
        if (next) { e.preventDefault(); router.push(pageHref(next)); }
      } else if (e.key === "Escape") {
        const l = useLayout.getState();
        if (l.open.bottom) l.set("bottom", false, true);
        else if (l.open.right) l.set("right", false, true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [run, router, feature.id]);

  return <FeatureView feature={feature} run={run} />;
}

/** The runs dock while it is shut: one pill with what is running or failed; a click opens the dock. */
function RunsPill({ runs }: { runs: RunRecord[] }) {
  const open = useLayout((s) => s.open.bottom);
  if (open || !runs.length) return null;
  const live = runs.filter((r) => r.status === "queued" || r.status === "running").length;
  const failed = runs.filter((r) => r.status === "failed").length;
  return (
    <button type="button" className="runs-pill" aria-keyshortcuts="Meta+J" onClick={() => useLayout.getState().set("bottom", true, true)}>
      <Dot live={live > 0} tone={failed ? "down" : live ? null : "up"} />
      <span>{live ? `${live} running` : `${runs.length} runs`}</span>
      {failed ? <b>{failed} failed</b> : null}
    </button>
  );
}

function InspectorHost({ feature }: { feature: FeatureSpec }) {
  const run = useActiveRun((s) => s.run);
  if (!run) return <div className="island" />;
  return <Inspector feature={feature} run={run} />;
}

function ErrorState({ message, onRetry, busy = false }: { message: string; onRetry: () => void; busy?: boolean }) {
  return (
    <div className="island" style={{ alignItems: "center", justifyContent: "center", gap: 10, padding: 24, textAlign: "center" }}>
      <div style={{ fontWeight: 550, fontSize: 14 }}>{busy ? `${lab().title} service is busy` : `${lab().title} service is unreachable`}</div>
      <div style={{ color: "var(--text-3)", maxWidth: 420 }}>{busy ? "Too many requests in a short time. Wait a moment and retry." : `${message}. Start the backend and retry.`}</div>
      <button className="btn" onClick={onRetry}>Retry</button>
    </div>
  );
}

/** When a run finishes while the tab is hidden, say so in the tab title until the reader comes back. */
function useDoneInTitle(runs: RunRecord[]) {
  const done = runs.filter((r) => r.status === "completed" || r.status === "failed").map((r) => r.jobId).join(",");
  const seen = useRef<string | null>(null);
  useEffect(() => {
    const prev = seen.current;
    seen.current = done;
    if (prev === null || !document.hidden) return;
    const fresh = runs.find((r) => (r.status === "completed" || r.status === "failed") && !prev.split(",").includes(r.jobId));
    if (!fresh) return;
    const base = document.title.replace(/^[✓✕] .*? · /, "");
    document.title = `${fresh.status === "failed" ? "✕" : "✓"} ${metaFor(fresh.featureId, fresh.featureName).name} finished · ${base}`;
    const back = () => { if (!document.hidden) { document.title = base; document.removeEventListener("visibilitychange", back); } };
    document.addEventListener("visibilitychange", back);
  }, [done, runs]);
}

const subscribeNarrow = (cb: () => void) => { const m = window.matchMedia("(max-width: 760px)"); m.addEventListener("change", cb); return () => m.removeEventListener("change", cb); };
