import { create } from "zustand";
import type { FormState } from "./StudyForm";
import { useStudies } from "./store";

type Stack = Record<string, (FormState | null)[]>;
/** Undo and redo of each study's settings; a null entry is the untouched defaults. */
export const useFormHistory = create<{ past: Stack; future: Stack }>(() => ({ past: {}, future: {} }));

let applying = false;
const lastEdit: Record<string, number> = {};

// A burst of keystrokes is one step, so undo does not replay every digit.
useStudies.subscribe((s, p) => {
  if (applying) return;
  for (const id of Object.keys(s.forms)) {
    if (s.forms[id] === p.forms[id]) continue;
    const now = Date.now();
    if (now - (lastEdit[id] ?? 0) > 800) useFormHistory.setState((h) => ({ past: { ...h.past, [id]: [...(h.past[id] ?? []), p.forms[id] ?? null].slice(-50) }, future: { ...h.future, [id]: [] } }));
    lastEdit[id] = now;
  }
});

const restore = (id: string, form: FormState | null) => {
  applying = true;
  useStudies.setState((s) => {
    const { [id]: _, ...rest } = s.forms;
    void _;
    return { forms: form ? { ...rest, [id]: form } : rest };
  });
  applying = false;
  lastEdit[id] = 0;
};

function step(id: string, from: "past" | "future", to: "past" | "future") {
  const h = useFormHistory.getState();
  const list = h[from][id] ?? [];
  if (!list.length) return;
  const target = list[list.length - 1];
  useFormHistory.setState({ [from]: { ...h[from], [id]: list.slice(0, -1) }, [to]: { ...h[to], [id]: [...(h[to][id] ?? []), useStudies.getState().forms[id] ?? null] } });
  restore(id, target);
}

export const undo = (id: string) => step(id, "past", "future");
export const redo = (id: string) => step(id, "future", "past");
