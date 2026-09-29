"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";

const emptyByChart = {};

export const useFactorsV2AnnotationStore = create(
  persist(
    (set, get) => ({
      annotationsByChart: emptyByChart,
      addAnnotation: (annotation) => set((state) => ({
        annotationsByChart: {
          ...state.annotationsByChart,
          [annotation.chart_id]: [
            ...(state.annotationsByChart[annotation.chart_id] || []),
            annotation,
          ],
        },
      })),
      replaceAnnotations: (annotations) => {
        const grouped = {};
        for (const annotation of annotations || []) {
          if (!annotation?.chart_id) continue;
          grouped[annotation.chart_id] = [...(grouped[annotation.chart_id] || []), annotation];
        }
        set({ annotationsByChart: grouped });
      },
      resolveAnnotation: (annotationId, chartId) => set((state) => ({
        annotationsByChart: {
          ...state.annotationsByChart,
          [chartId]: (state.annotationsByChart[chartId] || []).map((annotation) => (
            annotation.id === annotationId
              ? { ...annotation, resolved: !annotation.resolved }
              : annotation
          )),
        },
      })),
      replyAnnotation: (annotationId, chartId, text) => set((state) => ({
        annotationsByChart: {
          ...state.annotationsByChart,
          [chartId]: (state.annotationsByChart[chartId] || []).map((annotation) => (
            annotation.id === annotationId
              ? {
                ...annotation,
                thread: [
                  ...(annotation.thread || []),
                  {
                    id: `reply-${Date.now()}`,
                    text,
                    author: "Quant360",
                    created_at: new Date().toISOString(),
                  },
                ],
              }
              : annotation
          )),
        },
      })),
      allAnnotations: () => Object.values(get().annotationsByChart || {}).flat(),
    }),
    {
      name: "quant360:factors-v2:annotations",
      version: 1,
    },
  ),
);

