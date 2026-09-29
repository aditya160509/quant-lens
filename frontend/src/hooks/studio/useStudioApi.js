"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

const DEFAULT_TIMEOUT = 45_000;
const DEFAULT_RETRIES = 1;
const cache = new Map();

function sleep(ms) { return new Promise((resolve) => setTimeout(resolve, ms)); }

function isRetryableStatus(status) { return status === 408 || status === 425 || status === 429 || status >= 500; }

export function createStudioError(cause, fallback = "Studio request failed") {
  if (cause?.message && cause?.status !== undefined) return cause;
  if (cause?.name === "AbortError") return { message: "Request cancelled", code: "ABORTED", retryable: false };
  if (cause?.name === "TimeoutError") return { message: "Request timed out", code: "TIMEOUT", retryable: true };
  return { message: String(cause?.message || cause || fallback), code: cause?.code, status: cause?.status, retryable: cause?.retryable ?? false, details: cause?.details };
}

function withQuery(path, query) {
  if (!query || Object.keys(query).length === 0) return path;
  const [base, raw] = path.split("?");
  const params = new URLSearchParams(raw || "");
  Object.entries(query).forEach(([key, value]) => { if (value !== undefined && value !== null) params.set(key, String(value)); });
  const encoded = params.toString();
  return encoded ? `${base}?${encoded}` : base;
}

async function parseResponse(response) {
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) return response.json().catch(() => ({}));
  if (contentType.includes("application/zip") || contentType.includes("application/octet-stream") || contentType.includes("application/pdf")) return response.blob();
  return response.text();
}

export function useStudioApi() {
  const mountedRef = useRef(true);
  const controllersRef = useRef(new Map());
  const sequenceRef = useRef(0);
  const [requests, setRequests] = useState({});

  useEffect(() => {
    mountedRef.current = true;
    const controllers = controllersRef.current;
    return () => {
      mountedRef.current = false;
      controllers.forEach((controller) => controller.abort());
      controllers.clear();
    };
  }, []);

  const setRequestState = useCallback((key, patch) => {
    if (!mountedRef.current) return;
    setRequests((current) => ({ ...current, [key]: { ...(current[key] || {}), ...patch } }));
  }, []);

  const request = useCallback(async (path, options = {}) => {
    const { key = path, timeoutMs = DEFAULT_TIMEOUT, retries = DEFAULT_RETRIES, retryDelayMs = 250, cacheTtlMs = 0, query, signal: externalSignal, ...init } = options;
    const requestKey = String(key);
    const url = withQuery(path, query);
    const sequence = sequenceRef.current + 1;
    sequenceRef.current = sequence;
    if (init.method?.toUpperCase() === "GET" && cacheTtlMs > 0) {
      const entry = cache.get(url);
      if (entry && entry.expiresAt > Date.now()) {
        const completedAt = Date.now();
        setRequestState(requestKey, { status: "success", data: entry.data, error: null, startedAt: completedAt, completedAt, sequence });
        return entry.data;
      }
    }
    controllersRef.current.get(requestKey)?.abort();
    const controller = new AbortController();
    controllersRef.current.set(requestKey, controller);
    const mergedSignal = externalSignal ? AbortSignal.any([externalSignal, controller.signal]) : controller.signal;
    const isFormData = typeof FormData !== "undefined" && init.body instanceof FormData;
    const body = init.body && typeof init.body !== "string" && !isFormData ? JSON.stringify(init.body) : init.body;
    const headers = { Accept: "application/json", ...(body && !isFormData ? { "Content-Type": "application/json" } : {}), ...(init.headers || {}) };
    const startedAt = Date.now();
    const setOwnedRequestState = (patch) => {
      if (controllersRef.current.get(requestKey) !== controller) return;
      setRequestState(requestKey, { ...patch, sequence });
    };
    setOwnedRequestState({ status: "loading", data: null, error: null, startedAt, completedAt: null });
    let lastError = null;
    try {
      for (let attempt = 0; attempt <= Math.max(0, retries); attempt += 1) {
        const timeout = setTimeout(() => controller.abort(new DOMException("Request timed out", "TimeoutError")), timeoutMs);
        try {
          const response = await fetch(url, { ...init, body, headers, signal: mergedSignal });
          const payload = await parseResponse(response);
          if (mergedSignal.aborted || controllersRef.current.get(requestKey) !== controller) {
            throw mergedSignal.reason || new DOMException("Request cancelled", "AbortError");
          }
          if (!response.ok) {
            const serverMessage = typeof payload === "object" ? payload?.detail || payload?.message : payload;
            const error = { message: String(serverMessage || `Request failed (${response.status})`), status: response.status, retryable: isRetryableStatus(response.status), details: payload };
            if (error.retryable && attempt < retries) { lastError = error; await sleep(retryDelayMs * (attempt + 1)); continue; }
            throw error;
          }
          if (init.method?.toUpperCase() === "GET" && cacheTtlMs > 0) cache.set(url, { data: payload, expiresAt: Date.now() + cacheTtlMs });
          setOwnedRequestState({ status: "success", data: payload, error: null, completedAt: Date.now() });
          return payload;
        } catch (cause) {
          const abortReason = mergedSignal.aborted ? mergedSignal.reason : null;
          lastError = createStudioError(abortReason || cause);
          if (lastError.code === "ABORTED" || lastError.code === "TIMEOUT" || !lastError.retryable || attempt >= retries) throw lastError;
          await sleep(retryDelayMs * (attempt + 1));
        } finally { clearTimeout(timeout); }
      }
      throw lastError || createStudioError(null);
    } catch (cause) {
      const error = createStudioError(cause);
      setOwnedRequestState({ status: error.code === "ABORTED" ? "cancelled" : "error", error, completedAt: Date.now() });
      throw error;
    } finally { if (controllersRef.current.get(requestKey) === controller) controllersRef.current.delete(requestKey); }
  }, [setRequestState]);

  const cancel = useCallback((key) => controllersRef.current.get(String(key))?.abort(), []);
  const cancelAll = useCallback(() => controllersRef.current.forEach((controller) => controller.abort()), []);
  const reset = useCallback((key) => setRequests((current) => { const next = { ...current }; delete next[String(key)]; return next; }), []);
  const state = useMemo(() => {
    const values = Object.values(requests);
    const latest = values.reduce((candidate, value) => (value.sequence ?? -1) > (candidate.sequence ?? -1) ? value : candidate, { status: "idle", error: null, sequence: -1 });
    return { status: latest.status || "idle", isLoading: values.some((value) => value.status === "loading"), error: latest.error || null, errors: Object.fromEntries(Object.entries(requests).map(([key, value]) => [key, value.error || null])) };
  }, [requests]);
  const get = useCallback((path, options = {}) => request(path, { ...options, method: "GET" }), [request]);
  const post = useCallback((path, body, options = {}) => request(path, { ...options, method: "POST", body }), [request]);
  const put = useCallback((path, body, options = {}) => request(path, { ...options, method: "PUT", body }), [request]);
  const remove = useCallback((path, options = {}) => request(path, { ...options, method: "DELETE" }), [request]);
  return { request, get, post, put, remove, cancel, cancelAll, reset, requests, ...state };
}
