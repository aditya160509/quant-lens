import { autocompletion, type CompletionContext } from "@codemirror/autocomplete";
import { EditorState } from "@codemirror/state";
import { Decoration, EditorView, MatchDecorator, ViewPlugin, keymap, placeholder, type DecorationSet, type ViewUpdate } from "@codemirror/view";
import { useEffect, useRef, type ReactNode } from "react";

export interface FormulaBarProps {
  value: string;
  onChange: (value: string) => void;
  fields: string[];
  functions: string[];
  error?: string | null;
  /** Shown under the editor, e.g. what the formula gives today. */
  preview?: ReactNode;
  onSubmit?: () => void;
}

const theme = EditorView.theme({
  "&": { fontSize: "13px", background: "var(--panel-2)", borderRadius: "8px", boxShadow: "inset 0 0 0 1px var(--line)" },
  ".cm-content": { fontFamily: "var(--mono)", padding: "8px 10px" },
  ".cm-fn": { color: "var(--accent)" },
  ".cm-num": { color: "var(--text-2)" },
  ".cm-unknown": { textDecoration: "underline wavy var(--down)" },
});

/** Colours functions, numbers and known fields; an unknown word is underlined. */
const highlight = (known: Set<string>, functions: Set<string>) => {
  const deco = new MatchDecorator({
    regexp: /[A-Za-z_][A-Za-z0-9_]*|\d+(?:\.\d+)?/g,
    decoration: (m) => Decoration.mark({ class: /^\d/.test(m[0]) ? "cm-num" : functions.has(m[0]) ? "cm-fn" : known.has(m[0]) ? "cm-field" : "cm-unknown" }),
  });
  return ViewPlugin.fromClass(class {
    decorations: DecorationSet;
    constructor(view: EditorView) { this.decorations = deco.createDeco(view); }
    update(u: ViewUpdate) { this.decorations = deco.updateDeco(u, this.decorations); }
  }, { decorations: (v) => v.decorations });
};

export function FormulaBar({ value, onChange, fields, functions, error, preview, onSubmit }: FormulaBarProps) {
  const host = useRef<HTMLDivElement>(null);
  const view = useRef<EditorView | null>(null);
  const cb = useRef({ onChange, onSubmit });
  cb.current = { onChange, onSubmit };

  useEffect(() => {
    const complete = (ctx: CompletionContext) => {
      const word = ctx.matchBefore(/[A-Za-z_][A-Za-z0-9_]*/);
      if (!word || (word.from === word.to && !ctx.explicit)) return null;
      return {
        from: word.from,
        options: [
          ...fields.map((label) => ({ label, type: "variable" })),
          ...functions.map((label) => ({ label, type: "function", apply: `${label}(` })),
        ],
      };
    };
    const v = new EditorView({
      parent: host.current!,
      state: EditorState.create({
        doc: value,
        extensions: [
          theme,
          highlight(new Set(fields), new Set([...functions, "if"])),
          autocompletion({ override: [complete] }),
          keymap.of([{ key: "Mod-Enter", run: () => (cb.current.onSubmit?.(), true) }]),
          placeholder("rank(roe) + zscore(momentum_jt)"),
          EditorView.updateListener.of((u) => u.docChanged && cb.current.onChange(u.state.doc.toString())),
        ],
      }),
    });
    view.current = v;
    return () => v.destroy();
  }, [fields, functions]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const v = view.current;
    if (v && v.state.doc.toString() !== value) v.dispatch({ changes: { from: 0, to: v.state.doc.length, insert: value } });
  }, [value]);

  return (
    <div>
      <div ref={host} aria-invalid={!!error} />
      {error ? <div role="alert" style={{ color: "var(--down)", fontSize: 12, marginTop: 4 }}>{error}</div> : preview ? <div style={{ color: "var(--text-3)", fontSize: 12, marginTop: 4 }}>{preview}</div> : null}
    </div>
  );
}
