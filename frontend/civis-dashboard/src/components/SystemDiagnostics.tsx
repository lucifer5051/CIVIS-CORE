import React from 'react';

interface SystemDiagnosticsProps {
  detailedHealth: Record<string, any> | null;
}

export const SystemDiagnostics: React.FC<SystemDiagnosticsProps> = ({ detailedHealth }) => {
  const obs = detailedHealth?.observability || {};
  const rt = detailedHealth?.runtime || {};

  return (
    <div className="bg-slate-900/70 backdrop-blur border border-slate-800 rounded-xl p-4 shadow-lg space-y-3 font-mono text-xs">
      <div className="flex items-center justify-between border-b border-slate-800 pb-2">
        <h3 className="text-xs font-bold text-white uppercase tracking-wider">
          Diagnostic Telemetry
        </h3>
        <span className="text-[10px] text-cyan-400">
          Uptime: {obs.uptime_seconds ?? rt.uptime_seconds ?? 0}s
        </span>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="bg-slate-950 p-2.5 rounded-lg border border-slate-800">
          <span className="text-slate-500 block text-[10px]">Active Errors</span>
          <span className={`text-sm font-bold ${obs.active_error_count > 0 ? 'text-rose-400' : 'text-slate-200'}`}>
            {obs.active_error_count ?? 0}
          </span>
        </div>

        <div className="bg-slate-950 p-2.5 rounded-lg border border-slate-800">
          <span className="text-slate-500 block text-[10px]">Processed Frames</span>
          <span className="text-sm font-bold text-slate-200">
            {rt.total_frames_processed ?? 0}
          </span>
        </div>

        <div className="bg-slate-950 p-2.5 rounded-lg border border-slate-800">
          <span className="text-slate-500 block text-[10px]">Dropped Frames</span>
          <span className={`text-sm font-bold ${rt.total_frames_dropped > 0 ? 'text-amber-400' : 'text-slate-200'}`}>
            {rt.total_frames_dropped ?? 0}
          </span>
        </div>

        <div className="bg-slate-950 p-2.5 rounded-lg border border-slate-800">
          <span className="text-slate-500 block text-[10px]">Active Cameras</span>
          <span className="text-sm font-bold text-cyan-400">
            {rt.active_cameras ?? 0} / {rt.total_cameras ?? 0}
          </span>
        </div>
      </div>
    </div>
  );
};
