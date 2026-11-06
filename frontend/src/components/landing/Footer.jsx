"use client";

import React from "react";
import Link from "next/link";
import { 
  Zap, 
  Github, 
  Twitter, 
  Linkedin, 
  Mail,
  ArrowUp
} from "lucide-react";

const footerLinks = {
  Platform: [
    { name: "Trade", href: "/trade" },
    { name: "Labs", href: "/labs" },
    { name: "Portfolio", href: "/labs/portfolio-v2" },
  ],
  Research: [
    { name: "Factor Analysis", href: "/labs/factors-v2" },
    { name: "Volatility", href: "/labs/volatility-v2" },
    { name: "ML Models", href: "/ml" },
  ],
  Company: [
    { name: "About", href: "#" },
    { name: "Careers", href: "#" },
    { name: "Contact", href: "#" },
  ],
  Legal: [
    { name: "Privacy", href: "#" },
    { name: "Terms", href: "#" },
    { name: "Security", href: "#" },
  ],
};

const socialLinks = [
  { Icon: Github, href: "#", label: "GitHub" },
  { Icon: Twitter, href: "#", label: "Twitter" },
  { Icon: Linkedin, href: "#", label: "LinkedIn" },
  { Icon: Mail, href: "#", label: "Email" },
];

export default function Footer() {
  const scrollToTop = () => {
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  return (
    <footer className="relative border-t border-white/10 bg-[#030510]">
      {/* Main Footer */}
      <div className="max-w-7xl mx-auto px-6 py-16">
        <div className="grid grid-cols-2 md:grid-cols-6 gap-8 lg:gap-12">
          {/* Brand */}
          <div className="col-span-2">
            <Link href="/" className="flex items-center gap-3 mb-6">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-600 to-indigo-600 
                            flex items-center justify-center shadow-[0_0_15px_rgba(139,92,246,0.3)]">
                <Zap className="w-5 h-5 text-white" />
              </div>
              <span className="text-xl font-bold uppercase tracking-tighter">
                <span className="text-transparent bg-clip-text bg-gradient-to-r from-violet-400 to-indigo-500">
                  ATL
                </span>
                <span className="text-white">AS</span>
              </span>
            </Link>
            <p className="text-gray-500 text-sm mb-6 max-w-xs leading-relaxed">
              Institutional-grade quantitative intelligence terminal. 
              Built for performance. Engineered for alpha.
            </p>
            <div className="flex items-center gap-3">
              {socialLinks.map((social) => {
                const Icon = social.Icon;
                return (
                  <a
                    key={social.label}
                    href={social.href}
                    aria-label={social.label}
                    className="w-10 h-10 rounded-lg bg-white/5 border border-white/10
                             flex items-center justify-center text-gray-400
                             hover:bg-violet-500/10 hover:text-violet-400 hover:border-violet-500/30
                             transition-all duration-300 transform hover:-translate-y-1"
                  >
                    <Icon className="w-4 h-4" />
                  </a>
                );
              })}
            </div>
          </div>

          {/* Links */}
          {Object.entries(footerLinks).map(([category, links]) => (
            <div key={category}>
              <h3 className="text-xs font-mono text-gray-500 uppercase tracking-widest mb-6">{category}</h3>
              <ul className="space-y-3">
                {links.map((link) => (
                  <li key={link.name}>
                    <Link
                      href={link.href}
                      className="text-gray-500 hover:text-violet-400 transition-colors text-sm"
                    >
                      {link.name}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>

      {/* Bottom Bar */}
      <div className="border-t border-white/5 bg-black/20">
        <div className="max-w-7xl mx-auto px-6 py-8 flex flex-col md:flex-row items-center justify-between gap-6">
          <div className="text-gray-600 text-[10px] font-mono uppercase tracking-widest">
            © 2026 ATLAS. Kernel Version 2.0.4-STABLE
          </div>
          
          <div className="flex items-center gap-8 text-[10px] font-mono uppercase tracking-widest text-gray-600">
            <div className="flex items-center gap-2">
              <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse shadow-[0_0_8px_rgba(16,185,129,0.5)]" />
              <span className="text-emerald-500/80">Systems: Operational</span>
            </div>
            
            <button
              onClick={scrollToTop}
              className="flex items-center gap-2 hover:text-white transition-colors group"
            >
              <span>Back to surface</span>
              <ArrowUp className="w-3.5 h-3.5 group-hover:-translate-y-1 transition-transform" />
            </button>
          </div>
        </div>
      </div>
    </footer>
  );
}
