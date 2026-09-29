"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const FEATURES = [
  ["01", "CORE"],
  ["02", "FORMULA"],
  ["03", "COMPOSITE"],
  ["04", "ACADEMIC"],
  ["05", "BACKTEST"],
  ["06", "ALERTS"],
  ["07", "VALUE"],
  ["08", "EXPORT"],
];

export default function ScreenerV2Layout({ children }) {
  const pathname = usePathname();
  return (
    <div className="screener-v2-route">
      {children}
      <nav className="sv2-strip" aria-label="Screener V2 navigation">
        <Link href="/labs/screener-v2" className="sv2-strip-label">SCREEN</Link>
        <div className="sv2-strip-pills">
          {FEATURES.map(([id, label]) => {
            const active = pathname?.includes(`/feature-${id}`);
            return <Link key={id} href={`/labs/screener-v2/feature-${id}`} className={active ? "active" : ""}><span>S{id}</span>{label}</Link>;
          })}
        </div>
        <div className="sv2-strip-kbd">⌘K</div>
      </nav>
      <style jsx global>{`
        .screener-v2-route{min-height:100dvh;background:#050505;color:#f5f2ea;padding-bottom:92px}
        .sv2-strip{position:fixed;left:50%;bottom:14px;transform:translateX(-50%);z-index:80;width:min(980px,calc(100vw - 28px));height:62px;display:flex;align-items:center;gap:8px;padding:8px 10px;border:1px solid rgba(245,164,0,.28);border-radius:22px;background:rgba(5,5,5,.9);box-shadow:0 24px 80px rgba(0,0,0,.6),inset 0 1px 0 rgba(255,255,255,.06);backdrop-filter:blur(22px)}
        .sv2-strip-label{height:46px;min-width:86px;display:grid;place-items:center;border-radius:15px;background:#f5a400;color:#050505;text-decoration:none;font-size:11px;font-weight:950;letter-spacing:.18em}
        .sv2-strip-pills{flex:1;display:flex;gap:6px;overflow-x:auto;scrollbar-width:none}.sv2-strip-pills::-webkit-scrollbar{display:none}
        .sv2-strip-pills a{height:44px;max-width:54px;min-width:48px;display:inline-flex;align-items:center;justify-content:center;gap:7px;overflow:hidden;padding:0 10px;border:1px solid rgba(255,255,255,.08);border-radius:15px;background:rgba(19,18,16,.82);color:#8f8777;text-decoration:none;font-size:0;font-weight:900;transition:max-width 180ms cubic-bezier(.2,.9,.2,1),transform 180ms cubic-bezier(.2,.9,.2,1),background 140ms,border-color 140ms,color 140ms}
        .sv2-strip-pills a span{font-family:"JetBrains Mono",monospace;font-size:11px;color:inherit}
        .sv2-strip-pills a:hover,.sv2-strip-pills a.active{max-width:142px;transform:translateY(-8px) scale(1.08);background:rgba(31,27,20,.98);border-color:rgba(245,164,0,.42);color:#f5f2ea;font-size:10px;box-shadow:0 16px 42px rgba(0,0,0,.46)}
        .sv2-strip-pills a.active{color:#f5a400}
        .sv2-strip-kbd{height:34px;min-width:48px;display:grid;place-items:center;border:1px solid #302613;border-radius:12px;color:#6e665b;font-family:"JetBrains Mono",monospace;background:#090909}
      `}</style>
    </div>
  );
}
