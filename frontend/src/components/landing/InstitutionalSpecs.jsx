"use client";

import React, { useEffect, useRef } from "react";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { Check, Terminal, Cpu, Database, Activity, Code2 } from "lucide-react";

gsap.registerPlugin(ScrollTrigger);

const SPECS = [
  {
    category: "Technical Analysis",
    items: [
      { name: "Total Indicators", val: "400+", desc: "Built-in & open-source libraries" },
      { name: "Smart Drawings", val: "110+", desc: "Fibonacci, Gann, Pitchforks" },
      { name: "Volume Profiling", val: "YES", desc: "TPO and Volume Delta maps" },
      { name: "Candlestick Recognition", val: "NATIVE", desc: "Auto-detection of 45 patterns" }
    ],
    color: "violet"
  },
  {
    category: "System Engine",
    items: [
      { name: "Tick Latency", val: "< 50ms", desc: "Global edge-cached data streams" },
      { name: "Replay Mode", val: "9 SPEEDS", desc: "Tick-by-tick historical simulation" },
      { name: "Watchlist Sync", val: "CLOUD", desc: "Real-time sync across all modules" },
      { name: "Multi-Chart Hub", val: "8 GRID", desc: "Up to 8 concurrent sync charts" }
    ],
    color: "emerald"
  }
];

export default function InstitutionalSpecs() {
  const containerRef = useRef(null);
  const gridPathRef = useRef(null);

  useEffect(() => {
    const ctx = gsap.context(() => {
      // 1. Draw the Blueprint Grid
      gsap.fromTo(".blueprint-line", 
        { strokeDashoffset: 1000 },
        { 
          strokeDashoffset: 0, 
          duration: 3, 
          ease: "power2.inOut",
          scrollTrigger: {
            trigger: containerRef.current,
            start: "top 80%",
            end: "bottom 20%",
            scrub: 1
          }
        }
      );

      // 2. Animate the spec cards
      gsap.from(".spec-card", {
        y: 100,
        opacity: 0,
        stagger: 0.2,
        duration: 1,
        ease: "power4.out",
        scrollTrigger: {
          trigger: ".spec-grid",
          start: "top 80%"
        }
      });
    }, containerRef);
    return () => ctx.revert();
  }, []);

  return (
    <section ref={containerRef} className="py-24 bg-[#030510] relative overflow-hidden">
      {/* Background Animated Blueprint Grid */}
      <div className="absolute inset-0 z-0 opacity-20 pointer-events-none">
        <svg width="100%" height="100%" className="overflow-visible">
           {[...Array(20)].map((_, i) => (
             <React.Fragment key={i}>
                <line 
                  className="blueprint-line" 
                  x1="0" y1={i * 100} x2="100%" y2={i * 100} 
                  stroke="#8b5cf6" strokeWidth="0.5" strokeDasharray="1000"
                />
                <line 
                  className="blueprint-line" 
                  x1={i * 200} y1="0" x2={i * 200} y2="100%" 
                  stroke="#8b5cf6" strokeWidth="0.5" strokeDasharray="1000"
                />
             </React.Fragment>
           ))}
        </svg>
      </div>

      <div className="relative z-10 max-w-7xl mx-auto px-6">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-20">
          
          {/* Left Column: Vision Statement */}
          <div className="flex flex-col justify-center">
            <div className="flex items-center gap-3 mb-8 opacity-40">
               <Code2 className="w-5 h-5 text-violet-500" />
               <div className="h-px flex-grow bg-gradient-to-r from-violet-500 to-transparent" />
            </div>
            <h2 className="text-4xl md:text-6xl font-black text-white mb-8 tracking-tighter leading-none uppercase">
              Technical<br />
              <span className="text-violet-500 italic">Specifications.</span>
            </h2>
            <p className="text-gray-400 text-lg mb-10 max-w-md font-mono lowercase">
              [04] the quant360 terminal is not just a platform. it is a weaponized research laboratory for the 0.1%.
            </p>
            
            <div className="grid grid-cols-2 gap-6">
               <div className="p-6 rounded-2xl bg-white/5 border border-white/10 group hover:border-violet-500/50 transition-colors">
                  <Terminal className="w-6 h-6 text-violet-500 mb-4" />
                  <div className="text-xs font-bold text-white uppercase tracking-tighter mb-1">PinScript_Runtime</div>
                  <div className="text-[10px] text-gray-500 uppercase">Script Execution Lab</div>
               </div>
               <div className="p-6 rounded-2xl bg-white/5 border border-white/10 group hover:border-emerald-500/50 transition-colors">
                  <Cpu className="w-6 h-6 text-emerald-500 mb-4" />
                  <div className="text-xs font-bold text-white uppercase tracking-tighter mb-1">Hydra_Compute</div>
                  <div className="text-[10px] text-gray-600 uppercase">Distributed Calculations</div>
               </div>
            </div>
          </div>

          {/* Right Column: Spec Grid (High Density) */}
          <div className="spec-grid grid grid-cols-1 md:grid-cols-2 gap-4">
             {SPECS.map((group, idx) => (
                <div key={idx} className="spec-card bg-white/[0.03] border border-white/5 rounded-3xl p-8 backdrop-blur-md relative overflow-hidden group">
                   <div className={`absolute top-0 right-0 w-24 h-24 bg-gradient-to-br ${group.color === 'violet' ? 'from-violet-500/20' : 'from-emerald-500/20'} to-transparent opacity-0 group-hover:opacity-100 transition-opacity`} />
                   
                   <h3 className="text-[10px] font-mono text-gray-600 mb-8 uppercase tracking-[0.4em]">{group.category}</h3>
                   <div className="space-y-8">
                      {group.items.map((item, i) => (
                         <div key={i} className="relative z-10">
                            <div className="flex justify-between items-end mb-2">
                               <span className="text-sm font-bold text-white/80">{item.name}</span>
                               <span className={`text-base font-black ${group.color === 'violet' ? 'text-violet-500' : 'text-emerald-500'} tracking-tighter`}>{item.val}</span>
                            </div>
                            <div className="text-[9px] text-gray-500 font-mono flex items-center gap-2 uppercase">
                               <Check className={`w-3 h-3 ${group.color === 'violet' ? 'text-violet-800' : 'text-emerald-800'}`} />
                               {item.desc}
                            </div>
                         </div>
                      ))}
                   </div>
                </div>
             ))}
          </div>

        </div>
      </div>
    </section>
  );
}
