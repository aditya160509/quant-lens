import { lab } from "@/modules/research/lab";

/** A request to the Screener API; a failed one throws the server's own message. */
export async function send<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${lab().base}${path}`, { method, headers: body === undefined ? undefined : { "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body) });
  const json = (await res.json().catch(() => ({}))) as { detail?: unknown };
  if (!res.ok) throw new Error(typeof json.detail === "string" ? json.detail : `Request failed (${res.status})`);
  return json as T;
}
