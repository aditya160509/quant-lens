"use client";

import { useEffect } from "react";
import Link from "next/link";

export default function StudioError({ error, reset }) {
  useEffect(() => {
    console.error("Studio route render failure", error);
  }, [error]);

  return (
    <main className="studio-v2 lab-app">
      <section className="lab-error" role="alert">
        <strong>Studio could not load</strong>
        <span>{error?.message || "The workspace could not render safely."}</span>
        <div className="lab-actions-row">
          <button className="lab-button primary" type="button" onClick={reset}>Retry workspace</button>
          <Link className="lab-button secondary" href="/studio">Return to Algorithm Lab</Link>
        </div>
      </section>
    </main>
  );
}
