"use client";

import { Bell } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useToasterStore } from "react-hot-toast";

type Note = { id: string; text: string; at: number };
const KEEP = 50;

/** Status bar bell: the last 50 toast messages, read from react-hot-toast's store while the IDE is open. Clear drops what is shown so far. */
export function NotifyBell() {
  const { toasts } = useToasterStore();
  const [notes, setNotes] = useState<Note[]>([]);
  const cleared = useRef(0);
  useEffect(() => {
    setNotes((prev) => {
      let next = prev;
      for (const t of toasts) {
        const text = typeof t.message === "string" ? t.message : "";
        if (!text || t.createdAt < cleared.current) continue;
        const i = next.findIndex((n) => n.id === t.id);
        if (i < 0) next = [{ id: t.id, text, at: t.createdAt }, ...next].slice(0, KEEP);
        else if (next[i].text !== text) next = next.map((n) => (n.id === t.id ? { ...n, text } : n));
      }
      return next;
    });
  }, [toasts]);

  const clear = () => { cleared.current = Date.now(); setNotes([]); };
  return (
    <details className="dv-view dv-notes" onBlur={(e) => { if (!e.currentTarget.contains(e.relatedTarget)) e.currentTarget.open = false; }}>
      <summary aria-label={`Notifications (${notes.length})`} title="Notifications"><Bell size={13} />{notes.length ? <b>{notes.length}</b> : null}</summary>
      <div className="dv-menu">
        <div className="hd"><span>Notifications</span>{notes.length ? <button className="btn sm ghost" onClick={clear}>Clear</button> : null}</div>
        {notes.length ? notes.map((n) => (
          <div key={n.id} className="dv-note"><span>{n.text}</span><time>{new Date(n.at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</time></div>
        )) : <p className="dv-empty">No notifications</p>}
      </div>
    </details>
  );
}
