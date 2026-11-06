"use client";

import React from "react";
import { motion } from "framer-motion";
import Link from "next/link";
import { ArrowRight, Terminal } from "lucide-react";

export default function AlphaForgeCTA() {
  return (
    <section className="relative py-48 bg-[#030510] overflow-hidden flex items-center justify-center">
      {/* Background Video (Reusing the hero asset for closure) */}
      <div className="absolute inset-0 z-0 opacity-40">
        <video
          autoPlay
          muted
          loop
          playsInline
          className="absolute inset-0 w-full h-full object-cover scale-150 grayscale brightness-[0.2]"
        >
          <source src="/hero_quantum.webm" type="video/webm" />
        </video>
        <div className="absolute inset-0 bg-gradient-to-t from-[#030510] via-transparent to-[#030510]" />
      </div>

      <div className="relative z-10 text-center max-w-4xl px-6">
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          whileInView={{ opacity: 1, scale: 1 }}
          transition={{ duration: 1 }}
        >
           <div className="inline-flex items-center gap-2 mb-8 px-4 py-2 bg-violet-600/10 border border-violet-500/20 rounded-full text-violet-400 font-mono text-xs uppercase tracking-[0.3em]">
              <Terminal className="w-3.5 h-3.5" /> Start Your Session
           </div>
           
           <h2 className="text-5xl md:text-8xl font-black text-white mb-10 tracking-tighter uppercase">
             Ready to<br />
             <span className="text-transparent bg-clip-text bg-gradient-to-r from-violet-500 to-indigo-500">Master</span>
             <br />the forge?
           </h2>

           <div className="flex flex-col sm:flex-row items-center justify-center gap-6">
              <Link
                href="/ml"
                className="group w-full sm:w-auto px-12 py-5 rounded-2xl font-black text-lg
                           bg-violet-600 text-white shadow-[0_0_50px_rgba(139,92,246,0.5)]
                           hover:shadow-[0_0_80px_rgba(139,92,246,1)] hover:scale-105
                           transition-all duration-500 flex items-center justify-center gap-4"
              >
                ENTER TERMINAL
                <ArrowRight className="w-6 h-6 group-hover:translate-x-2 transition-transform" />
              </Link>
           </div>

           <div className="mt-20 flex justify-center gap-12 opacity-30 grayscale contrast-150">
              <div className="font-black text-2xl tracking-tighter text-white">NSE</div>
              <div className="font-black text-2xl tracking-tighter text-white">NASDAQ</div>
              <div className="font-black text-2xl tracking-tighter text-white">NYSE</div>
              <div className="font-black text-2xl tracking-tighter text-white">CME</div>
           </div>
        </motion.div>
      </div>
    </section>
  );
}
