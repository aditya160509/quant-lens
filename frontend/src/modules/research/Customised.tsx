"use client";

import * as Popover from "@radix-ui/react-popover";
import { RotateCcw, X } from "lucide-react";
import { defaultsFor, type FormState } from "./StudyForm";
import type { FeatureSpec } from "./types";

const show = (v: unknown) => (Array.isArray(v) ? v.join(", ") : v === "" || v === null || v === undefined ? "—" : String(v));

/** One marker when the settings differ from the defaults; it opens the list of what changed, each with its own reset. */
export function Customised({ feature, form, setForm }: { feature: FeatureSpec; form: FormState; setForm: (f: (c: FormState) => FormState) => void }) {
  const base = defaultsFor(feature);
  const diff = feature.inputs.filter((f) => JSON.stringify(form[f.key] ?? "") !== JSON.stringify(base[f.key] ?? ""));
  if (!diff.length) return null;
  return (
    <Popover.Root>
      <Popover.Trigger asChild><button type="button" className="custom-chip">Customised<b className="num">{diff.length}</b></button></Popover.Trigger>
      <Popover.Portal container={typeof document === "undefined" ? undefined : document.querySelector<HTMLElement>(".ws")}>
        <Popover.Content className="popover custom-pop" align="start" sideOffset={6} collisionPadding={12}>
          {diff.map((f) => (
            <div key={f.key} className="custom-row">
              <span>{f.label}</span>
              <span className="num"><s>{show(base[f.key])}</s>{show(form[f.key])}</span>
              <button type="button" className="btn sm ghost icon" aria-label={`Reset ${f.label}`} onClick={() => setForm((c) => ({ ...c, [f.key]: base[f.key] }))}><X size={12} /></button>
            </div>
          ))}
          <button type="button" className="btn sm" style={{ marginTop: 6, width: "100%", justifyContent: "center" }} onClick={() => setForm(() => base)}><RotateCcw size={12} />Reset all</button>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
