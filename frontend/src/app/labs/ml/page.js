'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { 
  Database, Settings, Target, BarChart2, Users, Search, 
  Activity, AlertTriangle, Layers, Link2, GitBranch, 
  Map, CheckCircle, Briefcase, ArrowRight, Play
} from 'lucide-react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

// ML Module Definitions - All 15 Modules organized by workflow steps
const ML_MODULES = [
  // Step 1 - Data & Feature Engineering
  {
    id: 'data',
    name: 'Data',
    description: 'Signal Outcome Dataset Builder',
    Icon: Database,
    path: '/labs/ml/data',
    step: 1,
    status: 'active',
    capabilities: ['Label generation', 'Dataset versioning', 'Leakage detection']
  },
  {
    id: 'features',
    name: 'Features',
    description: 'Feature Engineering & Validation',
    Icon: Settings,
    path: '/labs/ml/features',
    step: 1,
    status: 'active',
    capabilities: ['Lag windows', 'Normalization', 'Correlation analysis']
  },
  // Step 2 - Model Training
  {
    id: 'supervised',
    name: 'Supervised',
    description: 'Signal Success Probability',
    Icon: Target,
    path: '/labs/ml/supervised',
    step: 2,
    status: 'active',
    capabilities: ['Logistic/RF/XGBoost/LightGBM', 'Time-series CV', 'Probability estimation']
  },
  {
    id: 'conditional',
    name: 'Conditional',
    description: 'Conditional Performance',
    Icon: BarChart2,
    path: '/labs/ml/conditional',
    step: 2,
    status: 'active',
    capabilities: ['Performance by regime', 'Signal fingerprints', 'Best/worst conditions']
  },
  {
    id: 'ensemble',
    name: 'Ensemble',
    description: 'Model Consensus',
    Icon: Users,
    path: '/labs/ml/ensemble',
    step: 2,
    status: 'active',
    capabilities: ['Multi-model consensus', 'Disagreement scoring', 'Dynamic weighting']
  },
  // Step 3 - Explainability & Monitoring
  {
    id: 'explainability',
    name: 'Explainability',
    description: 'Feature Attribution (SHAP)',
    Icon: Search,
    path: '/labs/ml/explainability',
    step: 3,
    status: 'active',
    capabilities: ['Global importance', 'Per-signal attribution', 'Waterfall plots']
  },
  {
    id: 'monitoring',
    name: 'Monitoring',
    description: 'Model Drift & Decay',
    Icon: Activity,
    path: '/labs/ml/monitoring',
    step: 3,
    status: 'active',
    capabilities: ['Rolling accuracy', 'PSI drift detection', 'Alert system']
  },
  {
    id: 'errors',
    name: 'Errors',
    description: 'Failure Regime Analyzer',
    Icon: AlertTriangle,
    path: '/labs/ml/errors',
    step: 3,
    status: 'active',
    capabilities: ['Error clustering', 'High-risk conditions', 'Risk flags']
  },
  // Step 4 - Structure Discovery
  {
    id: 'regimes',
    name: 'Regimes',
    description: 'Market Regime Discovery',
    Icon: Layers,
    path: '/labs/ml/regimes',
    step: 4,
    status: 'active',
    capabilities: ['K-Means/Hierarchical', 'Transition matrix', 'Regime prediction']
  },
  {
    id: 'clustering',
    name: 'Clustering',
    description: 'Asset Similarity',
    Icon: Link2,
    path: '/labs/ml/clustering',
    step: 4,
    status: 'active',
    capabilities: ['Asset dendrograms', 'Redundancy scores', 'Diversification']
  },
  {
    id: 'strategies',
    name: 'Strategies',
    description: 'Strategy Overlap',
    Icon: GitBranch,
    path: '/labs/ml/strategies',
    step: 4,
    status: 'active',
    capabilities: ['Correlation matrix', 'Crowding detector', 'Allocation suggestions']
  },
  // Step 5 - Visualization
  {
    id: 'embedding',
    name: 'Embedding',
    description: 'Feature Space Visualization',
    Icon: Map,
    path: '/labs/ml/embedding',
    step: 5,
    status: 'active',
    capabilities: ['UMAP/t-SNE', '2D/3D visualization', 'Separation metrics']
  },
  {
    id: 'regime-quality',
    name: 'Quality',
    description: 'Regime Separation',
    Icon: CheckCircle,
    path: '/labs/ml/regime-quality',
    step: 5,
    status: 'active',
    capabilities: ['Silhouette scores', 'Overlap detection', 'Merge recommendations']
  },
  // Step 6 - Decision Support
  {
    id: 'summary',
    name: 'Summary',
    description: 'Signal Quality Scorecard',
    Icon: Briefcase,
    path: '/labs/ml/summary',
    step: 6,
    status: 'active',
    capabilities: ['Composite scores', 'Tier assignments', 'Ranking']
  },
  {
    id: 'sizing',
    name: 'Sizing',
    description: 'ML-Driven Position Advisor',
    Icon: Briefcase,
    path: '/portfolio/risk',
    step: 6,
    status: 'active',
    capabilities: ['Kelly criterion', 'Risk constraints', 'Stress testing']
  }
];

// Workflow steps configuration
const WORKFLOW_STEPS = [
  { step: 1, name: 'Data Preparation', description: 'Build datasets and engineer features' },
  { step: 2, name: 'Model Training', description: 'Train supervised and ensemble models' },
  { step: 3, name: 'Analysis', description: 'Explain predictions and monitor drift' },
  { step: 4, name: 'Discovery', description: 'Find regimes and asset clusters' },
  { step: 5, name: 'Visualization', description: 'Visualize feature space' },
  { step: 6, name: 'Decision', description: 'Score signals and size positions' },
];

export default function MLLabsPage() {
  const [healthStatus, setHealthStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeStep, setActiveStep] = useState(null);

  useEffect(() => {
    fetchHealthStatus();
  }, []);

  const fetchHealthStatus = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/ml/health`);
      const data = await res.json();
      setHealthStatus(data);
    } catch (error) {
      console.error('Failed to fetch ML health:', error);
    } finally {
      setLoading(false);
    }
  };

  const filteredModules = activeStep 
    ? ML_MODULES.filter(m => m.step === activeStep) 
    : ML_MODULES;

  return (
    <div className="min-h-screen bg-terminal-dark text-terminal-text p-6">
      {/* Header */}
      <div className="max-w-7xl mx-auto mb-8">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-terminal-yellow">
              ML Infrastructure
            </h1>
            <p className="text-terminal-dim mt-1 text-sm font-mono">
              15-Module Machine Learning Pipeline
            </p>
          </div>
          
          {/* Status Indicators */}
          <div className="flex items-center gap-3">
            <div className={`px-3 py-1.5 rounded text-xs font-mono ${healthStatus?.status === 'healthy' ? 'bg-terminal-green/20 border border-terminal-green/30 text-terminal-green' : 'bg-terminal-yellow/20 border border-terminal-yellow/30 text-terminal-yellow'}`}>
              {healthStatus?.status === 'healthy' ? 'System Ready' : 'Loading...'}
            </div>
            <div className={`px-3 py-1.5 rounded text-xs font-mono ${healthStatus?.model_trained ? 'bg-terminal-cyan/20 border border-terminal-cyan/30 text-terminal-cyan' : 'bg-terminal-gray/20 border border-terminal-gray/30 text-terminal-dim'}`}>
              {healthStatus?.model_trained ? 'Model Trained' : 'No Model'}
            </div>
          </div>
        </div>

        {/* Workflow Steps - Horizontal */}
        <div className="bg-terminal-black border border-terminal-gray rounded p-4 mb-6">
          <div className="text-xs text-terminal-dim uppercase tracking-wide mb-3">Workflow</div>
          <div className="flex items-center gap-2 overflow-x-auto">
            <button
              onClick={() => setActiveStep(null)}
              className={`px-4 py-2 rounded font-mono text-xs whitespace-nowrap transition-all ${
                activeStep === null 
                  ? 'bg-terminal-yellow text-terminal-black' 
                  : 'bg-terminal-dark border border-terminal-gray text-terminal-dim hover:text-terminal-text'
              }`}
            >
              All Modules
            </button>
            {WORKFLOW_STEPS.map((ws, i) => (
              <div key={ws.step} className="flex items-center gap-2">
                {i > 0 && <ArrowRight className="w-4 h-4 text-terminal-gray" />}
                <button
                  onClick={() => setActiveStep(ws.step)}
                  className={`px-4 py-2 rounded font-mono text-xs whitespace-nowrap transition-all ${
                    activeStep === ws.step 
                      ? 'bg-terminal-cyan text-terminal-black' 
                      : 'bg-terminal-dark border border-terminal-gray text-terminal-dim hover:text-terminal-text hover:border-terminal-cyan/50'
                  }`}
                >
                  <div className="font-bold">{ws.step}. {ws.name}</div>
                </button>
              </div>
            ))}
          </div>
        </div>

        {/* Quick Stats */}
        <div className="grid grid-cols-4 gap-4 mb-6">
          <div className="bg-terminal-black border border-terminal-gray rounded p-4">
            <div className="text-2xl font-mono font-bold text-terminal-cyan">15</div>
            <div className="text-xs text-terminal-dim">Modules</div>
          </div>
          <div className="bg-terminal-black border border-terminal-gray rounded p-4">
            <div className="text-2xl font-mono font-bold text-terminal-green">40+</div>
            <div className="text-xs text-terminal-dim">API Endpoints</div>
          </div>
          <div className="bg-terminal-black border border-terminal-gray rounded p-4">
            <div className="text-2xl font-mono font-bold text-terminal-yellow">
              {healthStatus?.dataset_cached ? 'Ready' : '--'}
            </div>
            <div className="text-xs text-terminal-dim">Dataset</div>
          </div>
          <div className="bg-terminal-black border border-terminal-gray rounded p-4">
            <div className="text-2xl font-mono font-bold text-terminal-text">
              {healthStatus?.monitor_initialized ? 'Active' : '--'}
            </div>
            <div className="text-xs text-terminal-dim">Monitor</div>
          </div>
        </div>
      </div>

      {/* Module Grid */}
      <div className="max-w-7xl mx-auto">
        {activeStep && (
          <div className="mb-4 text-sm text-terminal-dim font-mono">
            Step {activeStep}: {WORKFLOW_STEPS.find(w => w.step === activeStep)?.description}
          </div>
        )}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-3">
          {filteredModules.map((module) => (
            <Link
              key={module.id}
              href={module.path}
              className="group block"
            >
              <div className="bg-terminal-black border border-terminal-gray rounded p-4 hover:border-terminal-cyan/50 transition-all duration-200 h-full">
                <div className="flex items-center gap-3 mb-2">
                  <div className="w-8 h-8 rounded bg-terminal-dark flex items-center justify-center text-terminal-cyan">
                    <module.Icon className="w-4 h-4" />
                  </div>
                  <div>
                    <h3 className="font-mono text-sm font-bold text-terminal-text group-hover:text-terminal-cyan transition-colors">
                      {module.name}
                    </h3>
                  </div>
                </div>
                
                <p className="text-xs text-terminal-dim mb-3 leading-relaxed">
                  {module.description}
                </p>
                
                <div className="flex flex-wrap gap-1">
                  {module.capabilities.slice(0, 2).map((cap, i) => (
                    <span key={i} className="text-[10px] px-1.5 py-0.5 bg-terminal-dark rounded text-terminal-dim">
                      {cap}
                    </span>
                  ))}
                </div>
              </div>
            </Link>
          ))}
        </div>
      </div>

      {/* Recommended Workflow */}
      <div className="max-w-7xl mx-auto mt-8">
        <div className="bg-terminal-black border border-terminal-gray rounded p-4">
          <div className="text-xs text-terminal-dim uppercase tracking-wide mb-3">Recommended Workflow</div>
          <div className="flex items-center gap-2 text-xs font-mono text-terminal-text overflow-x-auto">
            <span className="text-terminal-cyan">Data</span>
            <ArrowRight className="w-3 h-3 text-terminal-dim" />
            <span className="text-terminal-cyan">Features</span>
            <ArrowRight className="w-3 h-3 text-terminal-dim" />
            <span className="text-terminal-green">Supervised</span>
            <ArrowRight className="w-3 h-3 text-terminal-dim" />
            <span className="text-terminal-green">Ensemble</span>
            <ArrowRight className="w-3 h-3 text-terminal-dim" />
            <span className="text-terminal-yellow">Explainability</span>
            <ArrowRight className="w-3 h-3 text-terminal-dim" />
            <span className="text-terminal-yellow">Summary</span>
          </div>
          
          <div className="mt-4">
            <Link 
              href="/labs/ml/data"
              className="inline-flex items-center gap-2 px-4 py-2 bg-terminal-cyan text-terminal-black font-mono text-sm font-bold rounded hover:bg-cyan-400 transition-colors"
            >
              <Play className="w-4 h-4" />
              Start Workflow
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
