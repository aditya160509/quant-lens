import { useEffect, useRef } from "react";
import { studio } from "../api";

/** Keeps a Build preference on the server (GET/PUT /build/prefs/{name}) so it follows the user across browsers; local storage stays the fast first paint.
 *  A local edit made before the server copy arrives wins (and is pushed); a server value of a different shape is ignored; the applied server value is not echoed back. */
export function useServerPref<T>(name: "layouts" | "runconfigs" | "inspections" | "settings" | "profiles" | "artefacts", value: T, apply: (v: T) => void) {
  const loaded = useRef(false), first = useRef(value), latest = useRef(value), fromServer = useRef<T | undefined>(undefined);
  latest.current = value;
  const put = (v: T) => studio("PUT", `/build/prefs/${name}`, v).catch(() => undefined);
  useEffect(() => {
    const ac = new AbortController();
    void studio<{ value: T | null }>("GET", `/build/prefs/${name}`, undefined, ac.signal).then((r) => {
      const v = r.value, f = first.current;
      if (ac.signal.aborted || v == null || typeof v !== typeof f || Array.isArray(v) !== Array.isArray(f)) return;
      if (latest.current === f) { fromServer.current = v; apply(v); }
    }, () => undefined).finally(() => {
      if (ac.signal.aborted) return;
      loaded.current = true;
      if (latest.current !== first.current && latest.current !== fromServer.current) void put(latest.current);
    });
    return () => ac.abort();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!loaded.current || value === fromServer.current) return;
    const t = setTimeout(() => void put(value), 800);
    return () => clearTimeout(t);
  }, [name, value]); // eslint-disable-line react-hooks/exhaustive-deps
}
