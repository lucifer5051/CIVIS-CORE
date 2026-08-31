import React, { useEffect, useState } from 'react';
import { api } from '../api/client';

export const ConfigPage: React.FC = () => {
  const [config, setConfig] = useState<Record<string, any> | null>(null);
  const [snapshot, setSnapshot] = useState<Record<string, any> | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    const fetchConfig = async () => {
      try {
        setLoading(true);
        const [cfg, snap] = await Promise.all([
          api.getConfig(),
          api.getConfigSnapshot(),
        ]);
        setConfig(cfg);
        setSnapshot(snap);
      } catch (err: any) {
        console.error('Failed to load configuration:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchConfig();
  }, []);

  if (loading) {
    return (
      <div className="p-12 text-center text-slate-500 font-mono text-xs">
        Loading active system configuration & snapshot...
      </div>
    );
  }

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold text-white font-['Outfit']">System Configuration & Policies</h2>
          <p className="text-xs text-slate-400 font-mono">
            Read-only configuration overview and cryptographic snapshot verification.
          </p>
        </div>

        {snapshot && (
          <div className="bg-slate-900 border border-slate-800 rounded-lg px-3 py-1.5 text-[10px] font-mono">
            <span className="text-slate-500 block">Snapshot Checksum:</span>
            <span className="text-cyan-400 font-bold">{snapshot.checksum?.slice(0, 16)}...</span>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Active Subsystem Sections */}
        <div className="bg-slate-900/70 backdrop-blur border border-slate-800 rounded-xl p-5 shadow-lg space-y-4">
          <h3 className="text-sm font-bold text-white font-mono uppercase tracking-wider border-b border-slate-800 pb-2">
            Subsystem Parameters
          </h3>
          <pre className="bg-slate-950 p-4 rounded-lg border border-slate-800 text-[11px] font-mono text-slate-300 overflow-x-auto max-h-96">
            {JSON.stringify(config, null, 2)}
          </pre>
        </div>

        {/* Snapshot & Policies */}
        <div className="bg-slate-900/70 backdrop-blur border border-slate-800 rounded-xl p-5 shadow-lg space-y-4">
          <h3 className="text-sm font-bold text-white font-mono uppercase tracking-wider border-b border-slate-800 pb-2">
            Active Snapshot Metadata
          </h3>
          <div className="space-y-3 text-xs font-mono">
            <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
              <span className="text-slate-500 block mb-1">Snapshot ID:</span>
              <span className="text-white font-bold">{snapshot?.snapshot_id}</span>
            </div>
            <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
              <span className="text-slate-500 block mb-1">Version:</span>
              <span className="text-slate-200">{snapshot?.version || '1.0.0'}</span>
            </div>
            <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
              <span className="text-slate-500 block mb-1">SHA-256 Checksum:</span>
              <span className="text-cyan-400 break-all text-[11px]">{snapshot?.checksum}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
