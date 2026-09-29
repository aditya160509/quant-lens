"use client";

import React, { useEffect, useRef, useMemo } from 'react';

export function PlotlyChart({ data, layout, config, className, style }) {
    const chartRef = useRef(null);

    // Memoize inputs to prevent unnecessary re-renders
    // We use a simple JSON stringify for deep comparison of the props
    // This is safe because Plotly data/layout are typically JSON-serializable objects
    const dataString = useMemo(() => JSON.stringify(data), [data]);
    const layoutString = useMemo(() => JSON.stringify(layout), [layout]);
    const configString = useMemo(() => JSON.stringify(config), [config]);

    useEffect(() => {
        let isMounted = true;
        let Plotly = null;
        // Capture ref value at effect start for cleanup
        const chartElement = chartRef.current;

        const initPlot = async () => {
            try {
                if (!chartElement) return;

                // Dynamic import to avoid SSR issues
                const plotlyModule = await import('plotly.js-dist-min');
                Plotly = plotlyModule.default;

                if (!isMounted) return;

                // Parse inputs from memoized strings
                let plotData = dataString ? JSON.parse(dataString) : [];
                const plotLayout = layoutString ? JSON.parse(layoutString) : {};
                const plotConfig = configString ? JSON.parse(configString) : {};

                // Default styles
                const defaultLayout = {
                    paper_bgcolor: 'rgba(0,0,0,0)',
                    plot_bgcolor: 'rgba(0,0,0,0)',
                    font: {
                        color: '#e0e0e0',
                        family: 'monospace'
                    },
                    margin: { t: 20, r: 20, b: 40, l: 40 },
                    xaxis: {
                        gridcolor: '#333',
                        zerolinecolor: '#333',
                    },
                    yaxis: {
                        gridcolor: '#333',
                        zerolinecolor: '#333',
                    },
                    autosize: true,
                    ...plotLayout
                };

                const defaultConfig = {
                    displayModeBar: false,
                    responsive: true,
                    ...plotConfig
                };

                // Downgrade WebGL traces to SVG if not explicitly required
                // This helps avoid "Too many active WebGL contexts"
                if (Array.isArray(plotData)) {
                    plotData = plotData.map(trace => {
                        // If it's a scattergl with < 5000 points, use scatter
                        if (trace.type === 'scattergl') {
                            const pointCount = (trace.x?.length || 0);
                            if (pointCount < 5000) {
                                return { ...trace, type: 'scatter' };
                            }
                        }
                        // If it's bargl, use bar
                        if (trace.type === 'bargl') {
                            const pointCount = (trace.x?.length || 0);
                            if (pointCount < 5000) {
                                return { ...trace, type: 'bar' };
                            }
                        }
                        return trace;
                    });
                }

                // Initial Plot or Update
                // We use React to update efficiently, but NewPlot is safer for full re-renders
                // to ensure we don't leak contexts if the DOM node was recycled weirdly.
                // However, the user requested: newPlot on first mount, react on updates.

                // Check if the element already has a plot
                if (chartElement._fullLayout) {
                    Plotly.react(chartElement, plotData, defaultLayout, defaultConfig);
                } else {
                    Plotly.newPlot(chartElement, plotData, defaultLayout, defaultConfig);
                }

                // Handle Resize
                // Plotly.react handles responsive: true in config, but sometimes explicit resize is needed
                // The user requested a resize listener.
                // We'll attach one window resize listener.

            } catch (err) {
                console.error("Error rendering PlotlyChart:", err, { dataString, layoutString, configString });
            }
        };

        initPlot();

        // Resize Handler
        const handleResize = () => {
            if (chartElement && Plotly) {
                Plotly.Plots.resize(chartElement);
            }
        };
        window.addEventListener('resize', handleResize);

        // Cleanup - use captured chartElement ref
        return () => {
            isMounted = false;
            window.removeEventListener('resize', handleResize);
            if (chartElement && Plotly) {
                try {
                    Plotly.purge(chartElement);
                } catch (e) {
                    console.warn("Failed to purge Plotly chart:", e);
                }
            }
        };
    }, [dataString, layoutString, configString]); // Dependencies are the stringified props

    return (
        <div
            ref={chartRef}
            className={className}
            style={{ width: '100%', height: '100%', ...style }}
        />
    );
}
