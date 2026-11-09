import { autocompletion, type CompletionContext } from "@codemirror/autocomplete";
import { EditorState } from "@codemirror/state";
import { EditorView, keymap, placeholder } from "@codemirror/view";
import { useEffect, useRef } from "react";

export interface FormulaBarProps {
  value: string;
  onChange: (value: string) => void;
  fields: string[];
  functions: string[];
  error?: string | null;
  onSubmit?: () => void;
}

export function FormulaBar({ value, onChange, fields, functions, error, onSubmit }: FormulaBarProps) {
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
      {error ? <div role="alert">{error}</div> : null}
    </div>
  );
}
