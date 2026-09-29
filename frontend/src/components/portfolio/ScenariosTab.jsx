import React, { useState } from 'react';
import { runScenario } from '@/lib/api';
import { Loader2 } from 'lucide-react';

export default function ScenariosTab({ holdings }) {
    const [scenario, setScenario] = useState("rates_up_200bp");
    const [shockSize, setShockSize] = useState(0.0); // For custom, or implicit in backend
    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState(null);

    const SCENARIOS = [
        { id: "rates_up_200bp", label: "Interest Rates +200bps" },
        { id: "equity_minus_20", label: "Global Equity Market Crash (-20%)" },
        { id: "inflation_shock", label: "Inflation Surprise (Stagflation)" },
        { id: "crash_2008", label: "2008 Financial Crisis Replay" },
        { id: "covid_2020", label: "Covid-19 2020 Crash" }
    ];

    const handleRun = async () => {
        setLoading(true);
        try {
            const res = await runScenario({ scenarioId: scenario, shockSize });
            setResult(res);
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="flex flex-col h-full p-1 gap-4">
            <div className="flex gap-4 items-center bg-terminal-darker p-3 rounded border border-terminal-gray/30">
                <select
                    value={scenario}
                    onChange={(e) => setScenario(e.target.value)}
                    className="bg-terminal-black border border-terminal-gray text-xs p-2 rounded outline-none w-64"
                >
                    {SCENARIOS.map(s => <option key={s.id} value={s.id}>{s.label}</option>)}
                </select>

                <button
                    onClick={handleRun}
                    disabled={loading || holdings.length === 0}
                    className="ml-auto bg-terminal-dark border border-terminal-red text-terminal-red px-6 py-2 text-xs font-bold rounded hover:bg-terminal-red hover:text-black transition-colors disabled:opacity-50"
                >
                    {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : "STRESS TEST"}
                </button>
            </div>

            {result && (
                <div className="flex-1 overflow-auto">
                    {/* Summary Card */}
                    <div className="bg-terminal-darker p-4 rounded border border-terminal-gray/30 mb-4 flex justify-between items-center">
                        <div>
                            <div className="text-xs text-terminal-dim uppercase">Total Portfolio Impact</div>
                            <div className="text-lg font-mono font-bold text-terminal-text">
                                ${(result.shocked_value - result.base_value).toLocaleString(undefined, { maximumFractionDigits: 0 })}
                            </div>
                        </div>
                        <div className={`text-2xl font-bold ${result.total_impact >= 0 ? 'text-terminal-green' : 'text-terminal-red'}`}>
                            {result.total_impact >= 0 ? '+' : ''}{(result.total_impact * 100).toFixed(2)}%
                        </div>
                    </div>

                    {/* Detailed Impacts */}
                    <h4 className="text-xs font-bold text-terminal-dim uppercase mb-2">Impact by Position</h4>
                    <div className="space-y-2">
                        {Object.entries(result.impacts).map(([ticker, impact]) => {
                            const isPos = impact >= 0;
                            const val = impact * 100;
                            // Simple bar viz
                            const width = Math.min(Math.abs(val) * 2, 100);

                            return (
                                <div key={ticker} className="flex items-center gap-4 text-xs">
                                    <div className="w-16 font-bold text-terminal-text">{ticker}</div>
                                    <div className="flex-1 bg-terminal-black h-6 relative rounded overflow-hidden flex items-center">
                                        <div className="absolute left-1/2 top-0 bottom-0 w-px bg-terminal-gray/50"></div>
                                        <div
                                            className={`h-4 ${isPos ? "bg-terminal-green" : "bg-terminal-red"}`}
                                            style={{
                                                width: `${width}%`,
                                                marginLeft: isPos ? "50%" : `calc(50% - ${width}%)`
                                            }}
                                        />
                                    </div>
                                    <div className={`w-16 text-right font-mono ${isPos ? "text-terminal-green" : "text-terminal-red"}`}>
                                        {isPos ? '+' : ''}{val.toFixed(2)}%
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}

            {!result && !loading && (
                <div className="flex-1 flex items-center justify-center text-terminal-dim italic">
                    Select a stress scenario to see potential portfolio impact.
                </div>
            )}
        </div>
    );
}
