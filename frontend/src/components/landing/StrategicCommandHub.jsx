"use client";

import React, { useEffect, useRef } from "react";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import DynamicTerminalKernel from "../ui/enhanced/DynamicTerminalKernel";

gsap.registerPlugin(ScrollTrigger);

export default function StrategicCommandHub() {
  const containerRef = useRef(null);
  const sectionRef = useRef(null);
  const hubRef = useRef(null);

  useEffect(() => {
    const ctx_gsap = gsap.context(() => {
       const tl = gsap.timeline({
         scrollTrigger: {
           trigger: containerRef.current,
           pin: sectionRef.current,
           start: "top top",
           end: "+=150%",
           scrub: 1.5,
           anticipatePin: 1
         }
       });

       // Premium Scrollytelling Transition
       tl.from(hubRef.current, {
          y: 200,
          rotationX: 15,
          scale: 0.9,
          opacity: 0,
          duration: 1.5,
          ease: "power3.out"
       });

       tl.to(hubRef.current, { 
          rotationY: 5, 
          duration: 1 
       }, "+=0.2");

       tl.to(hubRef.current, { 
          scale: 1.02, 
          duration: 1 
       }, "+=0.1");

    }, containerRef);

    return () => {
      ctx_gsap.revert();
    };
  }, []);

  return (
    <div ref={containerRef} className="relative">
      <section ref={sectionRef} className="relative min-h-screen bg-[#02040a] overflow-hidden flex flex-col items-center justify-center py-20">
        {/* Background Atmosphere */}
        <div className="absolute inset-0 z-0">
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[1000px] h-[1000px] bg-violet-600/5 rounded-full blur-[120px]" />
          <div className="absolute top-0 left-0 w-full h-full bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-[0.02] pointer-events-none" />
        </div>

        <div ref={hubRef} className="relative z-20 w-full px-6 flex flex-col items-center">
           <div className="mb-12 text-center max-w-2xl">
              <h3 className="text-[10px] font-mono text-gray-600 uppercase tracking-[0.5em] mb-4">Neural_Session_Initialized</h3>
              <p className="text-sm font-sans text-gray-500 lowercase leading-relaxed">
                Proprietary kernel monitoring core liquidity clusters and exchange gateways.
              </p>
           </div>
           <DynamicTerminalKernel />
        </div>

        <div className="relative z-10 w-full max-w-7xl px-6 mt-16 grid grid-cols-3 gap-8 pointer-events-none opacity-40">
          {[
            { label: "Neural_Drift", value: "0.04σ", desc: "Minimal deviation detected." },
            { label: "Alpha_Reserves", value: "Locked", desc: "Liquidity clusters finalized." },
            { label: "Packet_Loss", value: "0.00%", desc: "Full optical fiber sync." }
          ].map((stat, i) => (
            <div key={i} className="space-y-2 border-l border-white/5 pl-6 font-mono">
              <div className="text-[10px] text-gray-600 uppercase tracking-widest">{stat.label}</div>
              <div className="text-xl font-bold text-white">{stat.value}</div>
              <div className="text-[9px] text-gray-700 leading-relaxed italic">{stat.desc}</div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
