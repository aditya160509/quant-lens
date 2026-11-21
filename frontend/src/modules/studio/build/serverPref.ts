import { useEffect, useRef } from "react";
import { studio } from "../api";

/** Keeps a Build preference on the server (GET/PUT /build/prefs/{name}) so it follows the user across browsers; local storage stays the fast first paint. */
export function useServerPref<T>(name: "layouts" | "runconfigs", value: T, apply: (v: T) => void) {
  const loaded = useRef(false);
  useEffect(() => {
    void studio<{ value: T | null }>("GET", `/build/prefs/${name}`).then((r) => { if (r.value) apply(r.value); }, () => undefined).finally(() => { loaded.current = true; });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!loaded.current) return;
    const t = setTimeout(() => void studio("PUT", `/build/prefs/${name}`, value).catch(() => undefined), 800);
    return () => clearTimeout(t);
  }, [name, value]);
}
