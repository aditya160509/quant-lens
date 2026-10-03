"use client";

import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

export default function RouteTransition({ children }) {
  const pathname = usePathname();

  // Workspace modules keep one mounted shell across their routes
  const key = pathname?.startsWith("/research") ? "/research" : pathname;
  return <FadeIn key={key}>{children}</FadeIn>;
}

function FadeIn({ children }) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const id = window.setTimeout(() => setVisible(true), 80);
    return () => window.clearTimeout(id);
  }, []);

  return (
    <div style={{ opacity: visible ? 1 : 0, transition: "opacity 200ms ease-out" }}>
      {children}
    </div>
  );
}
