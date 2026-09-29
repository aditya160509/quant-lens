"use client";

import React, { useEffect, useRef } from "react";
import { cn } from "@/lib/utils";

interface AuroraBackgroundProps extends React.HTMLProps<HTMLDivElement> {
  children?: React.ReactNode;
  showRadialGradient?: boolean;
}

export default function AuroraBackground({
  className,
  children,
  showRadialGradient = true,
  ...props
}: AuroraBackgroundProps) {
  return (
    <div
      className={cn(
        "relative flex flex-col h-[100vh] items-center justify-center bg-zinc-950 text-slate-950 transition-bg",
        className
      )}
      {...props}
    >
      <div className="absolute inset-0 overflow-hidden">
        <div
          className={cn(
            `
            [--white-gradient:linear-gradient(to_bottom,white,transparent)]
            [--dark-gradient:linear-gradient(to_bottom,black,transparent)]
            [--aurora:radial-gradient(ellipse_at_100%_0%,#3b82f6_0%,#1d4ed8_25%,#6366f1_50%,#8b5cf6_75%,#a855f7_100%)]
            [--aurora-secondary:radial-gradient(ellipse_at_0%_100%,#06b6d4_0%,#0891b2_25%,#10b981_50%,#14b8a6_75%,#2dd4bf_100%)]
            [background-image:var(--aurora),var(--aurora-secondary)]
            [background-size:200%,150%]
            [background-position:50%_50%,50%_50%]
            filter blur-[100px] invert dark:invert-0
            after:content-[""] after:absolute after:inset-0 after:[background-image:var(--white-gradient),var(--aurora)]
            after:dark:[background-image:var(--dark-gradient),var(--aurora)]
            after:[background-size:200%,100%]
            after:animate-aurora after:[background-attachment:fixed] mix-blend-difference
            pointer-events-none
            absolute -inset-[10px] opacity-20 will-change-transform`,
            showRadialGradient &&
              `[mask-image:radial-gradient(ellipse_at_100%_0%,black_10%,transparent_70%)]`
          )}
        ></div>
      </div>
      {children}
    </div>
  );
}
