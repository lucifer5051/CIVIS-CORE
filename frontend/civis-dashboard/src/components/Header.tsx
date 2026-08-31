import React from 'react';
import { HealthResponse } from '../types';
import { ConnectionState } from '../hooks/useWebSocket';

interface HeaderProps {
  health: HealthResponse | null;
  wsState: ConnectionState;
  activeTab: 'live' | 'dashboard' | 'config';
  onTabChange: (tab: 'live' | 'dashboard' | 'config') => void;
}

export const Header: React.FC<HeaderProps> = ({
  health,
  wsState,
  activeTab,
  onTabChange,
}) => {
  const isHealthy = health?.status === 'HEALTHY';
  const isDegraded = health?.status === 'DEGRADED';

  return (
    <header className="bg-slate-900/80 backdrop-blur border-b border-slate-800 sticky top-0 z-40 px-6 py-3.5 flex items-center justify-between shadow-lg">
      <div className="flex items-center space-x-6">
        <div className="flex items-center space-x-3">
          <div className="w-8 h-8 rounded-lg bg-cyan-500/20 border border-cyan-500/50 flex items-center justify-center text-cyan-400 font-bold font-mono">
            CV
          </div>
          <div>
            <h1 className="text-lg font-bold tracking-wider text-white font-['Outfit'] flex items-center gap-2">
              CIVIS<span className="text-cyan-400 font-mono text-sm">CORE</span>
            </h1>
            <p className="text-[10px] text-slate-400 font-mono tracking-wider uppercase">Mission Control Console</p>
          </div>
        </div>

        <nav className="flex items-center space-x-1 bg-slate-950/60 p-1 rounded-lg border border-slate-800">
          <button
            onClick={() => onTabChange('live')}
            className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all flex items-center space-x-1.5 ${
              activeTab === 'live'
                ? 'bg-cyan-500 text-slate-950 font-semibold shadow-sm'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <span className="w-2 h-2 rounded-full bg-rose-500 animate-pulse" />
            <span>Live Monitor</span>
          </button>
          <button
            onClick={() => onTabChange('dashboard')}
            className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
              activeTab === 'dashboard'
                ? 'bg-cyan-500 text-slate-950 font-semibold shadow-sm'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            Surveillance Grid
          </button>
          <button
            onClick={() => onTabChange('config')}
            className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
              activeTab === 'config'
                ? 'bg-cyan-500 text-slate-950 font-semibold shadow-sm'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            Policy & Config
          </button>
        </nav>
      </div>

      <div className="flex items-center space-x-4">
        {/* System Health Badge */}
        <div className="flex items-center space-x-2 bg-slate-950/80 px-3 py-1.5 rounded-md border border-slate-800">
          <span className="text-xs text-slate-400 font-mono">SYSTEM:</span>
          <span
            className={`flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-bold font-mono ${
              isHealthy
                ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                : isDegraded
                ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                : 'bg-rose-500/20 text-rose-400 border border-rose-500/30'
            }`}
          >
            <span
              className={`w-2 h-2 rounded-full animate-pulse ${
                isHealthy ? 'bg-emerald-400' : isDegraded ? 'bg-amber-400' : 'bg-rose-400'
              }`}
            />
            {health?.status || 'OFFLINE'}
          </span>
        </div>

        {/* Live Cameras Count */}
        <div className="flex items-center space-x-2 bg-slate-950/80 px-3 py-1.5 rounded-md border border-slate-800 text-xs font-mono">
          <span className="text-slate-400">FEEDS:</span>
          <span className="text-cyan-400 font-bold">{health?.active_cameras ?? 0}</span>
          <span className="text-slate-600">/</span>
          <span className="text-slate-300">{health?.total_cameras ?? 0}</span>
        </div>

        {/* WebSocket Connection Status */}
        <div className="flex items-center space-x-2 bg-slate-950/80 px-3 py-1.5 rounded-md border border-slate-800 text-xs font-mono">
          <span className="text-slate-400">STREAM:</span>
          <span
            className={`font-semibold ${
              wsState === 'OPEN'
                ? 'text-emerald-400'
                : wsState === 'CONNECTING' || wsState === 'RECONNECTING'
                ? 'text-amber-400'
                : 'text-rose-400'
            }`}
          >
            {wsState}
          </span>
        </div>
      </div>
    </header>
  );
};
