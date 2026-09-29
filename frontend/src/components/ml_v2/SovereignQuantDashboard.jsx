import React, { useState } from "react";
import RegimeWaves3D from "./RegimeWaves3D";
import AnomalyGravityWell from "./AnomalyGravityWell";
import MonteCarloCone from "./MonteCarloCone";
import LiquidityCanyons3D from "./LiquidityCanyons3D";
import GalaxyStarMap from "./GalaxyStarMap";
import IntrinsicWarp from "./IntrinsicWarp";

export default function SovereignQuantDashboard() {
  const [ticker, setTicker] = useState("NVDA");
  const [activeTab, setActiveTab] = useState("state-engine");

  const tabs = [
    { id: "state-engine", name: "🏆 State Engine", icon: "💎" },
    { id: "probability", name: "🎲 Probability Hub", icon: "🎯" },
    { id: "galaxy", name: "🌌 The Galaxy", icon: "✨" },
    { id: "valuation", name: "⚖️ Intrinsic Warp", icon: "⚖️" },
  ];

  return (
    <div className="min-h-screen bg-[#050505] text-terminal-cyan font-mono p-4 lg:p-10 selection:bg-terminal-cyan selection:text-black">
      {/* Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6 mb-12 border-b border-terminal-cyan/10 pb-10">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <div className="w-3 h-3 bg-terminal-cyan animate-pulse rounded-full shadow-[0_0_15px_rgba(0,255,255,0.8)]" />
            <h1 className="text-3xl lg:text-5xl font-bold tracking-tighter text-white">SOVEREIGN QUANT <span className="text-terminal-cyan">v2.0</span></h1>
          </div>
          <p className="text-terminal-cyan/50 text-xs tracking-[0.2em] font-medium uppercase">Institutional Mission Control Engine // Zero-Pressure Architecture</p>
        </div>

        <div className="relative group">
          <input
            type="text"
            value={ticker}
            onChange={(e) => setTicker(e.target.value.toUpperCase())}
            className="bg-black/40 border-2 border-terminal-cyan/30 rounded-lg px-6 py-4 text-2xl font-bold text-white focus:border-terminal-cyan focus:outline-none transition-all w-48 text-center placeholder:text-terminal-cyan/20 group-hover:border-terminal-cyan/60"
            placeholder="TICKER"
          />
          <div className="absolute -top-3 left-4 px-2 bg-[#050505] text-[10px] text-terminal-cyan/60 font-bold uppercase tracking-widest">Active Target</div>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="flex flex-wrap gap-2 mb-8">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-3 px-6 py-3 rounded-lg border-2 transition-all text-sm font-bold uppercase tracking-widest ${
              activeTab === tab.id
                ? "bg-terminal-cyan text-black border-terminal-cyan shadow-[0_0_20px_rgba(0,255,255,0.4)]"
                : "bg-black/40 text-terminal-cyan border-terminal-cyan/20 hover:border-terminal-cyan/50 hover:bg-terminal-cyan/5"
            }`}
          >
            <span>{tab.icon}</span>
            {tab.name}
          </button>
        ))}
      </div>

      {/* Content Area */}
      <div className="space-y-10 animate-in fade-in slide-in-from-bottom duration-700">
        {activeTab === "state-engine" && (
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-10">
             <div className="space-y-4">
                <RegimeWaves3D ticker={ticker} />
             </div>
             <div className="space-y-4">
                <AnomalyGravityWell ticker={ticker} />
             </div>
          </div>
        )}

        {activeTab === "probability" && (
           <div className="grid grid-cols-1 xl:grid-cols-2 gap-10">
              <MonteCarloCone ticker={ticker} />
              <LiquidityCanyons3D ticker={ticker} />
           </div>
        )}

        {activeTab === "galaxy" && (
            <GalaxyStarMap />
        )}

        {activeTab === "valuation" && (
            <IntrinsicWarp ticker={ticker} />
        )}
      </div>

      {/* Footer System Status */}
      <div className="mt-20 pt-8 border-t border-terminal-cyan/5 flex flex-col md:flex-row justify-between gap-10 text-[10px] text-terminal-cyan/40">
        <div className="flex gap-10">
            <div className="flex items-center gap-2">
                <div className="w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse" />
                <span>NOHUP HARVESTER: ACTIVE [93059]</span>
            </div>
            <div>COMPUTE: LOCAL GPU (WEBGL 2.0)</div>
            <div>LATENCY: 12ms</div>
        </div>
        <div className="tracking-widest">QUANT360 SOVEREIGN TERMINAL OS v4.2 // CLUSTER D-F-G INTEGRATION</div>
      </div>
    </div>
  );
}
