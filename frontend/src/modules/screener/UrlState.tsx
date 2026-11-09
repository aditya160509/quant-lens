"use client";

import { useEffect, useRef } from "react";
import { useParams } from "next/navigation";
import { debounce, parseAsJson, useQueryState } from "nuqs";
import { useTableViews, type TableView } from "@/kit/tableView";
import { useStudies } from "@/modules/research/store";
import type { FormState } from "@/modules/research/StudyForm";
import { SCREENER_LAB } from "./screenerLab";

const object = (v: unknown) => (v && typeof v === "object" && !Array.isArray(v) ? v : null);
const options = { limitUrlUpdates: debounce(400) };
const RESULTS = "screener:results";

/** The page's settings and its results table's arrangement, kept in the address so any view is a link. */
export function UrlState() {
  const slug = useParams<{ feature?: string }>().feature;
  const id = Object.entries(SCREENER_LAB.catalog).find(([, meta]) => meta.slug === slug)?.[0];
  const [form, setForm] = useQueryState("form", parseAsJson((v) => object(v) as FormState | null).withOptions(options));
  const [table, setTable] = useQueryState("table", parseAsJson((v) => object(v) as TableView | null).withOptions(options));
  const live = useStudies((s) => (id ? s.forms[id] : undefined));
  const arranged = useTableViews((s) => s.live[RESULTS]);
  const loaded = useRef(false);

  useEffect(() => {
    if (loaded.current) return;
    loaded.current = true;
    if (id && form) useStudies.setState((s) => ({ forms: { ...s.forms, [id]: form } }));
    if (table) useTableViews.getState().set(RESULTS, table);
  }, [id, form, table]);
  useEffect(() => { if (live && loaded.current) void setForm(live); }, [live, setForm]);
  useEffect(() => { if (arranged && loaded.current) void setTable(arranged); }, [arranged, setTable]);
  return null;
}
