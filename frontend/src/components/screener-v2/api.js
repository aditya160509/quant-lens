import { API_BASE_URL } from "@/lib/api";

async function readResponse(res) {
  const body = await res.json();
  if (!res.ok) throw new Error(typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail || body));
  return body;
}

export async function runScreenerV2Feature(featureId, payload = {}) {
  const id = String(featureId).replace("feature_", "").replace("feature-", "").padStart(2, "0");
  const job = await readResponse(await fetch(`${API_BASE_URL}/screener-v2/feature/${id}/jobs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ payload }),
  }));
  for (let attempt = 0; attempt < 1800; attempt += 1) {
    const status = await readResponse(await fetch(`${API_BASE_URL}/screener-v2/jobs/${job.job_id}`));
    if (status.status === "completed") {
      if (!status.result) throw new Error("Completed job has no result");
      return status.result;
    }
    if (["failed", "cancelled"].includes(status.status)) throw new Error(status.error || `Run ${status.status}`);
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  throw new Error(`Run is still active. Job id: ${job.job_id}`);
}

export async function searchScreenerV2Symbols(query = "", options = {}) {
  const params = new URLSearchParams({ q: query, limit: String(options.limit || 25) });
  return readResponse(await fetch(`${API_BASE_URL}/screener-v2/symbols?${params}`));
}

export async function getScreenerV2Manifest() {
  return readResponse(await fetch(`${API_BASE_URL}/screener-v2/features`));
}
