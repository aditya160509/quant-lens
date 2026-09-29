"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { VolCommandPalette } from "@/components/VolCommandPalette";

const VOL_STRIP_FEATURES = [
  ["01", "ESTIMATORS"],
  ["02", "GARCH"],
  ["03", "HAR"],
  ["04", "REGIMES"],
  ["05", "VRP"],
  ["06", "SPILLOVER"],
  ["07", "DCC"],
  ["08", "STRESS"],
  ["09", "BUDGET"],
];

function VolatilityStrip() {
  const pathname = usePathname();
  const [activeCluster, setActiveCluster] = useState([]);

  useEffect(() => {
    function onCluster(event) {
      setActiveCluster(event.detail?.featureIds || []);
    }

    window.addEventListener("volatility-cluster-active", onCluster);
    return () => window.removeEventListener("volatility-cluster-active", onCluster);
  }, []);

  return (
    <nav className="volatility-strip" aria-label="Volatility V2 feature navigation">
      <Link href="/labs/volatility-v2" className="vol-strip-label">VOL</Link>
      <div className="vol-strip-divider" />
      <div className="vol-strip-pills">
        {VOL_STRIP_FEATURES.map(([id, label]) => {
          const active = pathname?.includes(`/feature-${id}`);
          const clusterActive = !active && pathname === "/labs/volatility-v2" && activeCluster.includes(id);
          return (
            <Link className={`vol-strip-pill ${active ? "active" : ""} ${clusterActive ? "cluster-active" : ""}`} href={`/labs/volatility-v2/feature-${id}`} key={id}>
              <span>V{id}</span>
              {label}
            </Link>
          );
        })}
      </div>
      <div className="vol-cmd-badge">⌘K</div>
    </nav>
  );
}

export default function VolatilityV2Layout({ children }) {
  return (
    <div className="volatility-v2-shell">
      {children}
      <VolatilityStrip />
      <VolCommandPalette />
      <style jsx global>{`
        .volatility-v2-shell {
          min-height: 100dvh;
          padding-bottom: 94px;
          background: #050505;
          color: #f5f2ea;
        }

        .volatility-strip {
          position: fixed;
          left: 50%;
          bottom: 14px;
          transform: translateX(-50%);
          z-index: 90;
          width: min(1040px, calc(100vw - 32px));
          min-height: 62px;
          padding: 8px 10px;
          display: flex;
          align-items: center;
          gap: 8px;
          border: 1px solid rgba(245, 164, 0, 0.24);
          border-radius: 22px;
          background: rgba(6, 6, 6, 0.9);
          box-shadow: 0 24px 80px rgba(0, 0, 0, 0.62), inset 0 1px 0 rgba(255, 255, 255, 0.06);
          backdrop-filter: blur(22px) saturate(1.18);
        }

        .vol-strip-label {
          height: 46px;
          min-width: 76px;
          display: grid;
          place-items: center;
          border-radius: 15px;
          color: #050505;
          background: #f5a400;
          text-decoration: none;
          font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
          font-size: 11px;
          font-weight: 950;
          letter-spacing: 0.2em;
        }

        .vol-strip-divider {
          width: 1px;
          height: 32px;
          flex: 0 0 auto;
          background: rgba(245, 164, 0, 0.22);
        }

        .vol-strip-pills {
          flex: 1 1 auto;
          min-width: 0;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 6px;
          overflow-x: auto;
          scrollbar-width: none;
        }

        .vol-strip-pills::-webkit-scrollbar { display: none; }

        .vol-strip-pill {
          height: 44px;
          min-width: 44px;
          max-width: 54px;
          flex: 0 0 auto;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          gap: 7px;
          padding: 0 10px;
          border: 1px solid rgba(255, 255, 255, 0.08);
          border-radius: 15px;
          background: rgba(19, 18, 16, 0.82);
          color: #8f8777;
          text-decoration: none;
          overflow: hidden;
          font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
          font-size: 0;
          font-weight: 850;
          letter-spacing: 0.08em;
          transition: max-width 190ms cubic-bezier(.2,.9,.2,1), transform 190ms cubic-bezier(.2,.9,.2,1), background 150ms ease, border-color 150ms ease, color 150ms ease;
        }

        .vol-strip-pill span {
          font-family: "JetBrains Mono", "IBM Plex Mono", Consolas, monospace;
          font-size: 11px;
          font-weight: 950;
          letter-spacing: 0;
        }

        .vol-strip-pill:hover {
          max-width: 154px;
          color: #f7f2e6;
          background: rgba(31, 27, 20, 0.98);
          border-color: rgba(245, 164, 0, 0.34);
          transform: translateY(-8px) scale(1.08);
          box-shadow: 0 16px 42px rgba(0, 0, 0, 0.46);
          font-size: 10px;
        }

        .vol-strip-pill.active {
          max-width: 154px;
          color: #050505;
          border-color: #f5a400;
          background: #f5a400;
          font-size: 10px;
          box-shadow: 0 16px 46px rgba(245, 164, 0, 0.28);
        }

        .vol-strip-pill.cluster-active {
          color: #f7f2e6;
          border-color: rgba(245, 164, 0, 0.46);
          background: rgba(245, 164, 0, 0.12);
        }

        .vol-cmd-badge {
          height: 44px;
          min-width: 54px;
          display: grid;
          place-items: center;
          border: 1px solid rgba(255, 255, 255, 0.09);
          border-radius: 15px;
          background: rgba(19, 18, 16, 0.82);
          color: #8f8777;
          font-family: "JetBrains Mono", "IBM Plex Mono", Consolas, monospace;
          font-size: 12px;
          font-weight: 850;
          cursor: pointer;
          transition: color 150ms ease, border-color 150ms ease, transform 150ms ease;
        }

        .vol-cmd-badge:hover {
          color: #f5a400;
          border-color: rgba(245, 164, 0, 0.42);
          transform: translateY(-5px);
        }

        .vol-cmdk-backdrop {
          position: fixed;
          inset: 0;
          z-index: 200;
          background: rgba(0, 0, 0, 0.72);
          backdrop-filter: blur(6px);
          animation: volCmdFade 120ms ease;
        }

        .vol-cmdk-shell {
          position: fixed;
          top: 18vh;
          left: 50%;
          transform: translateX(-50%);
          z-index: 201;
          width: min(680px, calc(100vw - 32px));
          border: 1px solid rgba(245, 164, 0, 0.28);
          border-radius: 16px;
          background: rgba(8, 7, 5, 0.97);
          box-shadow: 0 0 0 1px rgba(245, 164, 0, 0.06) inset, 0 40px 120px rgba(0, 0, 0, 0.8), 0 0 80px rgba(245, 164, 0, 0.04);
          overflow: hidden;
          animation: volCmdSlide 160ms cubic-bezier(0.16, 1, 0.3, 1);
        }

        @keyframes volCmdFade {
          from { opacity: 0; }
          to { opacity: 1; }
        }

        @keyframes volCmdSlide {
          from { opacity: 0; transform: translateX(-50%) translateY(-12px) scale(0.98); }
          to { opacity: 1; transform: translateX(-50%) translateY(0) scale(1); }
        }

        .vol-cmdk-input-wrap {
          height: 56px;
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 0 16px;
          border-bottom: 1px solid #1a1710;
        }

        .vol-cmdk-input-icon {
          color: #5a5448;
          font-family: "JetBrains Mono", "IBM Plex Mono", Consolas, monospace;
          font-size: 20px;
          line-height: 1;
        }

        .vol-cmdk-input {
          flex: 1;
          border: 0;
          outline: none;
          background: transparent;
          color: #f0ede4;
          caret-color: #f5a400;
          font-family: "JetBrains Mono", "IBM Plex Mono", Consolas, monospace;
          font-size: 14px;
          font-weight: 600;
        }

        .vol-cmdk-input::placeholder { color: #3a3530; }

        .vol-cmdk-esc,
        .vol-cmdk-footer kbd {
          border: 1px solid rgba(245, 164, 0, 0.16);
          border-radius: 5px;
          background: rgba(245, 164, 0, 0.06);
          color: #7a6d58;
          font-family: "JetBrains Mono", "IBM Plex Mono", Consolas, monospace;
          font-size: 9px;
          font-weight: 900;
          padding: 3px 6px;
        }

        .vol-cmdk-list {
          max-height: min(460px, 56vh);
          overflow-y: auto;
          padding: 10px;
        }

        .vol-cmdk-group [cmdk-group-heading] {
          padding: 12px 10px 7px;
          color: #f5a400;
          font-family: "JetBrains Mono", "IBM Plex Mono", Consolas, monospace;
          font-size: 10px;
          font-weight: 950;
          letter-spacing: 0.18em;
        }

        .vol-cmdk-item {
          min-height: 48px;
          display: grid;
          grid-template-columns: minmax(180px, 0.8fr) minmax(0, 1fr) 18px;
          align-items: center;
          gap: 12px;
          padding: 0 12px;
          border-radius: 10px;
          color: #9e9688;
          cursor: pointer;
          font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
          transition: background 90ms ease, color 90ms ease;
        }

        .vol-cmdk-item[aria-selected="true"] {
          background: linear-gradient(90deg, rgba(245, 164, 0, 0.16), rgba(245, 164, 0, 0.04));
          color: #f0ede4;
        }

        .vol-cmdk-item-label {
          color: inherit;
          font-size: 13px;
          font-weight: 850;
        }

        .vol-cmdk-item-sub {
          min-width: 0;
          overflow: hidden;
          color: #5a5448;
          font-family: "JetBrains Mono", "IBM Plex Mono", Consolas, monospace;
          font-size: 11px;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .vol-cmdk-item-arrow {
          color: #f5a400;
          opacity: 0.55;
        }

        .vol-cmdk-empty {
          padding: 28px 12px;
          color: #5a5448;
          font-family: "JetBrains Mono", "IBM Plex Mono", Consolas, monospace;
          font-size: 12px;
          text-align: center;
        }

        .vol-cmdk-footer {
          min-height: 42px;
          display: flex;
          align-items: center;
          gap: 12px;
          padding: 0 14px;
          border-top: 1px solid #1a1710;
          color: #5a5448;
          font-family: "JetBrains Mono", "IBM Plex Mono", Consolas, monospace;
          font-size: 10px;
        }

        .vol-cmdk-footer b {
          margin-left: auto;
          color: rgba(245, 164, 0, 0.55);
          font-size: 10px;
          letter-spacing: 0.12em;
        }

        @media (max-width: 720px) {
          .volatility-strip {
            width: calc(100vw - 18px);
            bottom: 8px;
            padding: 8px;
          }

          .vol-strip-label,
          .vol-strip-divider,
          .vol-cmd-badge {
            display: none;
          }
        }
      `}</style>
    </div>
  );
}
