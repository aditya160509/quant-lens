import { API_BASE_URL } from "@/lib/api";

async function readResponse(res) {
  const body = await res.json();
  if (!res.ok) throw new Error(typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail || body));
  return body;
}

export async function runScreenerV2Feature(featureId, payload = {}) {
  const id = String(featureId).replace("feature_", "").replace("feature-", "").padStart(2, "0");
  return readResponse(await fetch(`${API_BASE_URL}/screener-v2/run/${id}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ payload }),
  }));
}

export async function searchScreenerV2Symbols(query = "", options = {}) {
  const params = new URLSearchParams({ q: query, limit: String(options.limit || 25) });
  return readResponse(await fetch(`${API_BASE_URL}/screener-v2/symbols?${params}`));
}
