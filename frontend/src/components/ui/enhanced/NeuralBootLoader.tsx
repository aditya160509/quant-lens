"use client";

import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";

const BOOT_STEPS = [
  "Initializing Quantum Kernel...",
  "Allocating Neural Vectors...",
  "Syncing Liquidity Pools...",
  "hardware acceleration...",
  "Loading Tactical HUD...",
  "System Check: Operational"
];

export default function NeuralBootLoader({ onComplete }) {
  const [progress, setProgress] = useState(0);
  const [currentStepIndex, setCurrentStepIndex] = useState(0);
  const [isVisible, setIsVisible] = useState(true);

  useEffect(() => {
    const totalDuration = 3000; // 3 seconds boot
    const intervalTime = 30;
    const increment = (100 / (totalDuration / intervalTime));

    const progressInterval = setInterval(() => {
      setProgress(prev => {
        if (prev >= 100) {
          clearInterval(progressInterval);
          setTimeout(() => {
            setIsVisible(false);
            setTimeout(onComplete, 800);
          }, 400);
          return 100;
        }
        return prev + increment;
      });
    }, intervalTime);

    const stepInterval = setInterval(() => {
      setCurrentStepIndex(prev => {
        if (prev < BOOT_STEPS.length - 1) return prev + 1;
        clearInterval(stepInterval);
        return prev;
      });
    }, totalDuration / BOOT_STEPS.length);

    return () => {
      clearInterval(progressInterval);
      clearInterval(stepInterval);
    };
  }, [onComplete]);

  return (
    <AnimatePresence>
      {isVisible && (
        <motion.div
          initial={{ opacity: 1 }}
          exit={{ opacity: 0, filter: "blur(20px)" }}
          transition={{ duration: 0.8, ease: "circIn" }}
          className="fixed inset-0 z-[10000] bg-[#02040a] flex flex-col items-center justify-center p-12 overflow-hidden"
        >
          <div className="relative w-full max-w-sm space-y-12">
            <div className="space-y-6">
              <div className="flex justify-between items-end">
                <div className="space-y-2">
                   <div className="text-[9px] font-mono text-violet-500/60 tracking-[0.5em] uppercase font-bold">System_Boot</div>
                   <div className="text-[12px] font-mono text-white tracking-widest uppercase">
                     {BOOT_STEPS[currentStepIndex]}
                   </div>
                </div>
                <div className="text-3xl font-medium text-white tracking-tight font-display">
                  {Math.round(progress)}%
                </div>
              </div>
              
              <div className="h-0.5 w-full bg-white/5 rounded-full overflow-hidden">
                <motion.div 
                   initial={{ width: 0 }}
                   animate={{ width: `${progress}%` }}
                   className="h-full bg-violet-600 shadow-[0_0_15px_rgba(139,92,246,0.3)]"
                />
              </div>
            </div>

            <div className="flex gap-2 opacity-10 justify-center">
               {[...Array(8)].map((_, i) => (
                 <motion.div 
                   key={i}
                   animate={{ opacity: [0.1, 1, 0.1] }}
                   transition={{ duration: 1.5, repeat: Infinity, delay: i * 0.1 }}
                   className="h-0.5 w-8 bg-violet-500 rounded-full"
                 />
               ))}
            </div>
          </div>

          <div className="absolute bottom-12 text-center w-full">
              <div className="text-[8px] font-mono text-gray-700 tracking-[0.6em] uppercase">
                ATLAS // Intelligence_Core
              </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
