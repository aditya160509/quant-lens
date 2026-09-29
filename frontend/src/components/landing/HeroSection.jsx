"use client";

import React from "react";
import { motion } from "framer-motion";
import Link from "next/link";
import { 
  ArrowRight, 
  Terminal,
} from "lucide-react";
import BlurText from "../ui/enhanced/BlurText";

const slideInFromLeft = (delay) => ({
  hidden: { x: -60, opacity: 0 },
  visible: {
    x: 0,
    opacity: 1,
    transition: { delay, duration: 0.8, ease: [0.16, 1, 0.3, 1] },
  },
});

export default function HeroSection() {
  return (
    <section className="relative min-h-screen flex items-center overflow-hidden">
      {/* Ultra-Fidelity Background Reactor */}
      <div className="absolute inset-0 z-0 bg-[#02040a]">
        <video
          autoPlay
          muted
          loop
          playsInline
          className="absolute inset-0 w-full h-full object-cover pointer-events-none opacity-40 mix-blend-lighten"
        >
          <source src="/hero_quantum_ultra.webm" type="video/webm" />
          <source src="/hero_quantum_ultra.mp4" type="video/mp4" />
        </video>
        
        {/* Cinematic Overlays */}
        <div className="absolute inset-0 bg-gradient-to-r from-[#02040a] via-[#02040a]/20 to-transparent z-10" />
        <div className="absolute inset-0 bg-gradient-to-b from-[#02040a]/10 via-transparent to-[#02040a] z-10" />
        
        {/* High-End Noise Overlay */}
        <div className="absolute inset-0 opacity-[0.02] pointer-events-none z-10 bg-[url('https://grainy-gradients.vercel.app/noise.svg')]" />
      </div>

      <div className="relative z-20 w-full max-w-7xl mx-auto px-6 lg:px-12 py-16">
        <div className="grid lg:grid-cols-12 gap-8 items-center min-h-[80vh]">
          
          <div className="lg:col-span-12 flex flex-col items-center text-center">
            {/* Removed version badge per user request */}

            {/* Main Heading Refinement based on high-end search results */}
            <div className="mb-10 space-y-2">
              <h1 className="text-4xl sm:text-6xl lg:text-7xl xl:text-8xl font-medium tracking-tight text-white font-display overflow-hidden uppercase">
                <BlurText 
                  text="ALGORITHMIC EDGE." 
                  delay={50} 
                  animateBy="letters" 
                  direction="bottom" 
                />
              </h1>
              <h1 className="text-4xl sm:text-6xl lg:text-7xl xl:text-8xl font-medium tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-violet-400 via-indigo-400 to-emerald-400 font-display uppercase">
                <BlurText 
                  text="ABSOLUTE PERFORMANCE." 
                  delay={400} 
                  animateBy="letters" 
                  direction="bottom" 
                />
              </h1>
              <h1 className="text-2xl sm:text-4xl lg:text-5xl font-light tracking-[0.2em] text-gray-400 font-display uppercase mt-4">
                <BlurText 
                  text="& QUANTITATIVE DYNAMICS" 
                  delay={800} 
                  animateBy="letters" 
                  direction="bottom" 
                />
              </h1>
            </div>

            <motion.div 
               initial={{ opacity: 0, y: 20 }}
               animate={{ opacity: 1, y: 0 }}
               transition={{ delay: 0.8 }}
               className="flex flex-wrap justify-center gap-x-12 gap-y-4 mb-12 opacity-50"
            >
               {["NEURAL EXECUTION", "VECTOR ANALYTICS", "ALPHA PROTOCOLS", "QUANTUM RISK"].map((header, i) => (
                 <div key={i} className="flex items-center gap-3">
                   <div className="w-1 h-1 rounded-full bg-violet-500" />
                   <span className="text-[10px] font-mono tracking-[0.3em] text-white uppercase">{header}</span>
                 </div>
               ))}
            </motion.div>

            <div className="text-base sm:text-lg mb-12 max-w-2xl text-gray-400 font-sans leading-relaxed mx-auto">
              ATLAS // The definitive market vector processing engine for modern institutional desks. 
              Recursive alpha generation engineered for zero-latency execution.
            </div>

            <motion.div
              initial="hidden"
              animate="visible"
              variants={slideInFromLeft(0.6)}
              className="flex flex-col sm:flex-row gap-6 justify-center"
            >
              <Link
                href="/labs"
                className="group px-12 py-5 rounded-full font-bold text-[12px] uppercase tracking-widest
                           bg-white text-black hover:bg-violet-500 hover:text-white
                           transition-all duration-500 flex items-center justify-center gap-3 shadow-[0_10px_40px_rgba(255,255,255,0.05)]"
              >
                Launch Terminal
                <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
              </Link>
              
              <Link
                href="/labs"
                className="group px-12 py-5 rounded-full font-bold text-[12px] uppercase tracking-widest
                           bg-white/5 border border-white/10 text-white
                           hover:border-violet-500/40 hover:bg-white/10
                           backdrop-blur-md transition-all duration-300
                           flex items-center justify-center gap-2"
              >
                Deep Research
              </Link>
            </motion.div>
          </div>
        </div>
      </div>
    </section>
  );
}
