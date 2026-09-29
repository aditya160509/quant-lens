"use client";

import { useCallback } from "react";
import { useDataStudioStore } from "@/stores/studio/dataStudioStore";
import { useStudioApi } from "./useStudioApi";

export function useDataStudio() {
  const store = useDataStudioStore();
  const api = useStudioApi();
  const {
    request,
    seriesByTicker,
    setCatalog,
    setError,
    setLoadingSeries,
    setSeries,
    setTicker,
    setUniverse,
    ticker,
  } = store;
  const { get, post } = api;

  const loadSeries = useCallback(async (requestedTicker = ticker, options = {}) => {
    const normalized = String(requestedTicker || "SPY").trim().toUpperCase();
    const cached = seriesByTicker?.[normalized];
    if (cached && !options.force) {
      setSeries(cached, normalized);
      return cached;
    }
    setTicker(normalized);
    setLoadingSeries(true);
    try {
      const result = await get(`/api/v2/data-studio/explorer/series/${encodeURIComponent(normalized)}`, {
        key: `data.series.${normalized}`,
        query: { operation: "explorer_series", ticker: normalized, limit: 200, ...(options.query || {}) },
        cacheTtlMs: options.cacheTtlMs ?? 30_000,
        timeoutMs: 60_000,
      });
      setSeries(result, normalized);
      return result;
    } catch (cause) {
      setError(cause);
      throw cause;
    } finally {
      setLoadingSeries(false);
    }
  }, [get, seriesByTicker, setError, setLoadingSeries, setSeries, setTicker, ticker]);

  const buildUniverse = useCallback(async (payload = request) => {
    try {
      const result = await post("/api/v2/data-studio/universe/build", { ...payload, operation: "universe" }, { key: "data.universe", timeoutMs: 120_000, retries: 0 });
      setUniverse(result);
      return result;
    } catch (cause) {
      setError(cause);
      throw cause;
    }
  }, [post, request, setError, setUniverse]);

  const loadCatalog = useCallback(async () => {
    try {
      const result = await get("/api/v2/data-studio/catalog", { key: "data.catalog", cacheTtlMs: 60_000 });
      setCatalog(result);
      return result;
    } catch (cause) {
      setError(cause);
      throw cause;
    }
  }, [get, setCatalog, setError]);
  const loadFreshness = useCallback(() => get("/api/v2/data-studio/freshness", { key: "data.freshness", cacheTtlMs: 30_000 }), [get]);
  const loadManifests = useCallback(() => get("/api/v2/data-studio/manifests", { key: "data.manifests", cacheTtlMs: 60_000 }), [get]);
  const loadUploads = useCallback(() => get("/api/v2/data-studio/uploads", { key: "data.uploads", cacheTtlMs: 0 }), [get]);
  const deleteUpload = useCallback((uploadId) => api.request(`/api/v2/data-studio/uploads/${encodeURIComponent(uploadId)}`, { method: "DELETE", key: `data.upload.delete.${uploadId}`, retries: 0 }), [api]);
  const uploadDataset = useCallback((file, metadata) => {
    const form = new FormData();
    form.append("file", file);
    form.append("source_name", metadata.sourceName);
    form.append("date_column", metadata.dateColumn);
    form.append("symbol_column", metadata.symbolColumn);
    form.append("license_status", metadata.licenseStatus);
    form.append("permitted_use_attested", String(Boolean(metadata.permittedUseAttested)));
    form.append("retention_days", String(metadata.retentionDays));
    return api.request("/api/v2/data-studio/upload", { method: "POST", body: form, key: "data.upload", retries: 0, timeoutMs: 120_000 });
  }, [api]);
  const loadAnomalies = useCallback((query = {}) => get("/api/v2/data-studio/explorer/anomalies", { key: "data.anomalies", query: { operation: "anomalies", ...query }, cacheTtlMs: 30_000 }), [get]);
  const loadHeatmap = useCallback((query = {}) => get("/api/v2/data-studio/explorer/heatmap", { key: "data.heatmap", query: { operation: "missing_heatmap", ...query }, cacheTtlMs: 30_000 }), [get]);
  return { ...api, ...store, requestError: api.error, loadSeries, buildUniverse, loadCatalog, loadFreshness, loadManifests, loadUploads, deleteUpload, uploadDataset, loadAnomalies, loadHeatmap };
}
