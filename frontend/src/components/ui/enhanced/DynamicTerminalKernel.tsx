"use client";

import React, { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Terminal, Activity, ShieldAlert, Cpu } from "lucide-react";

const LOG_MESSAGES = [
  "> INITIALIZING_QUANT_CORE_V5.0",
  "> ALLOCATING_NEURAL_VECTORS...",
  "> SYNCING_GLOBAL_LIQUIDITY_POOLS",
  "> CURRENT_REGIME: RISK_ON_ACCELERATION",
  "> ALPHA_CONFIDENCE: 98.2%",
  "> KERNEL_ACTIVE // NODE_4096",
  "> ANALYZING_CORRELATION_CLUSTERS...",
  "> SYSTEM_STABLE_//_ZERO_LATENCY",
];

const DiagnosticBar = ({ label, value, color = "violet" }) => (
  <div className="space-y-1.5 w-full">
    <div className="flex justify-between text-[8px] font-mono text-gray-500 uppercase tracking-[0.2em]">
      <span>{label}</span>
      <span className={color === 'emerald' ? 'text-emerald-400' : color === 'red' ? 'text-red-400' : 'text-violet-400'}>{value}%</span>
    </div>
    <div className="h-0.5 w-full bg-white/5 rounded-full overflow-hidden">
      <motion.div 
        initial={{ width: 0 }}
        whileInView={{ width: `${value}%` }}
        transition={{ duration: 1.5, ease: "circOut" }}
        className={`h-full ${color === 'emerald' ? 'bg-emerald-500' : color === 'red' ? 'bg-red-500' : 'bg-violet-500'} shadow-[0_0_8px_rgba(139,92,246,0.2)]`}
      />
    </div>
  </div>
);

export default function DynamicTerminalKernel() {
  const [logs, setLogs] = useState([]);
  const [currentStep, setCurrentStep] = useState(0);
  const containerRef = useRef(null);

  useEffect(() => {
    if (currentStep < LOG_MESSAGES.length) {
      const timeout = setTimeout(() => {
        setLogs(prev => [...prev, LOG_MESSAGES[currentStep]].slice(-5));
        setCurrentStep(prev => prev + 1);
      }, 1500);
      return () => clearTimeout(timeout);
    } else {
      const resetTimeout = setTimeout(() => {
        setLogs([]);
        setCurrentStep(0);
      }, 5000);
      return () => clearTimeout(resetTimeout);
    }
  }, [currentStep]);

  return (
    <div 
      ref={containerRef}
      className="relative w-full max-w-6xl mx-auto aspect-[21/9] rounded-[2rem] border border-white/5 overflow-hidden shadow-[0_0_80px_rgba(139,92,246,0.05)] group bg-[#02040a]"
    >
      {/* Background Reactor - Subtler Cinematic Video */}
      <div className="absolute inset-0 z-0">
        <video
          autoPlay
          muted
          loop
          playsInline
          className="absolute inset-0 w-full h-full object-cover pointer-events-none grayscale opacity-20 group-hover:opacity-30 transition-all duration-1000"
        >
          <source src="/hero_quantum_ultra.webm" type="video/webm" />
          <source src="/hero_quantum_ultra.mp4" type="video/mp4" />
        </video>
        <div className="absolute inset-0 bg-gradient-to-t from-[#02040a] via-transparent to-[#02040a] z-10" />
      </div>

      {/* Glass Hardware Frame */}
      <div className="absolute inset-0 z-20 backdrop-blur-xl bg-black/40 border border-white/5 m-4 rounded-[1.5rem] flex flex-col">
        {/* Top Header Bar */}
        <div className="h-10 border-b border-white/5 flex items-center justify-between px-6 bg-black/20">
          <div className="flex items-center gap-2">
            <div className="w-1.5 h-1.5 rounded-full bg-white/10" />
            <div className="w-1.5 h-1.5 rounded-full bg-white/10" />
            <div className="w-1.5 h-1.5 rounded-full bg-white/10" />
            <span className="ml-4 text-[9px] font-mono text-gray-500 uppercase tracking-[0.4em] flex items-center gap-2">
              <Terminal className="w-3 h-3" /> Kernel_Session_v5.0
            </span>
          </div>
          <div className="text-[9px] font-mono text-violet-400/60 uppercase tracking-widest">
            Protocol: Enabled
          </div>
        </div>

        {/* Main Content */}
        <div className="flex-grow grid grid-cols-12 gap-8 p-10">
          
          {/* Left Stats */}
          <div className="col-span-3 flex flex-col justify-between py-2">
            <div className="space-y-8">
              <div className="flex items-center gap-3 text-violet-400/80">
                <Cpu className="w-4 h-4" />
                <span className="text-[9px] font-mono font-bold tracking-[0.3em] uppercase text-gray-400">System_Metrics</span>
              </div>
              <div className="space-y-6">
                <DiagnosticBar label="Neural_Load" value={78} />
                <DiagnosticBar label="Data_Converge" value={92} color="emerald" />
                <DiagnosticBar label="Alpha_Decay" value={14} color="red" />
              </div>
            </div>
            
            <div className="p-4 rounded-xl bg-white/5 border border-white/5 text-[9px] font-mono text-gray-600 leading-relaxed">
              {">"} processing cross-asset clusters...
            </div>
          </div>

          {/* Center Display */}
          <div className="col-span-6 flex flex-col items-center justify-center text-center relative">
             <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                <div className="w-64 h-64 bg-violet-500/[0.03] rounded-full blur-[80px]" />
             </div>
             
             <motion.h2 
               initial={{ opacity: 0 }}
               animate={{ opacity: 1 }}
               className="text-[9px] font-mono text-gray-600 tracking-[0.6em] uppercase mb-6"
             >
               Strategic_Core
             </motion.h2>
             
             <motion.div
               key={currentStep}
               initial={{ y: 10, opacity: 0 }}
               animate={{ y: 0, opacity: 1 }}
               className="text-4xl font-medium text-white tracking-tight uppercase leading-none mb-8 font-display"
             >
               Regime<br/>Detector
             </motion.div>
             
             <div className="w-full max-w-[200px] h-0.5 bg-white/5 rounded-full overflow-hidden">
                <motion.div 
                   animate={{ x: ["-100%", "100%"] }}
                   transition={{ duration: 3, repeat: Infinity, ease: "linear" }}
                   className="w-1/2 h-full bg-violet-500/30"
                />
             </div>
          </div>

          {/* Right Logs */}
          <div className="col-span-3 bg-white/[0.02] border border-white/5 rounded-2xl p-6 font-mono text-[9px] relative overflow-hidden">
             <div className="flex items-center justify-between mb-6 text-emerald-400/60">
                <span className="font-bold tracking-widest uppercase">Kernel_Logs</span>
                <Activity className="w-3 h-3 animate-pulse text-violet-500/50" />
             </div>
             
             <div className="space-y-4">
               <AnimatePresence mode="popLayout">
                 {logs.map((log) => (
                   <motion.div
                     key={log}
                     initial={{ opacity: 0, y: 5 }}
                     animate={{ opacity: 1, y: 0 }}
                     exit={{ opacity: 0 }}
                     className="text-gray-500 whitespace-nowrap overflow-hidden text-ellipsis"
                   >
                     {log}
                   </motion.div>
                 ))}
               </AnimatePresence>
             </div>
             
             <div className="mt-8 pt-6 border-t border-white/5">
                <div className="flex justify-between items-center text-gray-600 mb-2">
                   <ShieldAlert className="w-3 h-3" />
                   <span className="uppercase tracking-[0.4em]">Status: Nominal</span>
                </div>
             </div>
          </div>

        </div>

        {/* Footer Area */}
        <div className="h-8 border-t border-white/5 px-8 flex items-center justify-between bg-black/20">
           <div className="text-[7px] font-mono text-gray-700 uppercase tracking-widest">
             Node: Institutional_Grid_4.2
           </div>
           <div className="text-[7px] font-mono text-gray-700 uppercase tracking-widest">
             © 2026 QUANT360
           </div>
        </div>
      </div>
    </div>
  );
}
