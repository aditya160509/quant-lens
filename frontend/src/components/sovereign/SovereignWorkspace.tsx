'use client';

/**
 * SOVEREIGN WORKSPACE
 * The Command-and-Control Hub - A Koyfin-inspired modular dashboard
 * 
 * Features:
 * - 12-column draggable grid (react-grid-layout)
 * - Color-channel synchronization
 * - Widget library with custom formulas
 * - Multi-ticker chart support
 * - Template presets
 */

import React, { useState, useCallback, useMemo, useEffect } from 'react';
import GridLayout, { Layout } from 'react-grid-layout';
import 'react-grid-layout/css/styles.css';
import 'react-resizable/css/styles.css';

import { 
  useSovereignStore, 
  useActiveWorkspace, 
  WORKSPACE_TEMPLATES,
  CHANNEL_COLORS,
  WidgetConfig,
  WidgetType,
  ChannelColor 
} from '@/lib/sovereignStore';

// Widget imports
import AlphaChartWidget from './widgets/AlphaChartWidget';
import TickerTableWidget from './widgets/TickerTableWidget';
import WatchlistWidget from './widgets/WatchlistWidget';
import MetricCardWidget from './widgets/MetricCardWidget';
import GlobalMarketsWidget from './widgets/GlobalMarketsWidget';
import SectorHeatmapWidget from './widgets/SectorHeatmapWidget';
import FactorPulseWidget from './widgets/FactorPulseWidget';
import YieldCurveWidget from './widgets/YieldCurveWidget';
import FundamentalSnapWidget from './widgets/FundamentalSnapWidget';
import CommoditiesWidget from './widgets/CommoditiesWidget';
import CurrenciesWidget from './widgets/CurrenciesWidget';
import StudioChartWidget from './widgets/StudioChartWidget';
import TradingViewSearch from '@/components/symbols/TradingViewSearch';



// Icons
import { 
  Plus, 
  Settings, 
  Layout as LayoutIcon, 
  Trash2, 
  Copy,
  ChevronDown,
  X,
  Maximize2,
  Minimize2,
  Link2,
  Circle
} from 'lucide-react';

// Widget registry - maps type to component
const WIDGET_REGISTRY: Record<WidgetType, React.FC<{ config: WidgetConfig }>> = {
  'studio-chart': StudioChartWidget,
  'alpha-chart': AlphaChartWidget,
  'ticker-table': TickerTableWidget,
  'watchlist': WatchlistWidget,
  'metric-card': MetricCardWidget,
  'global-markets': GlobalMarketsWidget,
  'sector-heatmap': SectorHeatmapWidget,
  'factor-pulse': FactorPulseWidget,
  'yield-curve': YieldCurveWidget,
  'fundamental-snap': FundamentalSnapWidget,
  'commodities': CommoditiesWidget,
  'currencies': CurrenciesWidget,
  'news': () => <div className="p-4 text-terminal-dim text-[10px] uppercase font-mono">News Widget (Coming Soon)</div>,
  'logic-indicator': () => <div className="p-4 text-terminal-dim text-[10px] uppercase font-mono">Logic Indicator (Coming Soon)</div>,
  'custom-formula': () => <div className="p-4 text-terminal-dim text-[10px] uppercase font-mono">Custom Formula (Coming Soon)</div>,
};


// Widget catalog for drawer
const WIDGET_CATALOG = [
  { type: 'studio-chart' as WidgetType, name: 'Studio Chart', description: 'High-performance OHLCV canvas', icon: 'BarChart3', defaultW: 8, defaultH: 6 },
  { type: 'alpha-chart' as WidgetType, name: 'Alpha Chart', description: 'Normalized performance chart', icon: 'ChartLine', defaultW: 8, defaultH: 4 },

  { type: 'ticker-table' as WidgetType, name: 'Ticker Table', description: 'Price table with change %', icon: 'Table', defaultW: 4, defaultH: 4 },
  { type: 'watchlist' as WidgetType, name: 'Watchlist', description: 'Personal ticker watchlist', icon: 'Star', defaultW: 4, defaultH: 4 },
  { type: 'metric-card' as WidgetType, name: 'Metric Card', description: 'Single stat display', icon: 'Target', defaultW: 2, defaultH: 2 },
  { type: 'global-markets' as WidgetType, name: 'Global Markets', description: 'Global indices grid', icon: 'Globe', defaultW: 4, defaultH: 4 },
  { type: 'sector-heatmap' as WidgetType, name: 'Sector Heatmap', description: 'Sector rotation visual', icon: 'Flame', defaultW: 4, defaultH: 3 },
  { type: 'factor-pulse' as WidgetType, name: 'Factor Pulse', description: 'Value/Growth/Momentum matrix', icon: 'Zap', defaultW: 4, defaultH: 3 },
  { type: 'yield-curve' as WidgetType, name: 'Yield Curve', description: 'Global bond yields', icon: 'TrendingDown', defaultW: 4, defaultH: 3 },
  { type: 'fundamental-snap' as WidgetType, name: 'Fundamentals', description: 'P/E, P/B, ROE snapshot', icon: 'FileText', defaultW: 4, defaultH: 3 },
  { type: 'commodities' as WidgetType, name: 'Commodities', description: 'Oil, Gold, Gas prices', icon: 'Package', defaultW: 4, defaultH: 3 },
  { type: 'currencies' as WidgetType, name: 'Currencies', description: 'FX rates & crypto', icon: 'Coins', defaultW: 4, defaultH: 3 },
];

// Widget wrapper component with header
const WidgetWrapper: React.FC<{
  config: WidgetConfig;
  onRemove: () => void;
  onChannelChange: (channel: ChannelColor) => void;
}> = ({ config, onRemove, onChannelChange }) => {
  const [showChannelPicker, setShowChannelPicker] = useState(false);
  const WidgetComponent = WIDGET_REGISTRY[config.type];

  return (
    <div className="h-full flex flex-col bg-terminal-darker/80 backdrop-blur-sm border border-terminal-gray/50 rounded-lg overflow-hidden group">
      {/* Widget Header */}
      <div className="h-8 shrink-0 flex items-center justify-between px-3 bg-terminal-dark/60 border-b border-terminal-gray/30 cursor-move">
        <div className="flex items-center gap-2">
          {/* Channel indicator */}
          {config.channel !== 'none' && (
            <div 
              className="w-2 h-2 rounded-full animate-pulse"
              style={{ backgroundColor: CHANNEL_COLORS[config.channel] }}
            />
          )}
          <span className="text-[10px] font-mono text-terminal-dim uppercase tracking-wider truncate">
            {config.title}
          </span>
        </div>
        
        {/* Widget controls - shown on hover */}
        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          {/* Channel selector */}
          <div className="relative">
            <button
              onClick={(e) => { e.stopPropagation(); setShowChannelPicker(!showChannelPicker); }}
              className="p-1 hover:bg-terminal-gray/50 rounded"
              title="Link Channel"
            >
              <Link2 size={12} className="text-terminal-dim" />
            </button>
            {showChannelPicker && (
              <div className="absolute top-full right-0 mt-1 p-2 bg-terminal-dark border border-terminal-gray rounded-lg shadow-lg z-50 flex gap-1">
                {(['red', 'blue', 'green', 'yellow', 'none'] as ChannelColor[]).map(color => (
                  <button
                    key={color}
                    onClick={() => { onChannelChange(color); setShowChannelPicker(false); }}
                    className={`w-5 h-5 rounded-full border-2 ${
                      config.channel === color ? 'border-white' : 'border-transparent'
                    } hover:scale-110 transition-transform`}
                    style={{ backgroundColor: color === 'none' ? '#333' : CHANNEL_COLORS[color] }}
                    title={color === 'none' ? 'No channel' : `${color} channel`}
                  />
                ))}
              </div>
            )}
          </div>
          
          {/* Remove button */}
          <button
            onClick={(e) => { e.stopPropagation(); onRemove(); }}
            className="p-1 hover:bg-terminal-red/20 rounded"
            title="Remove Widget"
          >
            <X size={12} className="text-terminal-dim hover:text-terminal-red" />
          </button>
        </div>
      </div>
      
      {/* Widget Content */}
      <div className="flex-1 overflow-hidden">
        <WidgetComponent config={config} />
      </div>
    </div>
  );
};

// Main Workspace Component
const CompactGridLayout = GridLayout as any;

export default function SovereignWorkspace() {
  const workspace = useActiveWorkspace();
  const { 
    workspaces,
    activeWorkspaceId,
    isWidgetDrawerOpen,
    setActiveWorkspace,
    createWorkspace,
    deleteWorkspace,
    duplicateWorkspace,
    addWidget,
    removeWidget,
    updateWidgetLayout,
    setWidgetChannel,
    toggleWidgetDrawer,
    applyTemplate,
  } = useSovereignStore();

  const [gridWidth, setGridWidth] = useState(1200);
  const [showTemplates, setShowTemplates] = useState(false);
  const [showWorkspaceMenu, setShowWorkspaceMenu] = useState(false);

  // Calculate grid width on mount and resize
  useEffect(() => {
    const updateWidth = () => {
      const container = document.getElementById('workspace-grid-container');
      if (container) {
        setGridWidth(container.offsetWidth - 24); // Subtract padding
      }
    };
    updateWidth();
    window.addEventListener('resize', updateWidth);
    return () => window.removeEventListener('resize', updateWidth);
  }, []);

  // Convert widgets to grid layout
  const gridLayout: any[] = useMemo(() => 
    workspace?.widgets.map(w => ({
      i: w.id,
      x: w.x,
      y: w.y,
      w: w.w,
      h: w.h,
      minW: w.minW || 2,
      minH: w.minH || 2,
    })) || [], 
    [workspace?.widgets]
  );

  // Handle layout change
  const handleLayoutChange = useCallback((newLayout: any[]) => {
    newLayout.forEach(item => {
      updateWidgetLayout(item.i, { x: item.x, y: item.y, w: item.w, h: item.h });
    });
  }, [updateWidgetLayout]);

  // Add widget from catalog
  const handleAddWidget = useCallback((catalogItem: typeof WIDGET_CATALOG[0]) => {
    addWidget({
      type: catalogItem.type,
      title: catalogItem.name,
      channel: 'none',
      x: 0,
      y: Infinity, // Place at bottom
      w: catalogItem.defaultW,
      h: catalogItem.defaultH,
      settings: {},
    });
    toggleWidgetDrawer();
  }, [addWidget, toggleWidgetDrawer]);

  return (
    <div className="h-full w-full flex flex-col bg-terminal-black overflow-hidden">
      {/* Top Header Bar */}
      <div className="h-12 shrink-0 border-b border-terminal-gray/50 bg-terminal-darker/80 backdrop-blur-sm flex items-center justify-between px-4">
        {/* Left: Logo & Workspace Tabs */}
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2">
            <span className="font-display text-terminal-yellow font-bold tracking-tight">WORKSPACE</span>
          </div>

          
          {/* Workspace tabs */}
          <div className="relative">
            <button
              onClick={() => setShowWorkspaceMenu(!showWorkspaceMenu)}
              className="flex items-center gap-2 px-3 py-1.5 bg-terminal-gray/20 hover:bg-terminal-gray/30 border border-terminal-gray/30 rounded transition-colors"
            >
              <span className="font-mono text-xs text-terminal-text uppercase tracking-wider">{workspace?.name}</span>
              <ChevronDown size={14} className="text-terminal-dim" />
            </button>
            
            {showWorkspaceMenu && (
              <div className="absolute top-full left-0 mt-1 w-64 bg-terminal-dark border border-terminal-gray rounded shadow-xl z-50">
                <div className="p-2 border-b border-terminal-gray/50">
                  <div className="text-[10px] font-mono text-terminal-dim uppercase tracking-wider px-2 py-1">Workspaces</div>
                </div>
                <div className="p-1 max-h-60 overflow-y-auto">
                  {workspaces.map(ws => (
                    <button
                      key={ws.id}
                      onClick={() => { setActiveWorkspace(ws.id); setShowWorkspaceMenu(false); }}
                      className={`w-full flex items-center justify-between px-3 py-2 rounded-md text-left ${
                        ws.id === activeWorkspaceId 
                          ? 'bg-terminal-yellow/10 text-terminal-yellow' 
                          : 'hover:bg-terminal-gray/30 text-terminal-text'
                      }`}
                    >
                      <span className="font-mono text-sm truncate">{ws.name}</span>
                      <div className="flex items-center gap-1">
                        <button
                          onClick={(e) => { e.stopPropagation(); duplicateWorkspace(ws.id); }}
                          className="p-1 hover:bg-terminal-gray/50 rounded"
                        >
                          <Copy size={12} className="text-terminal-dim" />
                        </button>
                        {workspaces.length > 1 && (
                          <button
                            onClick={(e) => { e.stopPropagation(); deleteWorkspace(ws.id); }}
                            className="p-1 hover:bg-terminal-red/20 rounded"
                          >
                            <Trash2 size={12} className="text-terminal-dim hover:text-terminal-red" />
                          </button>
                        )}
                      </div>
                    </button>
                  ))}
                </div>
                <div className="p-2 border-t border-terminal-gray/50">
                  <button
                    onClick={() => { createWorkspace('New Workspace'); setShowWorkspaceMenu(false); }}
                    className="w-full flex items-center gap-2 px-3 py-2 rounded-md hover:bg-terminal-gray/30 text-terminal-dim hover:text-terminal-text"
                  >
                    <Plus size={14} />
                    <span className="font-mono text-sm">New Workspace</span>
                  </button>
                </div>
              </div>
            )}
          </div>

          <div className="h-6 w-px bg-terminal-gray/30 mx-2" />

          {/* Universe Selector */}
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-mono text-terminal-dim uppercase tracking-widest">Universe:</span>
            <select 
              value={useSovereignStore.getState().selectedUniverse}
              onChange={(e) => useSovereignStore.getState().setSelectedUniverse(e.target.value)}
              className="bg-terminal-black border border-terminal-gray/50 text-terminal-text px-2 py-1 font-mono text-xs outline-none rounded hover:border-terminal-yellow/50 transition-colors"
            >
              <option value="US">US Equity</option>
              <option value="ETF">ETF Universe</option>
              <option value="INDIA">India (NSE)</option>
              <option value="MACRO">Macro Assets</option>
            </select>
          </div>
        </div>

        {/* Center: Search */}
        <div className="flex-1 max-w-md px-10">
          <TradingViewSearch 
            onSelect={(ticker) => {
              // Broadcast to active channel (default blue if none)
              const { broadcastToChannel, addTicker } = useSovereignStore.getState();
              addTicker(ticker);
              broadcastToChannel('blue', ticker);
            }} 
            placeholder="Search symbols..."
          />
        </div>

        
        {/* Right: Actions */}
        <div className="flex items-center gap-2">
          {/* Templates dropdown */}
          <div className="relative">
            <button
              onClick={() => setShowTemplates(!showTemplates)}
              className="flex items-center gap-2 px-3 py-1.5 bg-terminal-gray/30 hover:bg-terminal-gray/50 rounded-md transition-colors"
            >
              <LayoutIcon size={14} className="text-terminal-dim" />
              <span className="font-mono text-xs text-terminal-dim">Templates</span>
            </button>
            
            {showTemplates && (
              <div className="absolute top-full right-0 mt-1 w-72 bg-terminal-dark border border-terminal-gray rounded-lg shadow-xl z-50">
                <div className="p-2 border-b border-terminal-gray/50">
                  <div className="text-[10px] font-mono text-terminal-dim uppercase tracking-wider px-2 py-1">Apply Template</div>
                </div>
                <div className="p-1">
                  {WORKSPACE_TEMPLATES.map(template => (
                    <button
                      key={template.id}
                      onClick={() => { applyTemplate(template.id); setShowTemplates(false); }}
                      className="w-full flex flex-col items-start px-3 py-2 rounded-md hover:bg-terminal-gray/30 text-left"
                    >
                      <span className="font-mono text-sm text-terminal-text">{template.name}</span>
                      <span className="text-[10px] text-terminal-dim">{template.description}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
          
          {/* Add Widget */}
          <button
            onClick={toggleWidgetDrawer}
            className="flex items-center gap-2 px-3 py-1.5 bg-terminal-yellow/10 hover:bg-terminal-yellow/20 border border-terminal-yellow/30 rounded-md transition-colors"
          >
            <Plus size={14} className="text-terminal-yellow" />
            <span className="font-mono text-xs text-terminal-yellow">Add Widget</span>
          </button>
        </div>
      </div>
      
      {/* Main Grid Area */}
      <div id="workspace-grid-container" className="flex-1 overflow-auto p-3">
        {workspace?.widgets.length === 0 ? (
          // Empty state
          <div className="h-full flex flex-col items-center justify-center gap-4 text-center">
            <div className="w-24 h-24 rounded-full bg-terminal-gray/20 flex items-center justify-center">
              <LayoutIcon size={32} className="text-terminal-dim" />
            </div>
            <div>
              <h3 className="font-display text-lg text-terminal-text mb-1">Empty Workspace</h3>
              <p className="text-sm text-terminal-dim">Add widgets or apply a template to get started</p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={toggleWidgetDrawer}
                className="px-4 py-2 bg-terminal-yellow/10 hover:bg-terminal-yellow/20 border border-terminal-yellow/30 rounded-md font-mono text-sm text-terminal-yellow"
              >
                Add Widget
              </button>
              <button
                onClick={() => setShowTemplates(true)}
                className="px-4 py-2 bg-terminal-gray/30 hover:bg-terminal-gray/50 rounded-md font-mono text-sm text-terminal-dim"
              >
                Use Template
              </button>
            </div>
          </div>
        ) : (
          <CompactGridLayout
            className="layout"
            layout={gridLayout}
            cols={12}
            rowHeight={80}
            width={gridWidth}
            onLayoutChange={handleLayoutChange}
            draggableHandle=".cursor-move"
            compactType="vertical"
            preventCollision={false}
            margin={[8, 8]}
          >
            {workspace?.widgets.map(widget => (
              <div key={widget.id}>
                <WidgetWrapper
                  config={widget}
                  onRemove={() => removeWidget(widget.id)}
                  onChannelChange={(channel) => setWidgetChannel(widget.id, channel)}
                />
              </div>
            ))}
          </CompactGridLayout>
        )}

      </div>
      
      {/* Widget Drawer */}
      {isWidgetDrawerOpen && (
        <div className="fixed inset-0 z-50 flex">
          {/* Backdrop */}
          <div 
            className="flex-1 bg-black/60 backdrop-blur-sm"
            onClick={toggleWidgetDrawer}
          />
          
          {/* Drawer */}
          <div className="w-80 bg-terminal-dark border-l border-terminal-gray/50 flex flex-col">
            <div className="h-12 shrink-0 flex items-center justify-between px-4 border-b border-terminal-gray/50">
              <span className="font-display text-sm text-terminal-text">Widget Library</span>
              <button
                onClick={toggleWidgetDrawer}
                className="p-1 hover:bg-terminal-gray/30 rounded"
              >
                <X size={16} className="text-terminal-dim" />
              </button>
            </div>
            
            <div className="flex-1 overflow-y-auto p-3">
              <div className="grid grid-cols-2 gap-2">
                {WIDGET_CATALOG.map(item => (
                  <button
                    key={item.type}
                    onClick={() => handleAddWidget(item)}
                    className="flex flex-col items-center gap-2 p-4 bg-terminal-gray/20 hover:bg-terminal-gray/40 border border-terminal-gray/30 hover:border-terminal-yellow/30 rounded transition-all"
                  >
                    <span className="font-mono text-[10px] font-bold text-terminal-text uppercase tracking-widest">{item.name}</span>
                    <span className="text-[10px] text-terminal-dim text-center">{item.description}</span>
                  </button>
                ))}
              </div>
            </div>

          </div>
        </div>
      )}
    </div>
  );
}
