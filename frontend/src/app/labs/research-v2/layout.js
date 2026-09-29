"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useResearchManifest } from "@/components/research-v2/api";

export default function ResearchV2Layout({ children }) {
  const pathname = usePathname();
  const { data: features = [] } = useResearchManifest();
  return <div className="research-v2-shell">
    {children}
    <nav className="research-v2-strip" aria-label="Research V2 feature navigation">
      <Link className="research-v2-mark" href="/labs/research-v2">R2</Link>
      <div className="research-v2-strip-items">{features.map((f) => <Link key={f.id} href={`/labs/research-v2/feature-${f.id}`} className={pathname?.includes(`feature-${f.id}`) ? "active" : ""} title={f.name}><span>F{f.id}</span><b>{f.name.split(" ")[0].toUpperCase()}</b></Link>)}</div>
    </nav>
    <style jsx global>{`
      .research-v2-shell{min-height:100dvh;padding-bottom:96px;background:#080907}.research-v2-strip{position:fixed;z-index:100;left:50%;bottom:15px;transform:translateX(-50%);width:min(1120px,calc(100vw - 30px));height:58px;padding:7px;display:flex;gap:7px;align-items:center;border:1px solid rgba(230,173,54,.28);border-radius:18px;background:rgba(8,9,7,.9);box-shadow:0 24px 80px rgba(0,0,0,.56),inset 0 1px 0 rgba(255,255,255,.06);backdrop-filter:blur(22px)}.research-v2-mark{height:43px;width:52px;display:grid;place-items:center;border-radius:12px;background:#e6ad36;color:#17130a;text-decoration:none;font:900 12px var(--font-ibm-plex-mono),monospace;letter-spacing:.1em}.research-v2-strip-items{min-width:0;flex:1;display:flex;align-items:center;justify-content:center;gap:5px;overflow-x:auto;scrollbar-width:none}.research-v2-strip-items::-webkit-scrollbar{display:none}.research-v2-strip-items a{flex:0 0 auto;max-width:46px;height:43px;padding:0 10px;display:inline-flex;align-items:center;justify-content:center;gap:7px;border:1px solid rgba(255,255,255,.075);border-radius:12px;background:rgba(21,24,18,.78);color:#77776e;text-decoration:none;overflow:hidden;font:800 0 var(--font-ibm-plex-mono),monospace;transition:max-width .18s ease,transform .18s ease,color .18s ease,border-color .18s ease,background .18s ease}.research-v2-strip-items a span{font-size:10px;color:#e6ad36}.research-v2-strip-items a b{font-size:10px;letter-spacing:.08em}.research-v2-strip-items a:hover{max-width:130px;transform:translateY(-7px) scale(1.07);color:#f1efe7;border-color:rgba(230,173,54,.42);background:#1a1b14;font-size:10px}.research-v2-strip-items a.active{max-width:130px;color:#17130a;border-color:#e6ad36;background:#e6ad36;font-size:10px;box-shadow:0 14px 34px rgba(230,173,54,.2)}.research-v2-strip-items a.active span{color:#17130a}@media(max-width:650px){.research-v2-strip{width:calc(100vw - 16px);bottom:8px}.research-v2-mark{width:43px}}
    `}</style>
  </div>;
}
