"use client";
import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowUpRight, Network, ShieldCheck, Target } from "lucide-react";
import { PORTFOLIO_V2_FEATURES } from "@/components/portfolio-v2/registry";

const groups = [
  { label: "ALLOCATE", ids: ["01", "10", "13"], icon: Target },
  { label: "VALIDATE", ids: ["02", "03", "09"], icon: ShieldCheck },
  { label: "CONTROL", ids: ["04", "06", "07", "11"], icon: Network },
  { label: "SYSTEMIC", ids: ["05", "08", "12"], icon: Network },
];
export default function PortfolioV2Page() {
  return (
    <main className="pv2">
      <style jsx global>
        {css}
      </style>
      <nav>
        <b>PORTFOLIO // V2</b>
        <span>13 INSTITUTIONAL ENGINES</span>
      </nav>
      <header>
        <p>CAPITAL SYSTEMS LABORATORY</p>
        <h1>Build portfolios that survive contact with reality.</h1>
        <span>
          Construction, attribution, stress, liquidity, execution, systemic
          contagion and multi-strategy control in one evidence-first research
          surface.
        </span>
      </header>
      {groups.map((group, g) => {
        const Icon = group.icon;
        return (
          <section key={group.label}>
            <div className="group-title">
              <Icon />
              <b>{group.label}</b>
              <i>{String(g + 1).padStart(2, "0")}</i>
            </div>
            <div className="cards">
              {PORTFOLIO_V2_FEATURES.filter((f) =>
                group.ids.includes(f.id),
              ).map((f, i) => (
                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: i * 0.06 }}
                  key={f.id}
                >
                  <Link href={`/labs/portfolio-v2/${f.slug}`}>
                    <small>ENGINE {f.id}</small>
                    <h2>{f.title}</h2>
                    <p>{f.description}</p>
                    <span>
                      OPEN WORKBENCH <ArrowUpRight size={14} />
                    </span>
                  </Link>
                </motion.div>
              ))}
            </div>
          </section>
        );
      })}
    </main>
  );
}
const css = `.pv2{min-height:100vh;background:radial-gradient(circle at 72% -8%,rgba(167,244,50,.12),transparent 35%),#050706;color:#edf5ed;padding:0 5vw 100px;font-family:"IBM Plex Sans",sans-serif}.pv2 nav{height:58px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid #253229}.pv2 nav b,.pv2 nav span,.pv2 header p{color:#a7f432;font:900 10px "JetBrains Mono",monospace;letter-spacing:.2em}.pv2 nav span{color:#849189}.pv2 header{padding:9vw 0 8vw;max-width:1100px}.pv2 h1{font-family:"Archivo Black",sans-serif;font-size:clamp(48px,8vw,120px);line-height:.87;letter-spacing:-.055em;margin:18px 0 26px}.pv2 header>span{max-width:780px;color:#849189;font-size:20px;line-height:1.65;display:block}.pv2 section{border-top:1px solid #253229;padding:34px 0 70px}.group-title{display:flex;align-items:center;gap:10px;color:#a7f432}.group-title b{font:900 11px "JetBrains Mono",monospace;letter-spacing:.18em}.group-title i{margin-left:auto;color:#849189;font-style:normal}.cards{margin-top:22px;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.cards a{min-height:310px;padding:24px;border:1px solid #253229;background:linear-gradient(160deg,#101611,#080b09);color:#edf5ed;text-decoration:none;display:flex;flex-direction:column;transition:.2s}.cards a:hover{border-color:#a7f432;transform:translateY(-5px);box-shadow:0 30px 80px rgba(0,0,0,.35)}.cards small{color:#a7f432;font:900 10px "JetBrains Mono",monospace;letter-spacing:.16em}.cards h2{font-size:26px;line-height:1.05;margin:28px 0 16px}.cards p{color:#849189;line-height:1.6}.cards span{margin-top:auto;color:#a7f432;font:900 10px "JetBrains Mono",monospace;display:flex;align-items:center;gap:8px}@media(max-width:850px){.cards{grid-template-columns:1fr}.pv2 h1{font-size:54px}}`;
