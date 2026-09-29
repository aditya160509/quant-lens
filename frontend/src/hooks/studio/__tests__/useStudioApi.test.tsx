import { act, renderHook, waitFor } from "@testing-library/react";
import { createStudioError, useStudioApi } from "../useStudioApi";

type Deferred<T> = {
  promise: Promise<T>;
  reject: (reason?: unknown) => void;
  resolve: (value: T) => void;
};

function deferred<T>(): Deferred<T> {
  let reject!: (reason?: unknown) => void;
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, reject, resolve };
}

function mockResponse(
  payload: unknown,
  { contentType = "application/json", status = 200 }: { contentType?: string; status?: number } = {},
): Response {
  return {
    blob: jest.fn().mockResolvedValue(payload),
    headers: { get: jest.fn().mockReturnValue(contentType) },
    json: jest.fn().mockResolvedValue(payload),
    ok: status >= 200 && status < 300,
    status,
    text: jest.fn().mockResolvedValue(typeof payload === "string" ? payload : JSON.stringify(payload)),
  } as unknown as Response;
}

function rejectWhenAborted<T>(request: Deferred<T>, signal?: AbortSignal | null) {
  if (!signal) return;
  if (signal.aborted) {
    request.reject(signal.reason);
    return;
  }
  signal.addEventListener("abort", () => request.reject(signal.reason), { once: true });
}

describe("useStudioApi", () => {
  const fetchMock = jest.fn<ReturnType<typeof fetch>, Parameters<typeof fetch>>();

  beforeEach(() => {
    fetchMock.mockReset();
    Object.defineProperty(globalThis, "fetch", { configurable: true, value: fetchMock, writable: true });
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it("serializes JSON requests and exposes the loading-to-success lifecycle", async () => {
    const response = deferred<Response>();
    fetchMock.mockReturnValue(response.promise);
    const { result } = renderHook(() => useStudioApi());
    let request!: Promise<{ run_id: string }>;

    act(() => {
      request = result.current.post(
        "/api/v2/backtest/run",
        { universe_id: ["SPY"] },
        { key: "backtest.run", retries: 0 },
      );
    });

    expect(result.current.requests["backtest.run"]).toMatchObject({
      data: null,
      error: null,
      status: "loading",
    });
    expect(result.current.isLoading).toBe(true);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v2/backtest/run",
      expect.objectContaining({
        body: JSON.stringify({ universe_id: ["SPY"] }),
        headers: expect.objectContaining({ Accept: "application/json", "Content-Type": "application/json" }),
        method: "POST",
        signal: expect.any(AbortSignal),
      }),
    );

    await act(async () => {
      response.resolve(mockResponse({ run_id: "run-1" }));
      await expect(request).resolves.toEqual({ run_id: "run-1" });
    });

    expect(result.current.requests["backtest.run"]).toMatchObject({
      data: { run_id: "run-1" },
      error: null,
      status: "success",
    });
    expect(result.current.isLoading).toBe(false);
  });

  it("passes multipart bodies through without overriding the browser boundary", async () => {
    fetchMock.mockResolvedValue(mockResponse({ success: true }));
    const { result } = renderHook(() => useStudioApi());
    const form = new FormData();
    form.append("source_name", "sample");

    await act(async () => {
      await expect(result.current.request("/api/v2/data-studio/upload", { method: "POST", body: form, retries: 0 })).resolves.toEqual({ success: true });
    });

    expect(fetchMock).toHaveBeenCalledWith("/api/v2/data-studio/upload", expect.objectContaining({
      body: form,
      headers: { Accept: "application/json" },
    }));
  });

  it("encodes query values, preserves existing parameters, and reuses a live GET cache entry", async () => {
    fetchMock.mockResolvedValue(mockResponse({ tickers: ["SPY"] }));
    const { result } = renderHook(() => useStudioApi());
    const path = "/api/v2/data-studio/catalog?scope=market";
    const options = {
      cacheTtlMs: 5_000,
      key: "catalog",
      query: { active_only: false, ignored: undefined, search: "US large cap" },
    };

    await act(async () => {
      await expect(result.current.get(path, options)).resolves.toEqual({ tickers: ["SPY"] });
      await expect(result.current.get(path, options)).resolves.toEqual({ tickers: ["SPY"] });
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v2/data-studio/catalog?scope=market&active_only=false&search=US+large+cap",
      expect.objectContaining({ method: "GET" }),
    );
    expect(result.current.requests["catalog"]).toMatchObject({ status: "success", data: { tickers: ["SPY"] } });
  });

  it("normalizes structured HTTP failures and records the keyed error", async () => {
    fetchMock.mockResolvedValue(mockResponse({ detail: "Universe must contain at least two assets" }, { status: 422 }));
    const { result } = renderHook(() => useStudioApi());
    let error: unknown;

    await act(async () => {
      try {
        await result.current.post("/api/v2/optimizer/cpcv", { tickers: ["SPY"] }, { key: "optimizer.run", retries: 0 });
      } catch (cause) {
        error = cause;
      }
    });

    expect(error).toMatchObject({
      details: { detail: "Universe must contain at least two assets" },
      message: "Universe must contain at least two assets",
      retryable: false,
      status: 422,
    });
    expect(result.current.requests["optimizer.run"]).toMatchObject({ status: "error", error });
    expect(result.current.error).toBe(error);
  });

  it("retries a transient server failure and commits only the successful response", async () => {
    fetchMock
      .mockResolvedValueOnce(mockResponse({ detail: "Temporarily unavailable" }, { status: 503 }))
      .mockResolvedValueOnce(mockResponse({ score: 0.81 }));
    const { result } = renderHook(() => useStudioApi());

    await act(async () => {
      await expect(result.current.get("/api/v2/robustness/composite-score", {
        key: "robustness.composite",
        retries: 1,
        retryDelayMs: 0,
      })).resolves.toEqual({ score: 0.81 });
    });

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(result.current.requests["robustness.composite"]).toMatchObject({
      data: { score: 0.81 },
      error: null,
      status: "success",
    });
  });

  it("cancels a keyed request without affecting a concurrent request", async () => {
    const first = deferred<Response>();
    const second = deferred<Response>();
    fetchMock
      .mockImplementationOnce((_url, init) => {
        rejectWhenAborted(first, init?.signal);
        return first.promise;
      })
      .mockImplementationOnce((_url, init) => {
        rejectWhenAborted(second, init?.signal);
        return second.promise;
      });
    const { result } = renderHook(() => useStudioApi());
    let firstResult!: Promise<unknown>;
    let secondResult!: Promise<unknown>;

    act(() => {
      firstResult = result.current.get("/api/v2/factors/library", { key: "factors.library", retries: 0 }).catch((error) => error);
      secondResult = result.current.get("/api/v2/data-studio/catalog", { key: "data.catalog", retries: 0 });
    });
    act(() => result.current.cancel("factors.library"));

    await act(async () => {
      expect(await firstResult).toMatchObject({ code: "ABORTED", message: "Request cancelled" });
    });
    expect(result.current.requests["factors.library"]).toMatchObject({ status: "cancelled" });
    expect(result.current.requests["data.catalog"]).toMatchObject({ status: "loading" });
    expect(result.current.isLoading).toBe(true);

    await act(async () => {
      second.resolve(mockResponse({ datasets: [] }));
      await expect(secondResult).resolves.toEqual({ datasets: [] });
    });
    expect(result.current.isLoading).toBe(false);
  });

  it("classifies deadline aborts as timeout failures", async () => {
    jest.useFakeTimers();
    const pending = deferred<Response>();
    fetchMock.mockImplementation((_url, init) => {
      rejectWhenAborted(pending, init?.signal);
      return pending.promise;
    });
    const { result } = renderHook(() => useStudioApi());
    let request!: Promise<unknown>;
    let settled!: Promise<unknown>;

    act(() => {
      request = result.current.get("/api/v2/slow", { key: "slow", retries: 0, timeoutMs: 25 });
      settled = request.catch((error) => error);
    });
    await act(async () => {
      jest.advanceTimersByTime(25);
      expect(await settled).toMatchObject({ code: "TIMEOUT", message: "Request timed out", retryable: true });
    });

    expect(result.current.requests["slow"]).toMatchObject({
      error: expect.objectContaining({ code: "TIMEOUT" }),
      status: "error",
    });
  });

  it("keeps the replacement request authoritative during same-key double submission", async () => {
    const stale = deferred<Response>();
    const current = deferred<Response>();
    fetchMock
      .mockImplementationOnce((_url, init) => {
        rejectWhenAborted(stale, init?.signal);
        return stale.promise;
      })
      .mockImplementationOnce((_url, init) => {
        rejectWhenAborted(current, init?.signal);
        return current.promise;
      });
    const { result } = renderHook(() => useStudioApi());
    let staleResult!: Promise<unknown>;
    let currentResult!: Promise<unknown>;

    act(() => {
      staleResult = result.current.post("/api/v2/backtest/run", { version: 1 }, { key: "backtest.run", retries: 0 }).catch((error) => error);
    });
    act(() => {
      currentResult = result.current.post("/api/v2/backtest/run", { version: 2 }, { key: "backtest.run", retries: 0 });
    });

    await act(async () => {
      expect(await staleResult).toMatchObject({ code: "ABORTED" });
    });
    expect(result.current.requests["backtest.run"]).toMatchObject({ status: "loading", data: null, error: null });
    expect(result.current.isLoading).toBe(true);

    await act(async () => {
      current.resolve(mockResponse({ run_id: "run-current" }));
      await expect(currentResult).resolves.toEqual({ run_id: "run-current" });
    });
    expect(result.current.requests["backtest.run"]).toMatchObject({
      data: { run_id: "run-current" },
      error: null,
      status: "success",
    });
  });

  it("aborts in-flight work on unmount without committing post-unmount state", async () => {
    const pending = deferred<Response>();
    let requestSignal: AbortSignal | null | undefined;
    fetchMock.mockImplementation((_url, init) => {
      requestSignal = init?.signal;
      rejectWhenAborted(pending, requestSignal);
      return pending.promise;
    });
    const { result, unmount } = renderHook(() => useStudioApi());
    let request!: Promise<unknown>;

    act(() => {
      request = result.current.get("/api/v2/factors/library", { key: "factors.library", retries: 0 }).catch((error) => error);
    });

    unmount();

    expect(requestSignal?.aborted).toBe(true);
    await expect(request).resolves.toMatchObject({ code: "ABORTED" });
  });

  it("supports PUT and DELETE contracts and resets keyed request state", async () => {
    fetchMock
      .mockResolvedValueOnce(mockResponse({ name: "Quality v2" }))
      .mockResolvedValueOnce(mockResponse({ deleted: true }))
      .mockResolvedValueOnce(mockResponse({ patched: true }));
    const { result } = renderHook(() => useStudioApi());

    await act(async () => {
      await expect(result.current.put("/api/v2/factors/library/quality", { name: "Quality v2" }, { key: "factor.update", retries: 0 }))
        .resolves.toEqual({ name: "Quality v2" });
      await expect(result.current.remove("/api/v2/factors/library/quality", { key: "factor.delete", retries: 0 }))
        .resolves.toEqual({ deleted: true });
      await expect(result.current.request("/api/v2/factors/library/quality", {
        body: { active: true }, key: "factor.patch", method: "PATCH", retries: 0,
      })).resolves.toEqual({ patched: true });
    });

    expect(fetchMock).toHaveBeenNthCalledWith(1, "/api/v2/factors/library/quality", expect.objectContaining({
      body: JSON.stringify({ name: "Quality v2" }), method: "PUT",
    }));
    expect(fetchMock).toHaveBeenNthCalledWith(2, "/api/v2/factors/library/quality", expect.objectContaining({ method: "DELETE" }));
    expect(fetchMock).toHaveBeenNthCalledWith(3, "/api/v2/factors/library/quality", expect.objectContaining({
      body: JSON.stringify({ active: true }), method: "PATCH",
    }));
    expect(result.current.requests["factor.update"]).toMatchObject({ status: "success" });
    expect(result.current.requests["factor.delete"]).toMatchObject({ status: "success" });
    expect(result.current.requests["factor.patch"]).toMatchObject({ status: "success" });

    act(() => result.current.reset("factor.update"));
    expect(result.current.requests["factor.update"]).toBeUndefined();
    expect(result.current.requests["factor.delete"]).toMatchObject({ status: "success" });
  });

  it("cancels all concurrent requests", async () => {
    const first = deferred<Response>();
    const second = deferred<Response>();
    fetchMock
      .mockImplementationOnce((_url, init) => {
        rejectWhenAborted(first, init?.signal);
        return first.promise;
      })
      .mockImplementationOnce((_url, init) => {
        rejectWhenAborted(second, init?.signal);
        return second.promise;
      });
    const { result } = renderHook(() => useStudioApi());
    let firstResult!: Promise<unknown>;
    let secondResult!: Promise<unknown>;

    act(() => {
      firstResult = result.current.get("/api/v2/one", { key: "one", retries: 0 }).catch((error) => error);
      secondResult = result.current.get("/api/v2/two", { key: "two", retries: 0 }).catch((error) => error);
    });
    act(() => result.current.cancelAll());

    await act(async () => {
      await expect(firstResult).resolves.toMatchObject({ code: "ABORTED" });
      await expect(secondResult).resolves.toMatchObject({ code: "ABORTED" });
    });
    expect(result.current.requests["one"]).toMatchObject({ status: "cancelled" });
    expect(result.current.requests["two"]).toMatchObject({ status: "cancelled" });
    expect(result.current.isLoading).toBe(false);
  });

  it.each([
    [new DOMException("cancelled", "AbortError"), { code: "ABORTED", retryable: false }],
    [new DOMException("late", "TimeoutError"), { code: "TIMEOUT", retryable: true }],
    [{ message: "Forbidden", status: 403 }, { message: "Forbidden", status: 403 }],
    [new Error("network down"), { message: "network down", retryable: false }],
  ])("normalizes request failures without discarding structured details", (cause, expected) => {
    expect(createStudioError(cause)).toMatchObject(expected);
  });
});
