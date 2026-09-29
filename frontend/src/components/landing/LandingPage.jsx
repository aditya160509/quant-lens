"use client";

import React, { useEffect, useRef, useState } from "react";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { motion, AnimatePresence } from "framer-motion";
import HeroSection from "./HeroSection";
import InstitutionalTerminal from "./InstitutionalTerminal";
import StrategicCommandHub from "./StrategicCommandHub";
import MacroRegimeScroller from "./MacroRegimeScroller";
import InstitutionalSpecs from "./InstitutionalSpecs";
// import AlphaForgeCTA from "./AlphaForgeCTA";
import HomeTerminalSection from "./HomeTerminalSection";
import Footer from "./Footer";
import Lenis from "lenis";
import AuroraBackground from "../ui/enhanced/AuroraBackground";
import NeuralBootLoader from "../ui/enhanced/NeuralBootLoader";

gsap.registerPlugin(ScrollTrigger);

export default function LandingPage() {
  const [activeSection, setActiveSection] = useState("01 // COMMAND_CORE");
  const [isBooted, setIsBooted] = useState(true);
  const cursorRef = useRef(null);

  useEffect(() => {
    // 1. Lenis Global Smooth Scrolling
    const lenis = new Lenis({
      duration: 1.5,
      easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
      orientation: 'vertical',
      gestureOrientation: 'vertical',
      smoothWheel: true,
      wheelMultiplier: 1.1,
      smoothTouch: false,
      touchMultiplier: 2,
    });

    function raf(time) {
      lenis.raf(time);
      requestAnimationFrame(raf);
    }
    requestAnimationFrame(raf);

    lenis.on('scroll', ScrollTrigger.update);
    gsap.ticker.add((time) => {
      lenis.raf(time * 1000);
    });
    gsap.ticker.lagSmoothing(0);

    // 2. Magnetic Cursor
    const cursor = cursorRef.current;
    if (!cursor) return;

    const moveCursor = (e) => {
      gsap.to(cursor, {
        x: e.clientX,
        y: e.clientY,
        duration: 0.2,
        ease: "power3.out"
      });
    };

    window.addEventListener("mousemove", moveCursor);

    // 3. Track active sections for the Progress HUD
    const sections = [
      { id: "COMMAND_CORE", label: "01 // COMMAND_CORE" },
      { id: "TERMINAL", label: "02 // INSTITUTIONAL" },
      { id: "TERMINAL_CORE", label: "03 // KERNEL" },
      { id: "REGIME_FLOW", label: "04 // REGIMES" }
    ];

    sections.forEach((section, i) => {
      const el = document.getElementById(section.id);
      if (el) {
        ScrollTrigger.create({
          trigger: el,
          start: "top center",
          end: "bottom center",
          onEnter: () => setActiveSection(section.label),
          onEnterBack: () => setActiveSection(section.label)
        });
      }
    });

    return () => {
      window.removeEventListener("mousemove", moveCursor);
      lenis.destroy();
      ScrollTrigger.getAll().forEach(t => t.kill());
    };
  }, []);

  return (
    <main className="bg-[#02040a] selection:bg-violet-500/30 selection:text-white overflow-x-hidden">
      {/* Cinematic Boot Sequence - DISABLED PER USER REQUEST */}
      {/* {!isBooted && <NeuralBootLoader onComplete={() => setIsBooted(true)} />} */}

      {/* Aurora Atmospheric Layer */}
      <AuroraBackground className="fixed inset-0 z-0 pointer-events-none opacity-40" />

      {/* MAG_CURSOR */}
      <div 
        ref={cursorRef}
        className="fixed top-0 left-0 w-4 h-4 pointer-events-none z-[9999] mix-blend-difference hidden md:block"
      >
        <div className="absolute inset-[-10px] rounded-full border border-violet-500/30 animate-ping" />
        <div className="absolute inset-0 bg-white rounded-full scale-50" />
      </div>

      <motion.div 
        animate={{ opacity: isBooted ? 1 : 0, y: isBooted ? 0 : 50 }}
        transition={{ duration: 1.2, ease: "circOut" }}
        className="relative z-10"
      >
        <div id="COMMAND_CORE" className="relative">
          <HeroSection />
        </div>
        
        <div id="TERMINAL">
          <InstitutionalTerminal />
        </div>

        <div id="TERMINAL_CORE">
          <HomeTerminalSection />
        </div>

        {/* REGIME DETECTOR REMOVED PER USER REQUEST */}
        {/* <div id="COMMAND_HUB">
          <StrategicCommandHub />
        </div> */}

        <div id="REGIME_FLOW">
          <MacroRegimeScroller />
        </div>

        <InstitutionalSpecs />
        {/* AlphaForgeCTA removed per user request */}
        <Footer />
      </motion.div>

      {/* MISSION_PROGRESS_HUD (Tactical Navigation) */}
      <div className={`fixed left-12 bottom-12 z-[100] flex flex-col gap-6 pointer-events-none hidden xl:flex transition-opacity duration-1000 ${isBooted ? 'opacity-100' : 'opacity-0'}`}>
        <div className="flex flex-col gap-1.5 translate-y-4">
          <div className="flex items-center gap-4">
             <div className="w-1.5 h-1.5 rounded-full bg-violet-500 shadow-[0_0_15px_rgba(139,92,246,1)]" />
             <span className="text-[11px] font-mono text-white tracking-[0.4em] uppercase font-bold">{activeSection}</span>
          </div>
          <p className="text-[8px] font-mono text-gray-700 tracking-[0.3em] uppercase ml-5">ATLAS // Institutional Protocol Active</p>
        </div>
        
        <div className="flex flex-col gap-2 ml-5">
           {[
             "01 // COMMAND_CORE", 
             "02 // INSTITUTIONAL", 
             "03 // KERNEL",
             "04 // REGIMES"
           ].map((s, i) => (
             <div key={i} className={`h-[1px] w-8 rounded-full ${activeSection === s ? 'bg-violet-500 w-16' : 'bg-white/10'} transition-all duration-700`} />
           ))}
        </div>
      </div>
    </main>
  );
}
