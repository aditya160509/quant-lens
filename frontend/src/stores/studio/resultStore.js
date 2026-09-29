"use client";

import { create } from "zustand";

export const emptyStudioResult = () => ({
    candles: [],
    signals: [],
    metrics: {},
    trades: [],
    equityCurve: [],
    series: null,
    runId: null,
    mcData: null,
    wfData: null,
    metadata: null,
    volumeProfile: [],
});

const initialResultState = () => ({
    data: emptyStudioResult(),
    dataA: emptyStudioResult(),
    dataB: emptyStudioResult(),
    gridData: [],
    gridDataA: [],
    gridDataB: [],
    gridVsView: "A",
    benchmarkData: [],
    previousEquityCurve: [],
    previousSignals: [],
    isExecuting: false,
    executionError: null,
    isPlaying: false,
    playIndex: 0,
    analysisComplete: false,
    dataLoading: false,
    dataError: null,
    gridLoading: false,
    gridError: null,
    mcLoading: false,
    mcError: null,
    mcJob: null,
    wfLoading: false,
    wfError: null,
    wfJob: null,
    portfolioArtifact: null,
    portfolioInputs: null,
    portfolioVersion: null,
    promotionAuditRecords: [],
});

const resolveUpdate = (nextValue, currentValue) => (
    typeof nextValue === "function" ? nextValue(currentValue) : nextValue
);

const setter = (set, field) => (nextValue) => set((state) => ({
    [field]: resolveUpdate(nextValue, state[field]),
}));

export const useStudioResultStore = create((set) => ({
    ...initialResultState(),
    setData: setter(set, "data"),
    setDataA: setter(set, "dataA"),
    setDataB: setter(set, "dataB"),
    setGridData: setter(set, "gridData"),
    setGridDataA: setter(set, "gridDataA"),
    setGridDataB: setter(set, "gridDataB"),
    setGridVsView: setter(set, "gridVsView"),
    setBenchmarkData: setter(set, "benchmarkData"),
    setPreviousEquityCurve: setter(set, "previousEquityCurve"),
    setPreviousSignals: setter(set, "previousSignals"),
    setIsExecuting: setter(set, "isExecuting"),
    setExecutionError: setter(set, "executionError"),
    setIsPlaying: setter(set, "isPlaying"),
    setPlayIndex: setter(set, "playIndex"),
    setAnalysisComplete: setter(set, "analysisComplete"),
    setDataLoading: setter(set, "dataLoading"),
    setDataError: setter(set, "dataError"),
    setGridLoading: setter(set, "gridLoading"),
    setGridError: setter(set, "gridError"),
    setMcLoading: setter(set, "mcLoading"),
    setMcError: setter(set, "mcError"),
    setMcJob: setter(set, "mcJob"),
    setWfLoading: setter(set, "wfLoading"),
    setWfError: setter(set, "wfError"),
    setWfJob: setter(set, "wfJob"),
    setPortfolioArtifact: setter(set, "portfolioArtifact"),
    setPortfolioInputs: setter(set, "portfolioInputs"),
    setPortfolioVersion: setter(set, "portfolioVersion"),
    setPromotionAuditRecords: setter(set, "promotionAuditRecords"),
    resetResults: () => set(initialResultState()),
}));
