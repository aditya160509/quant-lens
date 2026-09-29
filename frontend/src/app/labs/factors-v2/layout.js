"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

const STRIP_FEATURES = [
  ["01", "VALUATION"],
  ["02", "EXPOSURE"],
  ["03", "ATTRIBUTION"],
  ["04", "REGIMES"],
  ["05", "DECAY"],
  ["06", "CROWDING"],
  ["07", "BACKTEST"],
  ["08", "COVARIANCE"],
  ["09", "CAPACITY"],
  ["10", "OPTIMIZER"],
  ["11", "STRESS TEST"],
  ["12", "FACTOR DNA"],
  ["13", "SIGNAL HEALTH"],
  ["14", "DDQ REPORT"],
];

function FactorsStrip() {
  const pathname = usePathname();
  const [activeCluster, setActiveCluster] = useState([]);

  useEffect(() => {
    function onCluster(event) {
      setActiveCluster(event.detail?.featureIds || []);
    }

    window.addEventListener("factors-cluster-active", onCluster);
    return () => window.removeEventListener("factors-cluster-active", onCluster);
  }, []);

  return (
    <nav className="factors-strip" aria-label="Factors V2 feature navigation">
      <div className="strip-label">FACTORS</div>
      <div className="strip-divider" />
      <div className="strip-pills">
        {STRIP_FEATURES.map(([id, label]) => {
          const active = pathname?.includes(`/feature-${id}`);
          const clusterActive = !active && pathname === "/labs/factors-v2" && activeCluster.includes(id);
          return (
            <Link className={`strip-pill ${active ? "active" : ""} ${clusterActive ? "cluster-active" : ""}`} href={`/labs/factors-v2/feature-${id}`} key={id}>
              <span>F{id}</span>
              {label}
            </Link>
          );
        })}
      </div>
      <div className="cmd-badge">⌘K</div>
    </nav>
  );
}

export default function FactorsV2Layout({ children }) {
  return (
    <div className="factors-v2-shell">
      {children}
      <FactorsStrip />
      <style jsx global>{`
        .factors-v2-shell {
          min-height: 100dvh;
          padding-bottom: 92px;
          background: #050506;
        }

        .factors-strip {
          position: fixed;
          left: 50%;
          bottom: 14px;
          transform: translateX(-50%);
          z-index: 80;
          width: min(1180px, calc(100vw - 32px));
          min-height: 62px;
          padding: 8px 10px;
          display: flex;
          align-items: center;
          gap: 8px;
          background: rgba(8, 8, 9, 0.9);
          border: 1px solid rgba(245, 158, 11, 0.22);
          border-radius: 22px;
          box-shadow: 0 22px 70px rgba(0,0,0,.58), inset 0 1px 0 rgba(255,255,255,.06);
          backdrop-filter: blur(22px) saturate(1.2);
        }

        .strip-label {
          height: 46px;
          min-width: 88px;
          border-radius: 15px;
          display: grid;
          place-items: center;
          color: #050506;
          background: #f5a20b;
          font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
          font-size: 11px;
          font-weight: 900;
          letter-spacing: 0.18em;
          text-transform: uppercase;
          white-space: nowrap;
        }

        .strip-divider {
          width: 1px;
          height: 32px;
          flex: 0 0 auto;
          background: rgba(245,158,11,.22);
          margin: 0 2px;
        }

        .strip-pills {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 6px;
          min-width: 0;
          overflow-x: auto;
          scrollbar-width: none;
          flex: 1 1 auto;
          padding: 0 2px;
        }

        .strip-pills::-webkit-scrollbar { display: none; }

        .strip-pill {
          height: 44px;
          min-width: 44px;
          max-width: 52px;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          gap: 6px;
          flex: 0 0 auto;
          border: 1px solid rgba(255,255,255,.08);
          border-radius: 15px;
          padding: 0 10px;
          color: #8f8a80;
          background: rgba(22,22,24,.76);
          text-decoration: none;
          font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
          font-size: 0;
          font-weight: 800;
          letter-spacing: 0.08em;
          overflow: hidden;
          transition: max-width 180ms cubic-bezier(.2,.9,.2,1), transform 180ms cubic-bezier(.2,.9,.2,1), background 150ms ease, border-color 150ms ease, color 150ms ease;
        }

        .strip-pill span {
          font-family: "JetBrains Mono", "IBM Plex Mono", Consolas, monospace;
          letter-spacing: 0;
          font-size: 11px;
          font-weight: 900;
        }

        .strip-pill:hover {
          max-width: 168px;
          color: #f8f5ec;
          background: rgba(34,34,36,.98);
          border-color: rgba(245,158,11,.28);
          transform: translateY(-8px) scale(1.08);
          box-shadow: 0 16px 42px rgba(0,0,0,.44);
          font-size: 10px;
        }

        .strip-pill.active {
          max-width: 168px;
          color: #050506;
          border-color: #f5a20b;
          background: #f5a20b;
          font-size: 10px;
          box-shadow: 0 16px 44px rgba(245,158,11,.24);
        }

        .strip-pill.cluster-active {
          color: #f8f5ec;
          border-color: rgba(245,158,11,.42);
          background: rgba(245,158,11,.12);
        }

        .cmd-badge {
          height: 44px;
          min-width: 54px;
          border-radius: 15px;
          border: 1px solid rgba(255,255,255,.09);
          background: rgba(22,22,24,.76);
          color: #8f8a80;
          display: grid;
          place-items: center;
          font-family: "JetBrains Mono", "IBM Plex Mono", Consolas, monospace;
          font-size: 12px;
          font-weight: 800;
        }

        @media (max-width: 720px) {
          .factors-strip {
            width: calc(100vw - 18px);
            bottom: 8px;
            padding: 8px;
          }

          .strip-label,
          .strip-divider,
          .cmd-badge {
            display: none;
          }
        }
      `}</style>
    </div>
  );
}
