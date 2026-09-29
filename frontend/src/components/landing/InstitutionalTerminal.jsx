"use client";

import React, { useEffect, useRef, useState } from "react";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { 
  Terminal, 
  Settings, 
  Maximize2, 
  LayoutGrid, 
  LineChart, 
  Layers,
  Activity,
  Zap,
  RefreshCw,
  Search,
  Plus,
  Compass,
  BarChart3
} from "lucide-react";
import dynamic from "next/dynamic";
import { useStableDimensions } from "../chart_engine/StableChartContainer";

gsap.registerPlugin(ScrollTrigger);

const Q360ChartCore = dynamic(
  () => import("../chart_engine/q360_chart_core"),
  { ssr: false, loading: () => <div className="h-full w-full flex items-center justify-center text-violet-500/50 font-mono">Initializing Neural Chart...</div> }
);

const TERMINAL_CLUSTERS = Array.from({ length: 40 }, (_, index) => ({
  price: 95000 + ((index * 613 + 197) % 1000),
  weight: ((index * 37 + 11) % 101) / 100,
  active: (index * 19 + 3) % 10 > 6,
}));

export default function InstitutionalTerminal() {
  const containerRef = useRef(null);
  const sectionRef = useRef(null);
  const chartContainerRef = useRef(null);
  const frameRef = useRef(null);
  const [activeTab, setActiveTab] = useState("CHART");

  const dimensions = useStableDimensions(chartContainerRef);

  const [symbol, setSymbol] = useState("BTC-USD");
  const [timeframe, setTimeframe] = useState("1h");

  useEffect(() => {
    const ctx_gsap = gsap.context(() => {
       const tl = gsap.timeline({
         scrollTrigger: {
           trigger: containerRef.current,
           pin: sectionRef.current,
           start: "top top",
           end: "+=300%",
           scrub: 2,
           anticipatePin: 1
         }
       });

       tl.from(frameRef.current, { 
          rotationX: 20, 
          rotationY: -15, 
          scale: 0.8, 
          opacity: 0, 
          y: 300, 
          duration: 2, 
          ease: "expo.out" 
       });

       tl.to(frameRef.current, { rotationY: 15, duration: 2 }, "+=0.5");
       tl.to(frameRef.current, { rotationX: -15, duration: 2 }, "+=0.5");
       tl.to(frameRef.current, { rotationX: 10, rotationY: -10, scale: 1.05, duration: 2 });
       tl.to(frameRef.current, { rotationX: 0, rotationY: 0, scale: 1, duration: 1.5 });

       tl.from(".anno-1", { opacity: 0, x: -100, filter: "blur(10px)", duration: 1 }, "-=5");
       tl.to(".anno-1", { opacity: 0, scale: 0.8, duration: 0.5 }, "-=3");
       tl.from(".anno-2", { opacity: 0, x: 100, filter: "blur(10px)", duration: 1 }, "-=2.5");

    }, containerRef);

    return () => {
       ctx_gsap.revert();
    };
  }, []);

  return (
    <div ref={containerRef} className="relative">
      <section ref={sectionRef} className="relative min-h-screen bg-[#02040a] flex items-center justify-center overflow-hidden py-20">
        <div className="absolute inset-0 z-0 text-[300px] font-black opacity-[0.02] flex items-center justify-center select-none pointer-events-none italic tracking-tighter uppercase">Terminal</div>
        
        <div className="absolute left-20 top-1/2 -translate-y-1/2 z-20 pointer-events-none">
           <div className="anno-1 max-w-xs space-y-4">
              <h3 className="text-violet-400 font-mono text-[10px] tracking-[0.5em] uppercase">Phase 01</h3>
              <h2 className="text-4xl font-black text-white italic leading-tight uppercase">Institutional<br/>Core</h2>
              <p className="text-gray-500 font-mono text-xs leading-relaxed lowercase">
                 direct port of our high-speed trade execution engine. optimized for institutional throughput and zero-latency analysis.
              </p>
           </div>
        </div>

        <div className="absolute right-20 top-1/2 -translate-y-1/2 z-20 pointer-events-none">
           <div className="anno-2 max-w-xs space-y-4 text-right">
              <h3 className="text-emerald-400 font-mono text-[10px] tracking-[0.5em] uppercase">Tech Stack</h3>
              <h2 className="text-4xl font-black text-white italic leading-tight uppercase">Alpha<br/>Delivery</h2>
              <p className="text-gray-500 font-mono text-xs leading-relaxed lowercase">
                 using advanced canvas-based vector rendering for sub-pixel accuracy and high-frequency data updates.
              </p>
           </div>
        </div>

        <div 
          ref={frameRef}
          style={{ perspective: "2000px" }}
          className="terminal-frame relative z-10 w-[92%] max-w-[1440px] aspect-[16/9] rounded-[2.5rem] border border-white/10 bg-[#05070a]/90 backdrop-blur-3xl shadow-[0_0_150px_rgba(139,92,246,0.15)] overflow-hidden flex flex-col"
        >
          <div className="h-16 border-b border-white/10 bg-white/[0.02] flex items-center justify-between px-10">
             <div className="flex items-center gap-10">
                <div className="flex gap-2.5">
                   <div className="w-3.5 h-3.5 rounded-full bg-red-500/40 border border-red-500/20" />
                   <div className="w-3.5 h-3.5 rounded-full bg-yellow-500/40 border border-yellow-500/20" />
                   <div className="w-3.5 h-3.5 rounded-full bg-green-500/40 border border-green-500/20" />
                </div>
                <div className="h-6 w-px bg-white/10" />
                <nav className="flex items-center gap-10">
                  {["CHART", "ORDER_FLOW", "SIGNALS", "DOM"].map(tab => (
                     <button 
                       key={tab}
                       onClick={() => setActiveTab(tab)}
                       className={`text-[11px] font-mono tracking-[0.2em] transition-all ${activeTab === tab ? 'text-violet-400 font-bold scale-110' : 'text-gray-500 hover:text-white'}`}
                     >
                       {tab}
                     </button>
                  ))}
                </nav>
             </div>
             
             <div className="flex items-center gap-8 text-[11px] font-mono text-gray-400">
                <RefreshCw className="w-4 h-4 animate-spin text-emerald-500" />
                <div className="flex items-center gap-5">
                   <Search className="w-4.5 h-4.5 cursor-pointer hover:text-white transition-colors" />
                   <Settings className="w-4.5 h-4.5 cursor-pointer hover:text-white transition-colors" />
                   <Maximize2 className="w-4.5 h-4.5 cursor-pointer hover:text-white transition-colors" />
                </div>
             </div>
          </div>

          <div className="flex-grow flex relative">
             <div className="flex-grow relative bg-[#010206] flex" ref={chartContainerRef}>

                {activeTab === "CHART" ? (
                  <div className="flex-grow">
                     {dimensions.width > 0 && dimensions.height > 0 && (
                        <Q360ChartCore
                          symbol={symbol}
                          timeframe={timeframe}
                          mode="intraday"
                          width={dimensions.width - 256} 
                          height={dimensions.height}
                          onSymbolChange={setSymbol}
                          onTimeframeChange={setTimeframe}
                        />
                     )}
                  </div>
                ) : (
                  <div className="flex-grow flex items-center justify-center text-gray-700 font-mono text-xs uppercase tracking-widest">
                     Module Offline in Preview Mode
                  </div>
                )}

                <div className="w-64 bg-black/60 border-l border-white/5 backdrop-blur-3xl p-8 z-20">
                   <div className="text-[10px] font-mono text-gray-600 uppercase mb-8 tracking-[0.3em] flex items-center justify-between">
                      <span>DOM Activity</span>
                      <div className="w-2 h-2 rounded-full bg-violet-500 animate-pulse" />
                   </div>
                   <div className="space-y-6">
                      {TERMINAL_CLUSTERS.slice(0, 14).map((c, i) => (
                         <div key={i} className="group cursor-default">
                            <div className="flex justify-between items-center text-[10px] font-mono text-gray-500 mb-2">
                               <span className="group-hover:text-white transition-colors">{(c.price).toFixed(0)}</span>
                               <span className={c.active ? 'text-violet-400 font-bold' : 'text-gray-800'}>{Math.round(c.weight * 100)}%</span>
                            </div>
                            <div className="h-1.5 w-full bg-white/5 rounded-full overflow-hidden">
                               <div className="h-full bg-violet-600 shadow-[0_0_10px_rgba(139,92,246,0.5)] transition-all duration-1000" style={{ width: `${c.weight * 100}%`, opacity: c.active ? 1 : 0.2 }} />
                            </div>
                         </div>
                      ))}
                   </div>
                </div>
             </div>
          </div>

          <div className="h-10 border-t border-white/10 bg-black flex items-center justify-between px-8">
             <div className="flex items-center gap-10">
                <div className="text-[10px] font-mono text-gray-600 uppercase flex items-center gap-3">
                   <div className="w-2 h-2 rounded-full bg-emerald-500" />
                   System: 100% Operational // Alpha Sync
                </div>
             </div>
             <div className="text-[10px] font-mono text-gray-700 uppercase tracking-widest">Neural Terminal Environment</div>
          </div>
        </div>
      </section>
    </div>
  );
}
