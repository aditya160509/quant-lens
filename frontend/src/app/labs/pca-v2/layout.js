"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const PCA_STRIP_FEATURES = [
  ["01", "RMT"],
  ["02", "LOADINGS"],
  ["03", "RISK"],
  ["04", "OU"],
  ["05", "REGIME"],
  ["06", "OPT"],
  ["07", "VALID"],
  ["08", "CONTAGION"],
  ["09", "STRESS"],
  ["10", "X-ASSET"],
  ["11", "LIQUIDITY"],
];

function PcaStrip() {
  const pathname = usePathname();
  return (
    <nav className="pca-strip" aria-label="PCA V2 feature navigation">
      <Link href="/labs/pca-v2" className="pca-strip-label">PCA</Link>
      <div className="pca-strip-divider" />
      <div className="pca-strip-pills">
        {PCA_STRIP_FEATURES.map(([id, label]) => {
          const active = pathname?.includes(`/feature-${id}`);
          return (
            <Link className={`pca-strip-pill ${active ? "active" : ""}`} href={`/labs/pca-v2/feature-${id}`} key={id}>
              <span>P{id}</span>
              {label}
            </Link>
          );
        })}
      </div>
      <div className="pca-cmd-badge">⌘K</div>
    </nav>
  );
}

export default function PcaV2Layout({ children }) {
  return (
    <div className="pca-v2-shell">
      {children}
      <PcaStrip />
      <style jsx global>{`
        .pca-v2-shell {
          min-height: 100dvh;
          padding-bottom: 88px;
          background: #050505;
          color: #f7f1e6;
        }
        .pca-strip {
          position: fixed;
          left: 50%;
          bottom: 14px;
          transform: translateX(-50%);
          z-index: 90;
          width: min(1180px, calc(100vw - 32px));
          min-height: 62px;
          padding: 8px 10px;
          display: flex;
          align-items: center;
          gap: 8px;
          border: 1px solid rgba(245, 164, 0, 0.26);
          border-radius: 22px;
          background: rgba(5, 5, 5, 0.9);
          box-shadow: 0 24px 80px rgba(0, 0, 0, 0.62), inset 0 1px 0 rgba(255, 255, 255, 0.06);
          backdrop-filter: blur(22px) saturate(1.18);
        }
        .pca-strip-label {
          height: 46px;
          min-width: 76px;
          display: grid;
          place-items: center;
          border-radius: 15px;
          color: #050505;
          background: #f5a400;
          text-decoration: none;
          font-size: 11px;
          font-weight: 950;
          letter-spacing: 0.2em;
        }
        .pca-strip-divider {
          width: 1px;
          height: 32px;
          flex: 0 0 auto;
          background: rgba(245, 164, 0, 0.22);
        }
        .pca-strip-pills {
          flex: 1 1 auto;
          min-width: 0;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 6px;
          overflow-x: auto;
          scrollbar-width: none;
        }
        .pca-strip-pills::-webkit-scrollbar { display: none; }
        .pca-strip-pill {
          height: 44px;
          min-width: 46px;
          max-width: 56px;
          flex: 0 0 auto;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          gap: 7px;
          padding: 0 10px;
          border: 1px solid rgba(255, 255, 255, 0.08);
          border-radius: 15px;
          background: rgba(18, 18, 18, 0.86);
          color: #8f8777;
          text-decoration: none;
          overflow: hidden;
          font-size: 0;
          font-weight: 850;
          letter-spacing: 0.08em;
          transition: max-width 190ms cubic-bezier(.2,.9,.2,1), transform 190ms cubic-bezier(.2,.9,.2,1), background 150ms ease, border-color 150ms ease, color 150ms ease;
        }
        .pca-strip-pill span {
          font-family: "JetBrains Mono", "IBM Plex Mono", Consolas, monospace;
          font-size: 11px;
          font-weight: 950;
          letter-spacing: 0;
        }
        .pca-strip-pill:hover {
          max-width: 164px;
          color: #f7f1e6;
          background: rgba(31, 27, 20, 0.98);
          border-color: rgba(245, 164, 0, 0.36);
          transform: translateY(-8px) scale(1.08);
          box-shadow: 0 16px 42px rgba(0, 0, 0, 0.46);
          font-size: 10px;
        }
        .pca-strip-pill.active {
          max-width: 164px;
          color: #050505;
          background: #f5a400;
          border-color: #f5a400;
          font-size: 10px;
        }
        .pca-cmd-badge {
          height: 34px;
          min-width: 48px;
          display: grid;
          place-items: center;
          border: 1px solid rgba(255,255,255,.1);
          border-radius: 12px;
          color: #8f8777;
          background: rgba(18,18,18,.78);
          font: 800 11px "JetBrains Mono", monospace;
        }
      `}</style>
    </div>
  );
}
