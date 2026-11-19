"use client";

import Editor, { type Monaco, type OnMount } from "@monaco-editor/react";
import { useEffect, useRef } from "react";
import { studio } from "../api";

type Ed = Parameters<OnMount>[0];
export type Problem = { severity: string; file: string; line: number; column: number; end_column: number; code: string; message: string };
type Member = { name: string; kind: string; signature: string | null; documentation: string | null; insert_text?: string | null };
type Project = { file: string; files: Record<string, string>; params: string[]; symbols: string[]; goto: (file: string, line: number, column?: number) => void };

/** The open project, read by the Monaco providers (registered once per page load). */
const live: { current: Project | null } = { current: null };

const SNIPPETS: [string, string, string][] = [
  ["strategy", "Per-symbol strategy", "class Strategy:\n    def init(self, ctx):\n        ${1:pass}\n\n    def on_bar(self, ctx):\n        ${2:pass}\n"],
  ["portfolio", "Portfolio strategy", "class Strategy:\n    def init(self, ctx):\n        ${1:pass}\n\n    def on_data(self, ctx):\n        ${2:pass}\n"],
  ["entry", "Buy on a rule", "if ctx.position == 0 and ctx.rule(\"${1:close > sma(close, 200)}\"):\n    ctx.buy()"],
  ["exit", "Sell on a rule", "if ctx.position > 0 and ctx.rule(\"${1:close < sma(close, 200)}\"):\n    ctx.sell()"],
  ["fill", "Fill handler", "def on_fill(self, ctx, fill):\n    ctx.log(f\"{fill.side} {fill.quantity} {fill.symbol} @ {fill.price}\")"],
];

/** Which completion list applies at the cursor, from the text before it. */
function scopeAt(before: string): string | null {
  if (/ctx\.(value|rule)\("[^"]*$/.test(before)) return "formula";
  if (/ctx\.param\("[^"]*$/.test(before)) return "param";
  if (/ctx\.history\("[^"]*$/.test(before)) return "history_field";
  if (/(set_holdings|market_order|liquidate|limit_order|stop_order|indicator)\([^)]*"[^"]*$/.test(before)) return "symbol";
  const m = /\b(ctx|self|np|numpy|pd|pandas|math|statistics)\.\w*$/.exec(before);
  if (!m) return null;
  return ({ np: "numpy", pd: "pandas" } as Record<string, string>)[m[1]] ?? m[1];
}

let registered = false;
function register(monaco: Monaco) {
  if (registered) return;
  registered = true;
  const K = monaco.languages.CompletionItemKind;
  const kind = (k: string) => ({ method: K.Method, function: K.Function, field: K.Field, property: K.Property, module: K.Module, class: K.Class, constant: K.Constant }[k] ?? K.Variable);
  const doc = (m: Member) => [m.signature ? `\`${m.signature}\`` : "", m.documentation ?? ""].filter(Boolean).join("\n\n");
  monaco.languages.registerCompletionItemProvider("python", {
    triggerCharacters: [".", "\""],
    provideCompletionItems: async (model, pos) => {
      const word = model.getWordUntilPosition(pos);
      const range = { startLineNumber: pos.lineNumber, endLineNumber: pos.lineNumber, startColumn: word.startColumn, endColumn: word.endColumn };
      const before = model.getLineContent(pos.lineNumber).slice(0, pos.column - 1);
      const scope = scopeAt(before);
      if (!scope) return { suggestions: SNIPPETS.map(([l, d, s]) => ({ label: l, kind: K.Snippet, detail: d, insertText: s, insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet, range })) };
      const p = live.current;
      const items = await studio<Member[]>("POST", "/build/complete", { scope, code: model.getValue(), prefix: "", params: p?.params ?? [], symbols: p?.symbols ?? [] }).catch(() => []);
      return { suggestions: items.map((m) => ({ label: m.name, kind: kind(m.kind), detail: m.signature ?? m.kind, documentation: { value: doc(m) }, insertText: m.insert_text ?? m.name, range })) };
    },
  });
  monaco.languages.registerSignatureHelpProvider("python", {
    signatureHelpTriggerCharacters: ["(", ","],
    provideSignatureHelp: async (model, pos) => {
      const before = model.getValueInRange({ startLineNumber: pos.lineNumber, startColumn: 1, endLineNumber: pos.lineNumber, endColumn: pos.column });
      const open = before.lastIndexOf("(");
      const call = /\b(ctx|self|np|numpy|pd|pandas|math|statistics)\.(\w+)$/.exec(before.slice(0, open));
      if (open < 0 || !call) return null;
      const scope = ({ np: "numpy", pd: "pandas" } as Record<string, string>)[call[1]] ?? call[1];
      const m = await studio<Member | null>("POST", "/build/signature", { scope, name: call[2], code: model.getValue() }).catch(() => null);
      if (!m?.signature) return null;
      const args = m.signature.slice(m.signature.indexOf("(") + 1, m.signature.lastIndexOf(")")).split(",").map((s) => s.trim()).filter(Boolean);
      const active = (before.slice(open).match(/,/g) ?? []).length;
      return { value: { signatures: [{ label: m.signature, documentation: m.documentation ?? undefined, parameters: args.map((a) => ({ label: a })) }], activeSignature: 0, activeParameter: Math.min(active, Math.max(0, args.length - 1)) }, dispose: () => undefined };
    },
  });
  monaco.languages.registerDefinitionProvider("python", {
    provideDefinition: async (model, pos) => {
      const p = live.current;
      if (!p) return null;
      const hits = await studio<{ file: string; line: number; column: number }[]>("POST", "/build/definition", { code: model.getValue(), file: p.file, files: p.files, line: pos.lineNumber, column: pos.column }).catch(() => []);
      const same = hits.filter((h) => h.file === p.file);
      if (!same.length && hits[0]) { p.goto(hits[0].file, hits[0].line, hits[0].column); return null; }
      return same.map((h) => ({ uri: model.uri, range: new monaco.Range(h.line, h.column, h.line, h.column) }));
    },
  });
}

/** Resolve a CSS colour (oklch, var) to #rrggbb for Monaco's theme. */
function hex(css: string, fallback: string): string {
  if (typeof document === "undefined") return fallback;
  const c = document.createElement("canvas").getContext("2d");
  if (!c) return fallback;
  c.fillStyle = fallback; c.fillStyle = css; c.fillRect(0, 0, 1, 1);
  const [r, g, b, a] = c.getImageData(0, 0, 1, 1).data;
  return `#${[r, g, b, ...(a < 255 ? [a] : [])].map((v) => v.toString(16).padStart(2, "0")).join("")}`;
}
function theme(monaco: Monaco, dark: boolean) {
  const el = document.querySelector(".ws") ?? document.documentElement;
  const v = (n: string, f: string) => hex(getComputedStyle(el).getPropertyValue(n).trim() || f, f);
  const bg = v("--island", dark ? "#16181d" : "#ffffff"), text = v("--text", dark ? "#e6e6e6" : "#111111"), muted = v("--text-3", "#7a7f87"), line = v("--line", dark ? "#262a31" : "#e6e6e6");
  monaco.editor.defineTheme("studio", { base: dark ? "vs-dark" : "vs", inherit: true, rules: [{ token: "comment", foreground: muted.slice(1, 7), fontStyle: "italic" }],
    colors: { "editor.background": bg, "editor.foreground": text, "editorLineNumber.foreground": muted, "editorLineNumber.activeForeground": text, "editor.lineHighlightBackground": line, "editor.lineHighlightBorder": "#00000000", "editorGutter.background": bg, "editorWidget.background": bg, "editorWidget.border": line, "editorIndentGuide.background1": line } });
  monaco.editor.setTheme("studio");
}

/** Build › Dev: Monaco for one project file, with server completion, signature help, go to definition and line markers. */
export function CodeEditor({ path, value, onChange, problems, project, onSave, onRun, onCursor, reveal }: {
  path: string; value: string; onChange: (v: string) => void; problems: Problem[]; project: Project;
  onSave: () => void; onRun: () => void; onCursor?: (line: number, column: number) => void; reveal?: { line: number; column?: number; n: number } | null;
}) {
  const ed = useRef<{ editor: Ed; monaco: Monaco } | null>(null);
  const keys = useRef({ onSave, onRun, onCursor }); keys.current = { onSave, onRun, onCursor };
  live.current = project;

  useEffect(() => {
    const m = ed.current; if (!m) return;
    const model = m.editor.getModel(); if (!model) return;
    m.monaco.editor.setModelMarkers(model, "studio", problems.map((f) => ({ severity: f.severity === "error" ? m.monaco.MarkerSeverity.Error : f.severity === "warning" ? m.monaco.MarkerSeverity.Warning : m.monaco.MarkerSeverity.Info,
      message: f.message, code: f.code, startLineNumber: Math.max(1, f.line), endLineNumber: Math.max(1, f.line), startColumn: Math.max(1, f.column), endColumn: Math.max(f.end_column, f.column + 1) })));
  }, [problems, path]);

  useEffect(() => {
    const m = ed.current; if (!m || !reveal) return;
    m.editor.revealLineInCenter(reveal.line); m.editor.setPosition({ lineNumber: reveal.line, column: reveal.column ?? 1 }); m.editor.focus();
  }, [reveal, path]);

  useEffect(() => {
    const m = ed.current; if (!m) return;
    const obs = new MutationObserver(() => theme(m.monaco, document.documentElement.dataset.theme !== "light"));
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme", "class"] });
    return () => obs.disconnect();
  }, []);

  const mount: OnMount = (editor, monaco) => {
    ed.current = { editor, monaco };
    register(monaco);
    theme(monaco, document.documentElement.dataset.theme !== "light");
    editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => keys.current.onSave());
    editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter, () => keys.current.onRun());
    editor.onDidChangeCursorPosition((e) => keys.current.onCursor?.(e.position.lineNumber, e.position.column));
  };

  return (
    <Editor language="python" path={path} value={value} onChange={(v) => onChange(v ?? "")} onMount={mount} theme="studio" height="100%"
      options={{ minimap: { enabled: false }, fontSize: 13, lineHeight: 20, fontLigatures: false, lineNumbersMinChars: 3, scrollBeyondLastLine: false, tabSize: 4, renderLineHighlight: "line", automaticLayout: true,
        padding: { top: 10 }, fontFamily: "'JetBrains Mono', var(--font-mono), ui-monospace, monospace", quickSuggestions: { strings: true, other: true, comments: false },
        bracketPairColorization: { enabled: true }, stickyScroll: { enabled: true }, folding: true, guides: { indentation: true, bracketPairs: true } }} />
  );
}
