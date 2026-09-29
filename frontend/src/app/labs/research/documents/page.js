"use client";

import React, { useState, useCallback, useEffect } from 'react';
import dynamic from 'next/dynamic';
import Link from 'next/link';

const Plot = dynamic(() => import('react-plotly.js'), { ssr: false });

const API_BASE = 'http://127.0.0.1:8000/api/portfolio';

// =============================================================================
// DOCUMENT SUMMARIZER (Feature 70)
// SEC Filing Analysis with NLP Processing
// =============================================================================

const FILING_TYPES = ['10-K', '10-Q', '8-K', 'DEF 14A', '13F'];

const RISK_COLORS = {
  financial: { bg: 'bg-[var(--terminal-blue)]/10', border: 'border-[var(--terminal-blue)]/30', text: 'text-[var(--terminal-blue)]' },
  operational: { bg: 'bg-[var(--terminal-orange)]/10', border: 'border-[var(--terminal-orange)]/30', text: 'text-[var(--terminal-orange)]' },
  regulatory: { bg: 'bg-[var(--terminal-yellow)]/10', border: 'border-[var(--terminal-yellow)]/30', text: 'text-[var(--terminal-yellow)]' },
  strategic: { bg: 'bg-[var(--terminal-cyan)]/10', border: 'border-[var(--terminal-cyan)]/30', text: 'text-[var(--terminal-cyan)]' },
  reputational: { bg: 'bg-[var(--terminal-green)]/10', border: 'border-[var(--terminal-green)]/30', text: 'text-[var(--terminal-green)]' }
};

// Shared Components
const KPICard = ({ label, value, subtitle, color = 'cyan' }) => {
  const colorVar = `var(--terminal-${color})`;
  return (
    <div className="bg-[var(--terminal-dark)] border border-[var(--border)] rounded-lg p-4 font-mono">
      <div className="text-[10px] text-[var(--terminal-dim)] uppercase tracking-widest mb-1.5 font-bold">{label}</div>
      <div className="text-2xl font-black tracking-tighter" style={{ color: colorVar }}>{value}</div>
      {subtitle && <div className="text-[10px] text-[var(--terminal-dim)] mt-2 font-bold uppercase tracking-wider">{subtitle}</div>}
    </div>
  );
};

const LoadingSpinner = ({ text = 'Initializing deep extraction...' }) => (
  <div className="flex flex-col items-center justify-center p-12 font-mono">
    <div className="relative w-16 h-16 mb-6">
      <div className="absolute inset-0 border-t-2 border-[var(--terminal-cyan)] rounded-full animate-spin"></div>
      <div className="absolute inset-2 border-b-2 border-[var(--terminal-cyan)]/30 rounded-full animate-[spin_2s_linear_infinite]"></div>
    </div>
    <div className="text-[var(--terminal-dim)] uppercase tracking-[0.2em] animate-pulse text-xs font-bold">{text}</div>
  </div>
);

const RiskGauge = ({ category, score }) => {
  const colors = RISK_COLORS[category] || RISK_COLORS.financial;
  const percentage = Math.min(100, score);
  
  return (
    <div className={`${colors.bg} border ${colors.border} rounded-lg p-4 font-mono group hover:scale-[1.02] transition-transform`}>
      <div className="flex justify-between items-center mb-3">
        <span className={`text-[10px] font-black uppercase tracking-widest ${colors.text}`}>{category}</span>
        <span className={`text-xl font-black ${colors.text}`}>{score}</span>
      </div>
      <div className="w-full bg-[var(--terminal-darker)] rounded-full h-1.5 border border-[var(--border)]/10 p-[1px]">
        <div 
          className={`h-full rounded-full transition-all duration-1000 ${
            score > 70 ? 'bg-[var(--terminal-red)] shadow-[0_0_8px_rgba(239,68,68,0.5)]' : 
            score > 40 ? 'bg-[var(--terminal-orange)] shadow-[0_0_8px_rgba(249,115,22,0.5)]' : 
            'bg-[var(--terminal-green)] shadow-[0_0_8px_rgba(34,197,94,0.5)]'
          }`}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
};

// =============================================================================
// MAIN PAGE COMPONENT
// =============================================================================
export default function DocumentSummarizer() {
  const [ticker, setTicker] = useState('AAPL');
  const [filingType, setFilingType] = useState('10-K');
  const [loading, setLoading] = useState(false);
  const [document, setDocument] = useState(null);
  const [filings, setFilings] = useState([]);
  const [activeTab, setActiveTab] = useState('summary');
  const [error, setError] = useState(null);

  // Fetch available filings
  const fetchFilings = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/research/filings/${ticker}?filing_type=${filingType}&count=5`);
      const data = await res.json();
      setFilings(data.filings || []);
    } catch (e) {
      console.error('Failed to fetch filings:', e);
    }
  }, [ticker, filingType]);

  useEffect(() => {
    if (ticker.length >= 1) {
      fetchFilings();
    }
  }, [ticker, filingType, fetchFilings]);

  // Process filing
  const processDocument = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/research/fetch-filing/${ticker}?filing_type=${filingType}`);
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Failed to process filing');
      }
      const data = await res.json();
      setDocument(data);
    } catch (e) {
      setError(e.message);
    }
    setLoading(false);
  };

  const TABS = [
    { id: 'summary', label: 'Summary', icon: '📋' },
    { id: 'risks', label: 'Risk Analysis', icon: '⚠️' },
    { id: 'delta', label: 'Change Detection', icon: '🔄' },
    { id: 'metrics', label: 'Extracted Data', icon: '📊' },
    { id: 'full', label: 'Full Document', icon: '📄' }
  ];

  return (
    <div className="min-h-screen bg-[var(--background)] text-[var(--foreground)] font-mono">
      {/* Header with Back Link */}
      <div className="bg-[var(--terminal-darker)] border-b border-[var(--border)]">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center gap-4 mb-2 text-[10px] uppercase font-bold tracking-widest">
            <Link href="/labs" className="text-[var(--terminal-dim)] hover:text-[var(--foreground)] transition-colors">
              [LABS]
            </Link>
            <span className="text-[var(--border)]">/</span>
            <span className="text-[var(--terminal-dim)]">[RESEARCH]</span>
            <span className="text-[var(--border)]">/</span>
            <span className="text-[var(--terminal-cyan)] font-black">[DOCUMENTS]</span>
          </div>
          <h1 className="text-3xl font-black text-[var(--foreground)] uppercase tracking-tighter flex items-center gap-3">
             <span className="w-2 h-8 bg-[var(--terminal-cyan)] rounded-full"></span>
            Structural Document Extraction
          </h1>
          <p className="text-[var(--terminal-dim)] text-[11px] uppercase tracking-widest mt-1 font-bold">
            SEC AI Pipeline • NLP RISK HARVESTING • QUANTITATIVE FACTOR RECONSTRUCTION
          </p>
        </div>
      </div>

      {/* Sub-navigation */}
      <div className="bg-[var(--terminal-dark)] border-b border-[var(--border)]/50">
        <div className="max-w-7xl mx-auto px-6 flex gap-1">
          <Link 
            href="/labs/research/documents"
            className="px-6 py-4 text-[10px] font-black uppercase tracking-widest bg-[var(--terminal-darker)] text-[var(--terminal-cyan)] border-b-2 border-[var(--terminal-cyan)] transition-all"
          >
            📋 Analysis Engine
          </Link>
          <Link 
            href="/labs/research/sentiment"
            className="px-6 py-4 text-[10px] font-black uppercase tracking-widest text-[var(--terminal-dim)] hover:text-[var(--foreground)] hover:bg-[var(--terminal-darker)] transition-all"
          >
            💬 Sentiment Stream
          </Link>
        </div>
      </div>

      {/* Search Panel */}
      <div className="max-w-7xl mx-auto px-6 py-8">
        <div className="bg-[var(--terminal-dark)] border border-[var(--border)] rounded-xl p-6 mb-8 shadow-xl">
          <h3 className="text-xs font-black text-[var(--foreground)] mb-6 uppercase tracking-[0.2em] flex items-center gap-2">
            <span className="w-1.5 h-1.5 bg-[var(--terminal-cyan)] animate-pulse rounded-full"></span>
            Filing Acquisition Vector
          </h3>
          <div className="flex flex-wrap gap-6 items-end">
            <div className="flex-1 min-w-[150px]">
              <label className="text-[10px] text-[var(--terminal-dim)] block mb-2 uppercase font-bold tracking-widest text-shadow-sm">Equity Ticker</label>
              <input
                type="text"
                value={ticker}
                onChange={(e) => setTicker(e.target.value.toUpperCase())}
                className="w-full bg-[var(--terminal-darker)] border border-[var(--border)] rounded px-4 py-2.5 text-[var(--foreground)] uppercase font-black focus:border-[var(--terminal-cyan)] outline-none transition-all placeholder:text-[var(--terminal-dim)]/30"
                placeholder="AAPL"
              />
            </div>
            <div className="flex-1 min-w-[150px]">
              <label className="text-[10px] text-[var(--terminal-dim)] block mb-2 uppercase font-bold tracking-widest">SEC Filing Protocol</label>
              <select
                value={filingType}
                onChange={(e) => setFilingType(e.target.value)}
                className="w-full bg-[var(--terminal-darker)] border border-[var(--border)] rounded px-4 py-2.5 text-[var(--foreground)] font-bold focus:border-[var(--terminal-cyan)] outline-none appearance-none cursor-pointer hover:bg-[var(--terminal-dark)] transition-all"
              >
                {FILING_TYPES.map(type => (
                  <option key={type} value={type}>{type}</option>
                ))}
              </select>
            </div>
            <button
              onClick={processDocument}
              disabled={loading || !ticker}
              className="flex-[2] min-w-[200px] bg-[var(--terminal-cyan)] hover:opacity-90 disabled:bg-[var(--terminal-dim)]/20 text-[var(--terminal-black)] px-8 py-2.5 rounded font-black uppercase tracking-[0.2em] transition-all shadow-lg active:scale-[0.98]"
            >
              {loading ? 'EXECUTING PIPELINE...' : 'INITIATE ANALYSIS'}
            </button>
          </div>

          {/* Available Filings */}
          {filings.length > 0 && (
            <div className="mt-6 flex flex-wrap items-center gap-3 border-t border-[var(--border)]/10 pt-4">
              <span className="text-[9px] text-[var(--terminal-dim)] uppercase font-bold tracking-widest">Temporal Availability:</span>
              {filings.map((f, i) => (
                <span key={i} className="text-[10px] bg-[var(--terminal-darker)] px-2.5 py-1 rounded border border-[var(--border)]/10 text-[var(--foreground)] font-mono hover:border-[var(--terminal-cyan)] transition-colors cursor-default">
                  {f.date}
                </span>
              ))}
            </div>
          )}
        </div>

        {error && (
          <div className="bg-[var(--terminal-red)]/10 border border-[var(--terminal-red)]/30 rounded-xl p-5 text-[var(--terminal-red)] mb-8 flex items-center gap-4 animate-shake shadow-lg">
            <span className="text-xl">⚠️</span>
            <div className="flex flex-col">
              <span className="text-[10px] font-black uppercase tracking-widest text-[var(--terminal-red)]/70">Protocol Failure</span>
              <span className="text-xs font-bold uppercase tracking-tight">{error}</span>
            </div>
          </div>
        )}

        {loading && <LoadingSpinner text="Harvesting SEC dataset & executing neural summaries..." />}

        {/* Document Analysis */}
        {document && !loading && (
          <div className="animate-in fade-in slide-in-from-bottom-4 duration-700">
            {/* Company Info */}
            <div className="bg-[var(--terminal-dark)] border border-[var(--border)] rounded-xl p-6 mb-8 shadow-inner overflow-hidden relative">
              <div className="absolute top-0 right-0 w-64 h-64 bg-[var(--terminal-cyan)]/5 rounded-full blur-[80px] -mr-32 -mt-32"></div>
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 relative z-10">
                <div>
                  <div className="text-[10px] text-[var(--terminal-cyan)] uppercase font-black tracking-[0.2em] mb-1">Entity Identified</div>
                  <h2 className="text-3xl font-black text-[var(--foreground)] uppercase tracking-tighter">{document.company?.name || ticker}</h2>
                  <div className="flex items-center gap-3 text-[11px] text-[var(--terminal-dim)] mt-2 font-bold uppercase tracking-wider bg-[var(--terminal-darker)]/40 px-3 py-1 rounded-full border border-[var(--border)]/10 w-fit">
                    <span className="text-[var(--terminal-cyan)]">{document.filing?.type}</span>
                    <span className="opacity-20">|</span>
                    <span>TIMESTAMP: {document.filing?.date}</span>
                  </div>
                </div>
                <div className="flex gap-3">
                  {document.filing?.url && (
                    <a
                      href={document.filing.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="px-4 py-2 bg-[var(--terminal-darker)] border border-[var(--border)] rounded-lg text-[10px] font-black uppercase tracking-widest text-[var(--terminal-dim)] hover:text-[var(--terminal-cyan)] hover:border-[var(--terminal-cyan)] transition-all shadow-sm"
                    >
                      SEC SOURCE_DATA ↗
                    </a>
                  )}
                </div>
              </div>
            </div>

            {/* Tab Navigation */}
            <div className="bg-[var(--terminal-darker)] p-1.5 rounded-xl border border-[var(--border)]/30 mb-8 flex gap-1 overflow-x-auto no-scrollbar shadow-inner">
              {TABS.map(tab => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`px-5 py-3 text-[10px] font-black rounded-lg transition-all whitespace-nowrap uppercase tracking-widest flex items-center gap-2 group ${
                    activeTab === tab.id
                      ? 'bg-[var(--terminal-cyan)] text-[var(--terminal-black)] shadow-lg shadow-cyan-500/10'
                      : 'text-[var(--terminal-dim)] hover:text-[var(--foreground)] hover:bg-[var(--terminal-dark)]'
                  }`}
                >
                  <span className="text-lg opacity-80 group-hover:scale-110 transition-transform">{tab.icon}</span>
                  {tab.label}
                </button>
              ))}
            </div>

            {/* Tab Content */}
            <div className="min-h-[500px]">
              {activeTab === 'summary' && (
                <div className="space-y-8 animate-in fade-in slide-in-from-bottom-2 duration-500">
                  {/* Executive Summary */}
                  <div className="bg-[var(--terminal-dark)] border border-[var(--border)] rounded-xl p-8 relative overflow-hidden group">
                    <div className="absolute top-0 left-0 w-1 h-full bg-[var(--terminal-cyan)] opacity-20 group-hover:opacity-100 transition-opacity"></div>
                    <h3 className="text-xs font-black text-[var(--terminal-cyan)] uppercase tracking-[0.2em] mb-6 flex items-center gap-2">
                      <span className="w-1 h-3 bg-[var(--terminal-cyan)] rounded-full"></span>
                      Executive Intelligence Synthesis
                    </h3>
                    <p className="text-[var(--foreground)] leading-relaxed text-sm font-medium opacity-90 first-letter:text-3xl first-letter:font-black first-letter:text-[var(--terminal-cyan)] first-letter:mr-1">
                      {document.summary}
                    </p>
                  </div>

                  {/* Section Summaries */}
                  <div className="bg-[var(--terminal-dark)] border border-[var(--border)] rounded-xl p-8">
                    <h3 className="text-xs font-black text-[var(--foreground)] uppercase tracking-[0.2em] mb-8 border-b border-[var(--border)]/10 pb-4">
                      Segmental Deep Dives
                    </h3>
                    <div className="grid gap-6">
                      {Object.entries(document.sections || {}).map(([name, section]) => (
                        <details key={name} className="group border border-[var(--border)]/10 rounded-xl bg-[var(--terminal-darker)]/30 overflow-hidden">
                          <summary className="cursor-pointer p-4 hover:bg-[var(--terminal-darker)] transition-all flex items-center justify-between list-none">
                            <div className="flex items-center gap-3">
                               <div className="w-1.5 h-1.5 rounded-full bg-[var(--terminal-dim)] group-open:bg-[var(--terminal-cyan)] group-open:animate-pulse"></div>
                               <span className="font-black text-[var(--foreground)] uppercase text-[10px] tracking-widest">
                                {name.replace(/_/g, ' ')}
                              </span>
                            </div>
                            <span className="text-[var(--terminal-dim)] text-[9px] font-bold uppercase tracking-tighter bg-[var(--terminal-dark)] px-2 py-0.5 rounded border border-[var(--border)]/10">
                              {section.word_count?.toLocaleString()} WORDS_VEC
                            </span>
                          </summary>
                          <div className="p-6 bg-[var(--terminal-darker)]/60 text-[var(--foreground)]/80 text-sm leading-relaxed border-t border-[var(--border)]/5 font-medium">
                            {section.summary}
                          </div>
                        </details>
                      ))}
                    </div>
                  </div>

                  {/* Forward Looking Statements */}
                  {document.forward_looking?.length > 0 && (
                    <div className="bg-[var(--terminal-dark)] border border-[var(--border)] rounded-xl p-8">
                      <h3 className="text-xs font-black text-[var(--terminal-orange)] uppercase tracking-[0.2em] mb-8 flex items-center gap-2">
                        <span className="w-4 h-0.5 bg-[var(--terminal-orange)]"></span>
                        Projective Trajectory Indicators
                      </h3>
                      <div className="space-y-3">
                        {document.forward_looking.slice(0, 10).map((stmt, i) => (
                          <div key={i} className="flex gap-4 p-4 bg-[var(--terminal-darker)]/50 border border-[var(--border)]/5 rounded-xl group hover:border-[var(--terminal-orange)]/30 transition-all">
                            <div className={`shrink-0 w-20 py-1 rounded-full text-[9px] font-black uppercase tracking-widest text-center border self-start mt-0.5 ${
                              stmt.tone === 'positive' ? 'bg-[var(--terminal-green)]/10 text-[var(--terminal-green)] border-[var(--terminal-green)]/30' :
                              stmt.tone === 'cautious' ? 'bg-[var(--terminal-orange)]/10 text-[var(--terminal-orange)] border-[var(--terminal-orange)]/30' :
                              'bg-[var(--terminal-dim)]/10 text-[var(--terminal-dim)] border-[var(--terminal-dim)]/30'
                            }`}>
                              {stmt.tone}
                            </div>
                            <p className="text-[var(--foreground)]/80 text-sm font-medium leading-relaxed italic border-l-2 border-[var(--border)]/10 pl-4">{stmt.text}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {activeTab === 'risks' && (
                <div className="space-y-8 animate-in fade-in slide-in-from-bottom-2 duration-500">
                  {/* Risk Score Cards */}
                  <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                    {Object.entries(document.risk_scores || {}).map(([category, score]) => (
                      <RiskGauge key={category} category={category} score={score} />
                    ))}
                  </div>

                  {/* Risk List */}
                  <div className="bg-[var(--terminal-dark)] border border-[var(--border)] rounded-xl p-8">
                    <h3 className="text-xs font-black text-[var(--terminal-red)] uppercase tracking-[0.2em] mb-8 flex items-center gap-2">
                      <span className="w-1.5 h-4 bg-[var(--terminal-red)] rounded-full"></span>
                      Extracted Risk Factors Vector ({document.risks?.length || 0})
                    </h3>
                    <div className="space-y-4 max-h-[800px] overflow-y-auto pr-4 no-scrollbar">
                      {(document.risks || []).map((risk, i) => {
                        const colors = RISK_COLORS[risk.category] || RISK_COLORS.financial;
                        return (
                          <div key={i} className={`${colors.bg} border ${colors.border} rounded-xl p-6 transition-all hover:translate-x-1 group`}>
                            <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
                              <div className="flex items-center gap-3">
                                <span className={`px-3 py-1 rounded-full text-[9px] font-black uppercase tracking-widest ${colors.text} border ${colors.border}/20`}>
                                  {risk.category}
                                </span>
                                {risk.status === 'new' && (
                                  <span className="px-3 py-1 bg-[var(--terminal-orange)] text-[var(--terminal-black)] text-[9px] font-black rounded-full uppercase tracking-widest animate-pulse border border-orange-500/20">
                                    NEW_ENTRY
                                  </span>
                                )}
                              </div>
                              <div className="flex items-center gap-4 bg-[var(--terminal-darker)]/40 px-4 py-1.5 rounded-full border border-[var(--border)]/10">
                                <span className="text-[9px] text-[var(--terminal-dim)] font-bold uppercase tracking-widest">Intensity:</span>
                                <div className="flex gap-0.5">
                                  {[...Array(10)].map((_, idx) => (
                                    <div 
                                      key={idx} 
                                      className={`w-1.5 h-3 rounded-sm ${idx < risk.severity ? (risk.severity >= 7 ? 'bg-[var(--terminal-red)]' : risk.severity >= 4 ? 'bg-[var(--terminal-orange)]' : 'bg-[var(--terminal-green)]') : 'bg-[var(--terminal-dim)]/20'}`}
                                    />
                                  ))}
                                </div>
                                <span className={`text-sm font-black tracking-tighter ${
                                  risk.severity >= 7 ? 'text-[var(--terminal-red)]' :
                                  risk.severity >= 4 ? 'text-[var(--terminal-orange)]' : 'text-[var(--terminal-green)]'
                                }`}>
                                  {risk.severity}.0
                                </span>
                              </div>
                            </div>
                            <p className="text-[var(--foreground)] font-medium text-sm leading-relaxed mb-4">{risk.text}</p>
                            {risk.keywords?.length > 0 && (
                              <div className="flex flex-wrap gap-2 pt-4 border-t border-[var(--border)]/5">
                                {risk.keywords.map((kw, j) => (
                                  <span key={j} className="text-[9px] bg-[var(--terminal-darker)] text-[var(--terminal-dim)] px-2.5 py-1 rounded font-black uppercase tracking-widest border border-[var(--border)]/10 hover:border-[var(--terminal-cyan)] hover:text-[var(--terminal-cyan)] transition-colors cursor-default">
                                    #{kw}
                                  </span>
                                ))}
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>
              )}

              {activeTab === 'delta' && (
                <div className="space-y-8 animate-in fade-in slide-in-from-bottom-2 duration-500">
                  {document.delta ? (
                    <>
                      {/* Change Stats */}
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                        <KPICard 
                          label="Text Entropy Delta" 
                          value={`${document.delta.text_change_pct}%`}
                          color={document.delta.text_change_pct > 20 ? 'orange' : 'cyan'}
                        />
                        <KPICard 
                          label="Novel Content Chunks" 
                          value={document.delta.new_count}
                          color="green"
                        />
                        <KPICard 
                          label="Redacted Content Chunks" 
                          value={document.delta.removed_count}
                          color="red"
                        />
                        <KPICard 
                          label="Structural Mutated Nodes" 
                          value={document.delta.modified_count}
                          color="orange"
                        />
                      </div>

                      {/* New Content */}
                      {document.delta.new_content?.length > 0 && (
                        <div className="bg-[var(--terminal-green)]/5 border border-[var(--terminal-green)]/20 rounded-xl p-8">
                          <h3 className="text-xs font-black text-[var(--terminal-green)] mb-6 uppercase tracking-[0.2em] flex items-center gap-2">
                            <span className="text-lg">➕</span>
                            Injection Surface ({document.delta.new_content.length} MODES)
                          </h3>
                          <div className="space-y-3 max-h-80 overflow-y-auto pr-2 no-scrollbar font-mono">
                            {document.delta.new_content.map((text, i) => (
                              <div key={i} className="p-4 bg-[var(--terminal-darker)]/40 border-l-2 border-[var(--terminal-green)] text-[11px] leading-relaxed text-[var(--foreground)] font-medium">
                                {text}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Removed Content */}
                      {document.delta.removed_content?.length > 0 && (
                        <div className="bg-[var(--terminal-red)]/5 border border-[var(--terminal-red)]/20 rounded-xl p-8">
                          <h3 className="text-xs font-black text-[var(--terminal-red)] mb-6 uppercase tracking-[0.2em] flex items-center gap-2">
                            <span className="text-lg">➖</span>
                            Depletion Surface ({document.delta.removed_content.length} MODES)
                          </h3>
                          <div className="space-y-3 max-h-80 overflow-y-auto pr-2 no-scrollbar font-mono">
                            {document.delta.removed_content.map((text, i) => (
                              <div key={i} className="p-4 bg-[var(--terminal-darker)]/40 border-l-2 border-[var(--terminal-red)] text-[11px] leading-relaxed text-[var(--terminal-dim)] font-medium line-through decoration-[var(--terminal-red)]/50">
                                {text}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Modified Content */}
                      {document.delta.modified_content?.length > 0 && (
                        <div className="bg-[var(--terminal-orange)]/5 border border-[var(--terminal-orange)]/20 rounded-xl p-8">
                          <h3 className="text-xs font-black text-[var(--terminal-orange)] mb-6 uppercase tracking-[0.2em] flex items-center gap-2">
                            <span className="text-lg">✏️</span>
                            Mutation Analysis ({document.delta.modified_content.length} NODES)
                          </h3>
                          <div className="space-y-6 max-h-[500px] overflow-y-auto pr-2 no-scrollbar font-mono">
                            {document.delta.modified_content.map((item, i) => (
                              <div key={i} className="grid grid-cols-1 md:grid-cols-2 gap-px bg-[var(--border)]/10 rounded-xl overflow-hidden border border-[var(--border)]/10">
                                <div className="p-5 bg-[var(--terminal-darker)]/80">
                                  <div className="text-[9px] text-[var(--terminal-red)] font-black uppercase mb-3 px-2 py-0.5 bg-[var(--terminal-red)]/10 rounded w-fit">PRV_STATE</div>
                                  <div className="text-[11px] leading-relaxed text-[var(--terminal-dim)] italic">{item.previous}</div>
                                </div>
                                <div className="p-5 bg-[var(--terminal-darker)]/40 shadow-inner">
                                  <div className="text-[9px] text-[var(--terminal-green)] font-black uppercase mb-3 px-2 py-0.5 bg-[var(--terminal-green)]/10 rounded w-fit">CUR_STATE</div>
                                  <div className="text-[11px] leading-relaxed text-[var(--foreground)] font-bold">{item.current}</div>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </>
                  ) : (
                    <div className="bg-[var(--terminal-dark)] border border-[var(--border)] rounded-2xl p-24 text-center border-dashed">
                      <div className="text-6xl mb-8 opacity-20 grayscale">📊</div>
                      <h4 className="text-xl font-black text-[var(--foreground)] uppercase tracking-tighter mb-4">Historical Gap Detected</h4>
                      <p className="text-[var(--terminal-dim)] text-sm max-w-sm mx-auto font-bold uppercase tracking-widest leading-loose">
                        Comparative delta analysis requires a multi-filing temporal dataset. 
                        <br/>
                        <span className="text-[var(--terminal-cyan)]">[MIN_REQ: 2_DOCS]</span>
                      </p>
                    </div>
                  )}
                </div>
              )}

              {activeTab === 'metrics' && (
                <div className="space-y-8 animate-in fade-in slide-in-from-bottom-2 duration-500 font-mono">
                  {/* Extracted Metrics Table */}
                  <div className="bg-[var(--terminal-dark)] border border-[var(--border)] rounded-xl p-8 overflow-hidden shadow-2xl">
                    <h3 className="text-xs font-black text-[var(--foreground)] uppercase tracking-[0.2em] mb-8 border-b border-[var(--border)]/10 pb-4 flex items-center gap-2">
                       <span className="text-[var(--terminal-green)] text-lg">💰</span>
                       Extracted Factor Values (Float64)
                    </h3>
                    {Object.keys(document.extracted_metrics || {}).length > 0 ? (
                      <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                          <thead>
                            <tr className="text-[var(--terminal-dim)] text-left border-b border-[var(--border)]/10 uppercase text-[9px] font-black tracking-widest">
                              <th className="p-4">Structural Metric</th>
                              <th className="p-4 text-right">Sanitized Value</th>
                              <th className="p-4 text-right">Protocol Unit</th>
                              <th className="p-4 text-right opacity-50">Raw Source</th>
                            </tr>
                          </thead>
                          <tbody>
                            {Object.entries(document.extracted_metrics).map(([name, data]) => (
                              <tr key={name} className="border-b border-[var(--border)]/5 hover:bg-[var(--terminal-darker)] transition-all group">
                                <td className="p-4 text-[var(--foreground)] font-black uppercase text-[10px] tracking-tight group-hover:text-[var(--terminal-cyan)] transition-colors">
                                  {name.replace(/_/g, ' ')}
                                </td>
                                <td className="p-4 text-right text-[var(--terminal-green)] font-black text-sm">
                                  {typeof data.value === 'number' 
                                    ? data.value >= 1e9 
                                      ? `${(data.value / 1e9).toFixed(2)}B`
                                      : data.value >= 1e6
                                      ? `${(data.value / 1e6).toFixed(2)}M`
                                      : data.value.toLocaleString()
                                    : data.value}
                                </td>
                                <td className="p-4 text-right text-[var(--terminal-dim)] text-[10px] font-bold uppercase">{data.unit || 'NULL'}</td>
                                <td className="p-4 text-right text-[var(--terminal-dim)]/40 text-[9px] italic font-medium truncate max-w-[200px]">{data.raw || '-'}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <div className="text-center text-[var(--terminal-dim)] py-24 border border-dashed border-[var(--border)]/20 rounded-xl">
                        <div className="text-4xl mb-6 opacity-20">📂</div>
                        <div className="text-xs font-black uppercase tracking-widest">No Quantitative Vector Points Identified</div>
                      </div>
                    )}
                  </div>

                  {/* Export Options */}
                  <div className="flex gap-4 justify-end">
                    <button 
                      onClick={() => {
                        const json = JSON.stringify(document, null, 2);
                        const blob = new Blob([json], { type: 'application/json' });
                        const url = URL.createObjectURL(blob);
                        if (typeof window !== 'undefined') {
                           const a = window.document.createElement('a');
                           a.href = url;
                           a.download = `${ticker}_${filingType}_analysis.json`;
                           a.click();
                        }
                      }}
                      className="bg-[var(--terminal-dark)] border border-[var(--border)] hover:border-[var(--terminal-cyan)] hover:text-[var(--terminal-cyan)] text-[var(--terminal-dim)] px-6 py-3 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all shadow-lg flex items-center gap-2"
                    >
                      <span className="text-lg">📥</span>
                      Export Data Model (.JSON)
                    </button>
                  </div>
                </div>
              )}

              {activeTab === 'full' && (
                <div className="bg-[var(--terminal-dark)] border border-[var(--border)] rounded-xl p-8 animate-in fade-in slide-in-from-bottom-2 duration-500">
                  <h3 className="text-xs font-black text-[var(--foreground)] uppercase tracking-[0.2em] mb-8 border-b border-[var(--border)]/10 pb-4">
                     Structural Document Segments
                  </h3>
                  <div className="space-y-4">
                    {Object.entries(document.sections || {}).map(([name, section]) => (
                      <details key={name} className="group border border-[var(--border)]/10 rounded-xl bg-[var(--terminal-darker)]/30 overflow-hidden">
                        <summary className="cursor-pointer p-4 hover:bg-[var(--terminal-darker)] transition-all font-black text-[var(--foreground)] uppercase text-[10px] tracking-widest flex items-center gap-2">
                           <span className="text-[var(--terminal-cyan)] group-open:rotate-90 transition-transform">▶</span>
                          {name.replace(/_/g, ' ')} 
                          <span className="text-[var(--terminal-dim)] text-[9px] ml-2 bg-[var(--terminal-dark)] px-2 py-0.5 rounded">
                            ({section.word_count?.toLocaleString()} WORDS)
                          </span>
                        </summary>
                        <div className="p-6 bg-[var(--terminal-darker)]/60 text-[var(--foreground)]/80 text-[11px] font-mono leading-relaxed border-t border-[var(--border)]/5 max-h-[600px] overflow-y-auto whitespace-pre-wrap no-scrollbar">
                          {section.text?.substring(0, 10000)}
                          {section.text?.length > 10000 && '\n\n[PROTOCOL_RESTRICTION: BLOCK_TRUNCATED_AT_10K_CHARS]'}
                        </div>
                      </details>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {!document && !loading && (
          <div className="bg-[var(--terminal-dark)] border border-[var(--border)] rounded-2xl p-24 text-center border-dashed group hover:border-[var(--terminal-cyan)]/50 transition-all shadow-2xl relative overflow-hidden">
            <div className="absolute inset-0 bg-gradient-to-br from-[var(--terminal-cyan)]/2 to-transparent"></div>
            <div className="relative z-10">
              <div className="text-7xl mb-10 group-hover:scale-110 transition-transform duration-500 opacity-60 grayscale group-hover:grayscale-0 group-hover:opacity-100">📄</div>
              <h3 className="text-3xl font-black text-[var(--foreground)] mb-4 uppercase tracking-tighter">SEC DOCUMENT ANALYSIS ENGINE</h3>
              <p className="text-[var(--terminal-dim)] text-sm max-w-lg mx-auto font-bold uppercase tracking-[0.1em] leading-loose">
                Select an institutional entity and filing protocol to initiate the 
                <br/>
                <span className="text-[var(--terminal-cyan)]">[DEEP_SUMMARIZATION_PIPELINE]</span>.
              </p>
              <div className="mt-12 flex justify-center gap-8 opacity-20 group-hover:opacity-100 transition-opacity duration-1000">
                <div className="text-[9px] font-black uppercase tracking-widest text-[var(--terminal-dim)]">NLP_READY</div>
                <div className="text-[9px] font-black uppercase tracking-widest text-[var(--terminal-dim)]">SEC_EDGAR_SYNCED</div>
                <div className="text-[9px] font-black uppercase tracking-widest text-[var(--terminal-dim)]">NEURAL_CLUSTERING</div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
