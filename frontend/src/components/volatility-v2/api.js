import { API_BASE_URL } from "@/lib/apiBase";

async function request(path, options) {
  const response = await fetch(`${API_BASE_URL}/labs/volatility/v2${path}`, options);
  const body = await response.json();
  if (!response.ok) throw new Error(typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail));
  return body;
}

export function toVolatilityPayload(form, contract) {
  const keys = new Set(contract.inputs.map(input => input.key));
  // Existing shell display controls do not change backend calculations.
  const displayOnly = new Set(["compute_mode", "active_estimators", "cross_asset_panel", "network_layout", "cross_asset_mode"]);
  const payload = {};
  for (const [oldKey, value] of Object.entries(form)) {
    if (value === "" || value == null || displayOnly.has(oldKey)) continue;
    const key = contract.aliases?.[oldKey] || oldKey;
    if (!keys.has(key)) throw new Error(`Unsupported control ${oldKey}. This feature's supported controls are declared by the backend.`);
    if (key in payload && String(payload[key]) !== String(value)) throw new Error(`Conflicting values for ${key}`);
    payload[key] = value;
  }
  return payload;
}

export async function runVolatilityV2Feature(featureId, form) {
  const id = String(featureId).replace("feature_", "").replace("feature-", "").padStart(2, "0");
  const manifest = await request("/features");
  const contract = manifest.features.find(feature => feature.id === id);
  if (!contract) throw new Error(`Unknown Volatility V2 feature ${id}`);
  const payload = toVolatilityPayload(form, contract);
  const job = await request(`/feature/${id}/jobs`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ payload }),
  });
  while (true) {
    const state = await request(`/jobs/${job.job_id}`);
    if (state.status === "completed") return state.result;
    if (["failed", "cancelled", "interrupted"].includes(state.status)) throw new Error(state.error || `Job ${state.status}`);
    await new Promise(resolve => setTimeout(resolve, 500));
  }
}
