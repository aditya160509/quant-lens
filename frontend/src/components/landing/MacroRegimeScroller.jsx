"use client";

import React, { useEffect, useRef } from "react";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { ArrowUpRight, ShieldAlert, BarChart, Zap, Layers } from "lucide-react";
import BlurText from "../ui/enhanced/BlurText";

gsap.registerPlugin(ScrollTrigger);

const REGIMES = [
  {
    id: "01",
    label: "The Expansion",
    status: "BULLISH",
    desc: "low volatility and steady trending. neural weights shift toward momentum-alpha. liquidity clusters forming at support.",
    stats: { confidence: "94%", priority: "MEDIUM" },
    icon: Zap,
    color: "emerald"
  },
  {
    id: "02",
    label: "High Volatility",
    status: "DISRUPTION",
    desc: "vix spikes and standard models fail. the neural-signal hub activates recursive filtering to find signal in the noise.",
    stats: { confidence: "82%", priority: "URGENT" },
    icon: ShieldAlert,
    color: "orange"
  },
  {
    id: "03",
    label: "Systemic Reset",
    status: "BEARISH",
    desc: "panic-selling creates liquidity gaps. our risk-vault scales down exposures and targets hedged short-alpha clusters.",
    stats: { confidence: "89%", priority: "CRITICAL" },
    icon: BarChart,
    color: "red"
  },
  {
    id: "04",
    label: "Mean Reversion",
    status: "RANGE",
    desc: "price oscillates within high-conviction zones. delta-neutral strategies deployed across the systemic node network.",
    stats: { confidence: "91%", priority: "STABLE" },
    icon: Layers,
    color: "blue"
  }
];

export default function MacroRegimeScroller() {
  const containerRef = useRef(null);
  const sectionRef = useRef(null);
  const marqueeRef = useRef(null);

  useEffect(() => {
    const ctx = gsap.context(() => {
      // 1. Horizontal Infinite Loop Logic
      const marquee = marqueeRef.current;
      const totalWidth = marquee.scrollWidth / 3;

      gsap.to(marquee, {
        x: `-=${totalWidth}`,
        duration: 40,
        ease: "none",
        repeat: -1,
      });

      // 2. Pinning Fix for React 19/Turbopack
      // We pin the inner section using the outer div as the trigger.
      ScrollTrigger.create({
        trigger: containerRef.current,
        pin: sectionRef.current,
        start: "top top",
        end: "+=150%",
        scrub: 1,
        anticipatePin: 1
      });
      
    }, containerRef);

    return () => ctx.revert();
  }, []);

  return (
    <div ref={containerRef} className="relative">
      <section ref={sectionRef} className="relative min-h-screen bg-[#02040a] flex flex-col justify-center overflow-hidden">
        {/* Huly Laser Background Layer */}
        <div className="absolute inset-0 z-0 overflow-hidden">
          <video
            autoPlay
            muted
            loop
            playsInline
            className="absolute inset-0 w-full h-full object-cover opacity-25 grayscale-[0.6]"
          >
            <source src="/huly_laser_remix.webm" type="video/webm" />
          </video>
          <div className="absolute inset-0 bg-gradient-to-b from-[#02040a] via-transparent to-[#02040a] z-10" />
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,_transparent_0%,_#02040a_100%)] opacity-80 z-10" />
        </div>
        
        <div className="max-w-[1400px] mx-auto px-10 mb-20 relative z-20 w-full">
           <div className="flex flex-col gap-6">
              <h3 className="text-violet-400 font-mono text-[9px] tracking-[0.5em] uppercase flex items-center gap-4">
                 <span className="w-10 h-px bg-violet-500/30" />
                 Adaptive_Regime_Protocols
              </h3>
              <h2 className="text-4xl md:text-6xl font-medium text-white tracking-tight font-display max-w-2xl leading-[1.1]">
                <BlurText text="Built for every" delay={30} animateBy="letters" />
                <br/>
                <span className="text-transparent bg-clip-text bg-gradient-to-r from-violet-500 via-indigo-400 to-emerald-500">
                  <BlurText text="Genetic Shift." delay={150} animateBy="letters" />
                </span>
              </h2>
           </div>
        </div>

        {/* Infinite Marquee Container */}
        <div className="relative w-full overflow-hidden z-20">
          <div ref={marqueeRef} className="flex gap-8 whitespace-nowrap py-10">
            {[...REGIMES, ...REGIMES, ...REGIMES].map((regime, i) => (
              <div 
                key={i}
                className="relative flex-shrink-0 w-[420px] rounded-[2rem] bg-white/[0.03] border border-white/5 backdrop-blur-2xl overflow-hidden group hover:border-white/10 transition-all duration-700"
              >
                <div className="p-10 space-y-8">
                  <div className="flex justify-between items-start">
                     <div className="space-y-1">
                        <span className="text-[9px] font-mono text-gray-600 tracking-widest uppercase">{regime.status}</span>
                        <h3 className="text-2xl font-medium text-white tracking-tight font-display">
                          {regime.label}
                        </h3>
                     </div>
                     <div className={`p-3.5 rounded-2xl bg-${regime.color}-500/5 border border-${regime.color}-500/20`}>
                        <regime.icon className={`w-5 h-5 text-${regime.color}-400/80 shadow-glow`} />
                     </div>
                  </div>

                  <p className="text-gray-500 font-sans text-xs leading-relaxed whitespace-normal lowercase h-12">
                     {regime.desc}
                  </p>

                  <div className="flex items-center gap-6 pt-6 border-t border-white/5">
                     <button className="flex items-center gap-3 text-[9px] font-mono text-gray-300 tracking-[0.2em] uppercase hover:text-white transition-all group/btn">
                        Read Protocol <ArrowUpRight className="w-3.5 h-3.5 text-violet-500 group-hover/btn:rotate-45 transition-transform" />
                     </button>
                  </div>

                  <div className="flex gap-4 items-center">
                      <div className="flex-1 space-y-2">
                         <div className="flex justify-between text-[8px] font-mono text-gray-700 uppercase">
                            <span>Confidence</span>
                            <span>{regime.stats.confidence}</span>
                         </div>
                         <div className="h-0.5 w-full bg-white/5 rounded-full overflow-hidden">
                            <div className={`h-full bg-${regime.color}-500/30`} style={{ width: regime.stats.confidence }} />
                         </div>
                      </div>
                  </div>
                </div>
              </div>
            ))}
          </div>

          <div className="absolute bottom-4 left-10 flex items-center gap-4 opacity-30 pointer-events-none">
             <div className="text-[8px] font-mono text-gray-600 tracking-[0.5em] uppercase">Horizontal_Stream</div>
          </div>
        </div>
        
        <style jsx>{`
          .shadow-glow { filter: drop-shadow(0 0 8px currentColor); }
        `}</style>
      </section>
    </div>
  );
}
