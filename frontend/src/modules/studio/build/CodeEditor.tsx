"use client";

import Editor, { type Monaco, type OnMount } from "@monaco-editor/react";
import { useEffect, useRef } from "react";
import { studio } from "../api";
import { chordStarts, comboFromEvent } from "./keymap";

type Ed = Parameters<OnMount>[0];
type TextEdit = { line: number; column: number; end_line: number; end_column: number; text: string };
export type Problem = { severity: string; file: string; line: number; column: number; end_column: number; code: string; message: string; fix?: { title: string; edits: TextEdit[] } | null };
type Member = { name: string; kind: string; signature: string | null; documentation: string | null; insert_text?: string | null };
type UserSnippet = { name: string; prefix: string; body: string; description: string };
type Project = { file: string; files: Record<string, string>; params: string[]; symbols: string[]; goto: (file: string, line: number, column?: number) => void; replace: (files: Record<string, string>) => void; snippets?: UserSnippet[];
  paramSpecs?: Record<string, { value: number; min?: number | null; max?: number | null; step?: number | null }>; problems?: Problem[];
  lens?: (command: string, args: Record<string, unknown>) => void; addParam?: (name: string, value: number) => void };
export type EditorAction = { id: string; label: string; keys?: (m: Monaco) => number[]; run: (line: number) => void };
type Sym = { name: string; kind: string; line: number; column: number; end_line: number; end_column: number; children: Sym[] };

/** The open project, read by the Monaco providers (registered once per page load). */
const live: { current: (Project & { owner: object }) | null } = { current: null };

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
      if (!scope) return { suggestions: [...SNIPPETS, ...(live.current?.snippets ?? []).map((u) => [u.prefix, u.name, u.body] as [string, string, string])].map(([l, d, s]) => ({ label: l, kind: K.Snippet, detail: d, insertText: s, insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet, range })) };
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
  const nav = (model: { getValue: () => string }, pos: { lineNumber: number; column: number }, extra: Record<string, unknown> = {}) => {
    const p = live.current;
    return { code: model.getValue(), file: p?.file ?? "main.py", files: p?.files ?? {}, line: pos.lineNumber, column: pos.column, ...extra };
  };
  monaco.languages.registerReferenceProvider("python", {
    provideReferences: async (model, pos) => {
      const hits = await studio<{ file: string; line: number; column: number; name: string }[]>("POST", "/build/references", nav(model, pos)).catch(() => []);
      return hits.map((h) => ({ uri: h.file === live.current?.file ? model.uri : monaco.Uri.parse(`file:///${h.file}`), range: new monaco.Range(h.line, h.column, h.line, h.column + h.name.length) }));
    },
  });
  monaco.languages.registerRenameProvider("python", {
    provideRenameEdits: async (model, pos, newName) => {
      const out = await studio<Record<string, string>>("POST", "/build/rename", nav(model, pos, { new_name: newName })).catch((e: Error) => ({ __error: e.message }));
      if ("__error" in out) return { edits: [], rejectReason: out.__error };
      live.current?.replace(out);
      return { edits: [] };
    },
  });
  monaco.languages.registerDocumentSymbolProvider("python", {
    provideDocumentSymbols: async (model) => {
      const S = monaco.languages.SymbolKind;
      type DocSym = { name: string; detail: string; kind: number; range: InstanceType<Monaco["Range"]>; selectionRange: InstanceType<Monaco["Range"]>; tags: []; children: DocSym[] };
      const map = (x: Sym): DocSym => {
        const range = new monaco.Range(x.line, x.column, x.end_line, x.end_column);
        return { name: x.name, detail: x.kind, kind: ({ class: S.Class, method: S.Method, function: S.Function } as Record<string, number>)[x.kind] ?? S.Variable, range, selectionRange: range, tags: [], children: x.children.map(map) };
      };
      const items = await studio<Sym[]>("POST", "/build/outline", { code: model.getValue() }).catch(() => []);
      return items.map(map);
    },
  });
  const values = () => Object.fromEntries(Object.entries(live.current?.paramSpecs ?? {}).map(([k, v]) => [k, v.value]));
  monaco.languages.registerHoverProvider("python", {
    provideHover: async (model, pos) => {
      const h = await studio<{ contents: string; range: { line: number; column: number; end_line: number; end_column: number } } | null>("POST", "/build/hover", { code: model.getValue(), line: pos.lineNumber, column: pos.column, params: live.current?.paramSpecs ?? {} }).catch(() => null);
      return h ? { contents: [{ value: h.contents }], range: new monaco.Range(h.range.line, h.range.column, h.range.end_line ?? h.range.line, h.range.end_column ?? h.range.column) } : null;
    },
  });
  monaco.languages.registerInlayHintsProvider("python", {
    provideInlayHints: async (model) => {
      const hints = await studio<{ line: number; column: number; label: string; kind: string }[]>("POST", "/build/inlay-hints", { code: model.getValue(), params: values() }).catch(() => []);
      return { hints: hints.map((h) => ({ position: { lineNumber: h.line, column: h.column }, label: h.kind === "name" ? h.label : ` ${h.label}`, kind: h.kind === "name" ? monaco.languages.InlayHintKind.Parameter : monaco.languages.InlayHintKind.Type, paddingLeft: h.kind !== "name" })), dispose: () => undefined };
    },
  });
  const lensCmd = monaco.editor.registerCommand("studio.lens", (_a, command: string, args: Record<string, unknown>) => live.current?.lens?.(command, args));
  const paramCmd = monaco.editor.registerCommand("studio.addParam", (_a, name: string, value: number) => live.current?.addParam?.(name, value));
  void lensCmd; void paramCmd;
  monaco.languages.registerCodeLensProvider("python", {
    provideCodeLenses: async (model) => {
      const lenses = await studio<{ line: number; title: string; command: string; arguments: Record<string, unknown> }[]>("POST", "/build/codelens", { code: model.getValue(), symbol: live.current?.symbols[0] ?? "SPY", params: values() }).catch(() => []);
      return { lenses: lenses.map((l, i) => ({ range: new monaco.Range(l.line, 1, l.line, 1), id: `lens${i}`, command: { id: "studio.lens", title: l.title, arguments: [l.command, l.arguments] } })), dispose: () => undefined };
    },
  });
  const edits = (model: { uri: unknown }, list: TextEdit[]) => list.map((e) => ({ resource: model.uri as never, versionId: undefined, textEdit: { range: new monaco.Range(e.line, e.column, e.end_line, e.end_column), text: e.text } }));
  monaco.languages.registerCodeActionProvider("python", {
    provideCodeActions: async (model, range) => {
      const found = await studio<{ title: string; kind: string; edits: TextEdit[]; parameter?: { name: string; value: number } }[]>("POST", "/build/code-actions", { code: model.getValue(), line: range.startLineNumber, column: range.startColumn,
        ...(range.isEmpty() ? {} : { end_line: range.endLineNumber, end_column: range.endColumn }) }).catch(() => []);
      const fixes = (live.current?.problems ?? []).filter((p) => p.fix && p.line >= range.startLineNumber && p.line <= range.endLineNumber);
      return { actions: [
        ...fixes.map((p) => ({ title: p.fix!.title, kind: "quickfix", isPreferred: true, edit: { edits: edits(model, p.fix!.edits) } })),
        ...found.map((a) => ({ title: a.title, kind: a.kind, edit: { edits: edits(model, a.edits) }, command: a.parameter ? { id: "studio.addParam", title: "Add parameter", arguments: [a.parameter.name, a.parameter.value] } : undefined })),
      ], dispose: () => undefined };
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
/** JetBrains New UI syntax palettes (Dark and IntelliJ Light): readable in both themes, no neon. */
const rules = (pairs: [string, string][]) => pairs.map(([token, foreground]) => ({ token, foreground }));
const SYNTAX = {
  dark: rules([["keyword", "CF8E6D"], ["string", "6AAB73"], ["number", "2AACB8"], ["type", "C77DBB"], ["delimiter", "BCBEC4"], ["identifier", "BCBEC4"]]),
  light: rules([["keyword", "0033B3"], ["string", "067D17"], ["number", "1750EB"], ["type", "871094"], ["delimiter", "080808"], ["identifier", "080808"]]),
};
function theme(monaco: Monaco, dark: boolean) {
  const el = document.querySelector(".ws") ?? document.documentElement;
  const v = (n: string, f: string) => hex(getComputedStyle(el).getPropertyValue(n).trim() || f, f);
  const bg = v("--island", dark ? "#16181d" : "#ffffff"), text = v("--text", dark ? "#e6e6e6" : "#111111"), muted = v("--text-3", "#7a7f87"), line = v("--line", dark ? "#262a31" : "#e6e6e6");
  monaco.editor.defineTheme("studio", { base: dark ? "vs-dark" : "vs", inherit: true, rules: [{ token: "comment", foreground: muted.slice(1, 7), fontStyle: "italic" }, ...SYNTAX[dark ? "dark" : "light"]],
    colors: { "editor.background": bg, "editor.foreground": text, "editorLineNumber.foreground": muted, "editorLineNumber.activeForeground": text, "editor.lineHighlightBackground": line, "editor.lineHighlightBorder": "#00000000", "editorGutter.background": bg, "editorWidget.background": bg, "editorWidget.border": line, "editorIndentGuide.background1": line } });
  monaco.editor.setTheme("studio");
}

/** Build › Dev: Monaco for one project file, with server completion, signature help, go to definition and line markers. */
export function CodeEditor({ path, value, onChange, problems, project, onSave, onRun, onCursor, reveal, actions = [], breakpoints = [], bookmarks = [], logpoints = [], ran = [], onGutter, onComment, commentLines = [], readOnly, font = 13, snippets, onSelection, insertRef }: {
  path: string; value: string; onChange: (v: string) => void; problems: Problem[]; project: Project;
  onSave: () => void; onRun: () => void; onCursor?: (line: number, column: number) => void; reveal?: { line: number; column?: number; n: number } | null;
  actions?: EditorAction[]; breakpoints?: number[]; bookmarks?: number[]; logpoints?: { line: number; message: string }[]; ran?: { line: number; count: number; dates: string[] }[]; onGutter?: (line: number) => void; onComment?: (line: number) => void; commentLines?: number[];
  readOnly?: boolean; font?: number; snippets?: UserSnippet[]; onSelection?: (text: string) => void; insertRef?: { current: ((text: string) => void) | null };
}) {
  const deco = useRef<{ clear: () => void; set: (d: NonNullable<Parameters<Ed["createDecorationsCollection"]>[0]>) => void } | null>(null);
  const acts = useRef(actions); acts.current = actions;
  const ed = useRef<{ editor: Ed; monaco: Monaco } | null>(null);
  const keys = useRef({ onSave, onRun, onCursor, onGutter, onComment }); keys.current = { onSave, onRun, onCursor, onGutter, onComment };
  const context = useRef({ ...project, snippets });
  useEffect(() => {
    context.current = { ...project, snippets };
    if (ed.current?.editor.hasTextFocus() || live.current?.owner === context) {
      live.current = { ...context.current, owner: context };
    }
  }, [project, snippets]);
  const sel = useRef(onSelection); sel.current = onSelection;

  useEffect(() => {
    const m = ed.current; if (!m) return;
    const model = m.editor.getModel(); if (!model) return;
    m.monaco.editor.setModelMarkers(model, "studio", problems.map((f) => ({ severity: f.severity === "error" ? m.monaco.MarkerSeverity.Error : f.severity === "warning" ? m.monaco.MarkerSeverity.Warning : m.monaco.MarkerSeverity.Info,
      message: f.message, code: f.code, startLineNumber: Math.max(1, f.line), endLineNumber: Math.max(1, f.line), startColumn: Math.max(1, f.column), endColumn: Math.max(f.end_column, f.column + 1) })));
  }, [problems, path]);

  useEffect(() => {
    const m = ed.current; if (!m) return;
    deco.current?.set([
      ...breakpoints.map((line) => ({ range: new m.monaco.Range(line, 1, line, 1), options: { glyphMarginClassName: "dv-bp", glyphMarginHoverMessage: { value: "Breakpoint" } } })),
      ...logpoints.map((p) => ({ range: new m.monaco.Range(p.line, 1, p.line, 1), options: { glyphMarginClassName: "dv-lp", glyphMarginHoverMessage: { value: `Logpoint: ${p.message}` } } })),
      ...commentLines.map((line) => ({ range: new m.monaco.Range(line, 1, line, 1), options: { linesDecorationsClassName: "dv-cmt", hoverMessage: { value: "Comment thread" } } })),
      ...bookmarks.map((line) => ({ range: new m.monaco.Range(line, 1, line, 1), options: { linesDecorationsClassName: "dv-bm", hoverMessage: { value: "Bookmark" } } })),
      ...ran.map((r) => ({ range: new m.monaco.Range(r.line, 1, r.line, 1), options: { linesDecorationsClassName: "dv-ran", hoverMessage: { value: `Placed ${r.count} order${r.count === 1 ? "" : "s"}: ${r.dates.slice(0, 5).join(", ")}` } } })),
    ]);
  }, [breakpoints, bookmarks, logpoints, ran, commentLines, path, value]);

  useEffect(() => {
    const m = ed.current; if (!m || !reveal) return;
    m.editor.revealLineInCenter(reveal.line); m.editor.setPosition({ lineNumber: reveal.line, column: reveal.column ?? 1 }); m.editor.focus();
  }, [reveal, path]);

  const mount: OnMount = (editor, monaco) => {
    ed.current = { editor, monaco };
    register(monaco);
    live.current ??= { ...context.current, owner: context };
    editor.onDidFocusEditorText(() => { live.current = { ...context.current, owner: context }; });
    editor.onDidDispose(() => { if (live.current?.owner === context) live.current = null; });
    // The workspace marks light mode with .is-light on its root, not on <html>; follow it live.
    const root = editor.getContainerDomNode().closest(".ws") ?? document.documentElement;
    const sync = () => theme(monaco, !root.classList.contains("is-light")); sync();
    const obs = new MutationObserver(sync); obs.observe(root, { attributes: true, attributeFilter: ["class"] });
    editor.onDidDispose(() => obs.disconnect());
    editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => keys.current.onSave());
    editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter, () => keys.current.onRun());
    editor.onDidChangeCursorPosition((e) => keys.current.onCursor?.(e.position.lineNumber, e.position.column));
    editor.onDidChangeCursorSelection((e) => sel.current?.(editor.getModel()?.getValueInRange(e.selection) ?? ""));
    if (insertRef) insertRef.current = (text) => { (editor.getContribution("snippetController2") as unknown as { insert: (t: string) => void } | null)?.insert(text); editor.focus(); };
    const c = editor.createDecorationsCollection();
    deco.current = { clear: () => c.clear(), set: (d) => c.set(d) };
    editor.addAction({ id: "studio.comment", label: "Comment on line", contextMenuGroupId: "navigation", run: (x) => keys.current.onComment?.(x.getPosition()?.lineNumber ?? 1) });
    editor.onMouseDown((e) => { if (e.target.type === monaco.editor.MouseTargetType.GUTTER_LINE_DECORATIONS && e.target.position && e.target.element?.classList.contains("dv-cmt")) keys.current.onComment?.(e.target.position.lineNumber); if (e.target.type === monaco.editor.MouseTargetType.GUTTER_GLYPH_MARGIN && e.target.position) keys.current.onGutter?.(e.target.position.lineNumber); });
    const rewrite = (path: string, extra: Record<string, unknown> = {}) => void studio<{ code: string }>("POST", path, { code: editor.getValue(), ...extra }).then((r) => {
      const model = editor.getModel(); if (!model || r.code === model.getValue()) return;
      editor.executeEdits("studio", [{ range: model.getFullModelRange(), text: r.code }]);
    }, () => undefined);
    editor.addAction({ id: "studio.formatSelection", label: "Format selection", keybindings: [monaco.KeyMod.chord(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyK, monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyF)],
      run: (x) => { const r = x.getSelection(); if (r) rewrite("/build/format-range", { start_line: r.startLineNumber, end_line: r.endLineNumber }); } });
    editor.addAction({ id: "studio.organiseImports", label: "Organise imports", keybindings: [monaco.KeyMod.Shift | monaco.KeyMod.Alt | monaco.KeyCode.KeyO], run: () => rewrite("/build/organise-imports") });
    editor.addAction({ id: "studio.migrate", label: "Migrate to the current Studio API", run: () => rewrite("/build/migrate") });
    const custom = userKeys();
    const starts = chordStarts(custom); let pending = 0;
    const node = editor.getContainerDomNode(); const hint = document.createElement("div"); hint.className = "km-hint"; hint.hidden = true; node.appendChild(hint);
    editor.onKeyDown((e) => { if (["shift", "control", "alt", "meta"].includes(e.browserEvent.key.toLowerCase())) return; clearTimeout(pending); hint.hidden = true; const cb = comboFromEvent(e.browserEvent);
      if (starts.has(cb)) { hint.textContent = `${cb.replace(/cmd/g, "⌘").replace(/shift/g, "⇧").replace(/alt/g, "⌥").replace(/\+/g, "").toUpperCase()} was pressed, waiting for second key`; hint.hidden = false; pending = window.setTimeout(() => { hint.hidden = true; }, 1500); } });
    editor.onDidDispose(() => { clearTimeout(pending); hint.remove(); });
    for (const a of acts.current) editor.addAction({ id: a.id, label: a.label, keybindings: custom[a.id] ? parseKeys(monaco, custom[a.id]) ?? a.keys?.(monaco) : a.keys?.(monaco), run: (x) => acts.current.find((y) => y.id === a.id)?.run(x.getPosition()?.lineNumber ?? 1) });
  };

  const prefs = editorPrefs();
  return (
    <div className="dv-monaco"><Editor language="python" path={path} value={value} onChange={(v) => onChange(v ?? "")} onMount={mount} theme="studio" height="100%"
      options={{ minimap: { enabled: false }, wordWrap: prefs.wrap === false ? "off" : "on", rulers: prefs.rulers ? [prefs.rulers] : [], overviewRulerLanes: 0, overviewRulerBorder: false, hideCursorInOverviewRuler: true, fontSize: font, lineHeight: Math.round(font * 1.54), fontLigatures: prefs.ligatures === true, lineNumbersMinChars: 3, scrollBeyondLastLine: false, tabSize: 4, renderLineHighlight: "line", automaticLayout: true, fixedOverflowWidgets: true, scrollbar: { alwaysConsumeMouseWheel: false },
        padding: { top: 10 }, fontFamily: "'JetBrains Mono', var(--font-mono), ui-monospace, monospace", quickSuggestions: { strings: true, other: true, comments: false },
        bracketPairColorization: { enabled: true }, stickyScroll: { enabled: true }, folding: true, guides: { indentation: true, bracketPairs: true }, glyphMargin: true, readOnly }} /></div>
  );
}

/** Studio commands whose shortcut can be changed in Customise (B-100). */
export const REBINDABLE: [string, string][] = [["studio.debug", "Debug: start"], ["studio.bp", "Toggle breakpoint"], ["studio.step", "Step one bar"], ["studio.stepline", "Step line"], ["studio.stepback", "Step back one bar"],
  ["studio.panel", "Toggle panel"], ["studio.rail", "Toggle side bar"], ["studio.files", "Go to file"], ["studio.search", "Search project"], ["studio.docs", "Docs"], ["studio.fullrun", "Full run"], ["studio.quickrun", "Quick run"]];

export const userKeys = (): Record<string, string> => { try { return (JSON.parse(localStorage.getItem("studio:build:defaults") ?? "{}") as { keys?: Record<string, string> }).keys ?? {}; } catch { return {}; } };
/** Editor settings from Customise Build: word wrap (on unless off), ruler column (0 none), ligatures (off unless on). */
const editorPrefs = ():{ wrap?: boolean; rulers?: number; ligatures?: boolean } => { try { return JSON.parse(localStorage.getItem("studio:build:defaults") ?? "{}"); } catch { return {}; } };

/** "Cmd+Shift+K", "F6", "Alt+Enter" or a chord "Cmd+K Cmd+S" as a Monaco keybinding; null when it does not parse. */
export function parseKeys(m: Monaco, text: string): number[] | null {
  const one = (t: string): number | null => {
    let mod = 0, key: number | undefined;
    for (const raw of t.split("+").map((x) => x.trim().toLowerCase()).filter(Boolean)) {
      if (["cmd", "ctrl", "meta", "⌘"].includes(raw)) mod |= m.KeyMod.CtrlCmd;
      else if (["shift", "⇧"].includes(raw)) mod |= m.KeyMod.Shift;
      else if (["alt", "option", "opt", "⌥"].includes(raw)) mod |= m.KeyMod.Alt;
      else if (raw === "enter" || raw === "return") key = m.KeyCode.Enter;
      else if (/^f([1-9]|1[0-9])$/.test(raw)) key = (m.KeyCode as unknown as Record<string, number>)[raw.toUpperCase()];
      else if (/^[a-z]$/.test(raw)) key = (m.KeyCode as unknown as Record<string, number>)[`Key${raw.toUpperCase()}`];
      else if (/^[0-9]$/.test(raw)) key = (m.KeyCode as unknown as Record<string, number>)[`Digit${raw}`];
      else return null;
    }
    return key === undefined ? null : mod | key;
  };
  const steps = text.trim().split(/\s+/).map(one);
  if (steps.length > 2 || steps.some((x) => x === null)) return null;
  return [steps.length === 2 ? m.KeyMod.chord(steps[0]!, steps[1]!) : steps[0]!];
}
