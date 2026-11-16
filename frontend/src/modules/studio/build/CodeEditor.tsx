"use client";

import Editor, { type Monaco, type OnMount } from "@monaco-editor/react";
import { useEffect, useRef } from "react";
import type { Finding } from "../api";

type Ed = Parameters<OnMount>[0];

/** What `ctx` offers inside on_bar: the completion list and hover docs. */
const CTX: [string, string, string][] = [
  ["close", "History", "Closes: close[-1] is this bar, close[-2] the one before, close[-20:] the last 20"],
  ["open", "History", "Opens, indexed like close"],
  ["high", "History", "Highs, indexed like close"],
  ["low", "History", "Lows, indexed like close"],
  ["volume", "History", "Volumes, indexed like close"],
  ["position", "int", "1 long, -1 short, 0 flat"],
  ["symbol", "str", "Ticker of the name being stepped"],
  ["date", "str", "Date of this bar, YYYY-MM-DD"],
  ["bar", "int", "Index of this bar"],
  ["params", "dict", "Strategy parameters by name"],
  ["value(expr)", "float", "A formula's value on this bar: ctx.value(\"rsi(close, 14)\")"],
  ["rule(expr)", "bool", "A formula's truth on this bar: ctx.rule(\"close > sma(close, 200)\")"],
  ["param(name)", "float", "One parameter: ctx.param(\"fast\")"],
  ["buy()", "order", "Enter long at the next open"],
  ["sell()", "order", "Exit long at the next open"],
  ["short()", "order", "Enter short at the next open"],
  ["cover()", "order", "Exit short at the next open"],
];
const SNIPPETS: [string, string, string][] = [
  ["strategy", "Strategy class", "class Strategy:\n    def init(self, ctx):\n        ${1:pass}\n\n    def on_bar(self, ctx):\n        ${2:pass}\n\n    def on_fill(self, ctx):\n        ${3:pass}\n"],
  ["entry", "Buy on a rule", "if ctx.position == 0 and ctx.rule(\"${1:close > sma(close, 200)}\"):\n    ctx.buy()"],
  ["exit", "Sell on a rule", "if ctx.position > 0 and ctx.rule(\"${1:close < sma(close, 200)}\"):\n    ctx.sell()"],
  ["held", "Bars held counter", "self.held = self.held + 1 if ctx.position else 0"],
];

let registered = false;
function register(monaco: Monaco, catalogue: () => string[]) {
  if (registered) return;
  registered = true;
  const K = monaco.languages.CompletionItemKind;
  monaco.languages.registerCompletionItemProvider("python", {
    triggerCharacters: [".", "\""],
    provideCompletionItems: (model, pos) => {
      const word = model.getWordUntilPosition(pos);
      const range = { startLineNumber: pos.lineNumber, endLineNumber: pos.lineNumber, startColumn: word.startColumn, endColumn: word.endColumn };
      const before = model.getLineContent(pos.lineNumber).slice(0, pos.column - 1);
      if (/ctx\.(value|rule)\("[^"]*$/.test(before)) {
        return { suggestions: catalogue().map((c) => ({ label: c, kind: K.Function, insertText: c, range })) };
      }
      if (/ctx\.\w*$/.test(before)) {
        return { suggestions: CTX.map(([n, t, d]) => ({ label: n, kind: n.includes("(") ? K.Method : K.Property, detail: t, documentation: d,
          insertText: n.includes("(") ? n.replace(/\(.*\)/, n.endsWith("()") ? "()" : "(\"$1\")") : n, insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet, range })) };
      }
      return { suggestions: SNIPPETS.map(([l, d, s]) => ({ label: l, kind: K.Snippet, detail: d, insertText: s, insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet, range })) };
    },
  });
  monaco.languages.registerHoverProvider("python", {
    provideHover: (model, pos) => {
      const w = model.getWordAtPosition(pos);
      const line = model.getLineContent(pos.lineNumber);
      if (!w || line.slice(Math.max(0, w.startColumn - 5), w.startColumn - 1) !== "ctx.") return null;
      const hit = CTX.find(([n]) => n.split("(")[0] === w.word);
      return hit ? { contents: [{ value: `**ctx.${hit[0]}** → \`${hit[1]}\`` }, { value: hit[2] }] } : null;
    },
  });
}

/** Build › Python: Monaco with ctx completion, formula completion inside ctx.value/rule, and server findings as markers. */
export function CodeEditor({ value, onChange, findings, runtime, catalogue, onSave, onRun }: {
  value: string; onChange: (v: string) => void; findings: Finding[]; runtime: { line: number | null; message: string } | null; catalogue: string[];
  onSave: () => void; onRun: () => void;
}) {
  const ed = useRef<{ editor: Ed; monaco: Monaco } | null>(null);
  const cat = useRef(catalogue); cat.current = catalogue;
  const keys = useRef({ onSave, onRun }); keys.current = { onSave, onRun };

  useEffect(() => {
    const m = ed.current; if (!m) return;
    const model = m.editor.getModel(); if (!model) return;
    const marks = findings.map((f) => ({ severity: f.severity === "error" ? m.monaco.MarkerSeverity.Error : m.monaco.MarkerSeverity.Warning, message: f.message,
      startLineNumber: Math.max(1, f.line), endLineNumber: Math.max(1, f.line), startColumn: f.start + 1, endColumn: Math.max(f.end, f.start + 1) + 1 }));
    if (runtime?.line) marks.push({ severity: m.monaco.MarkerSeverity.Error, message: runtime.message, startLineNumber: runtime.line, endLineNumber: runtime.line, startColumn: 1, endColumn: model.getLineMaxColumn(runtime.line) });
    m.monaco.editor.setModelMarkers(model, "studio", marks);
  }, [findings, runtime]);

  const mount: OnMount = (editor, monaco) => {
    ed.current = { editor, monaco };
    register(monaco, () => cat.current);
    editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => keys.current.onSave());
    editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter, () => keys.current.onRun());
  };
  const dark = typeof document === "undefined" || document.documentElement.dataset.theme !== "light";

  return (
    <div className="bd-code-ed">
      <Editor language="python" value={value} onChange={(v) => onChange(v ?? "")} onMount={mount} theme={dark ? "vs-dark" : "light"} height={420}
        options={{ minimap: { enabled: false }, fontSize: 13, lineNumbersMinChars: 3, scrollBeyondLastLine: false, tabSize: 4, renderLineHighlight: "line", automaticLayout: true,
          padding: { top: 10 }, fontFamily: "var(--font-mono), ui-monospace, monospace", quickSuggestions: { strings: true, other: true, comments: false } }} />
    </div>
  );
}
