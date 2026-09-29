"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ML_V2_FEATURES } from "@/components/ml-v2/registry";

export default function MLV2Layout({ children }) {
  const pathname = usePathname();
  return (
    <div className="ml-v2-shell">
      {children}
      <nav className="ml-strip" aria-label="ML V2 feature navigation">
        <Link href="/labs/ml-v2" className="ml-strip-label">ML</Link>
        <div className="ml-strip-track">
          {ML_V2_FEATURES.map((feature) => {
            const active = pathname?.includes(`/feature-${feature.id}`);
            return (
              <Link href={`/labs/ml-v2/${feature.slug}`} key={feature.id} className={`ml-strip-pill ${active ? "active" : ""}`}>
                <span>M{feature.id}</span>
                <em>{feature.shortTitle || feature.title}</em>
              </Link>
            );
          })}
        </div>
        <div className="ml-strip-kbd">⌘K</div>
      </nav>
      <style jsx global>{`
        .ml-v2-shell { min-height: 100dvh; padding-bottom: 92px; background:#050505; color:#f7f0df; }
        .ml-strip { position:fixed; left:50%; bottom:14px; transform:translateX(-50%); z-index:95; width:min(1180px, calc(100vw - 32px)); min-height:62px; display:flex; align-items:center; gap:8px; padding:8px 10px; border:1px solid rgba(245,164,0,.28); border-radius:22px; background:rgba(5,5,5,.91); backdrop-filter:blur(22px) saturate(1.15); box-shadow:0 30px 90px rgba(0,0,0,.7), inset 0 1px 0 rgba(255,255,255,.06); }
        .ml-strip-label { height:46px; min-width:72px; display:grid; place-items:center; border-radius:15px; background:#f5a400; color:#050505; text-decoration:none; font-weight:1000; letter-spacing:.24em; }
        .ml-strip-track { flex:1; min-width:0; display:flex; align-items:center; justify-content:center; gap:6px; overflow-x:auto; scrollbar-width:none; }
        .ml-strip-track::-webkit-scrollbar { display:none; }
        .ml-strip-pill { height:44px; min-width:48px; max-width:56px; overflow:hidden; flex:0 0 auto; display:inline-flex; align-items:center; justify-content:center; gap:7px; padding:0 10px; border:1px solid rgba(255,255,255,.08); border-radius:15px; background:rgba(20,17,10,.78); color:#8e8270; text-decoration:none; transition:max-width 190ms cubic-bezier(.2,.9,.2,1), transform 190ms cubic-bezier(.2,.9,.2,1), background 150ms, border-color 150ms, color 150ms; }
        .ml-strip-pill span { font-family:"JetBrains Mono", monospace; font-size:11px; font-weight:950; }
        .ml-strip-pill em { font-style:normal; font-size:0; white-space:nowrap; font-weight:850; letter-spacing:.05em; }
        .ml-strip-pill:hover, .ml-strip-pill.active { max-width:210px; transform:translateY(-8px) scale(1.07); color:#f7f0df; border-color:rgba(245,164,0,.48); background:rgba(37,28,12,.98); box-shadow:0 16px 46px rgba(0,0,0,.5); }
        .ml-strip-pill:hover em, .ml-strip-pill.active em { font-size:10px; }
        .ml-strip-pill.active { background:#f5a400; color:#050505; border-color:#f5a400; box-shadow:0 18px 50px rgba(245,164,0,.24); }
        .ml-strip-kbd { height:44px; min-width:54px; display:grid; place-items:center; border:1px solid rgba(255,255,255,.09); border-radius:15px; background:rgba(20,17,10,.78); color:#8e8270; font-family:"JetBrains Mono", monospace; font-weight:900; }
      `}</style>
    </div>
  );
}
