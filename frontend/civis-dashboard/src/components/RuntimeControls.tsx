import React, { useState } from 'react';
import { RuntimeStatusResponse } from '../types';

interface RuntimeControlsProps {
  runtimeStatus: RuntimeStatusResponse | null;
  onStartRuntime: () => void;
  onStopRuntime: () => void;
}

export const RuntimeControls: React.FC<RuntimeControlsProps> = ({
  runtimeStatus,
  onStartRuntime,
  onStopRuntime,
}) => {
  const [showConfirm, setShowConfirm] = useState(false);
  const isRunning = runtimeStatus?.state === 'running';

  const handleStopClick = () => {
    setShowConfirm(true);
  };

  const confirmStop = () => {
    setShowConfirm(false);
    onStopRuntime();
  };

  return (
    <div className="bg-slate-900/70 backdrop-blur border border-slate-800 rounded-xl p-4 flex items-center justify-between shadow-lg">
      <div className="flex items-center space-x-3">
        <div className="w-3 h-3 rounded-full bg-cyan-400 animate-pulse" />
        <div>
          <h3 className="text-xs font-bold text-white uppercase tracking-wider font-mono">
            Pipeline Orchestration Engine
          </h3>
          <p className="text-[10px] text-slate-400 font-mono">
            State: <strong className="text-slate-200 uppercase">{runtimeStatus?.state || 'STOPPED'}</strong> | Uptime: {runtimeStatus?.uptime_seconds?.toFixed(1) ?? 0}s
          </p>
        </div>
      </div>

      <div className="flex items-center space-x-3">
        {isRunning ? (
          <button
            onClick={handleStopClick}
            className="px-4 py-2 rounded-lg bg-rose-500/20 text-rose-300 border border-rose-500/40 text-xs font-bold font-mono hover:bg-rose-500/30 transition-all"
          >
            STOP PIPELINE
          </button>
        ) : (
          <button
            onClick={onStartRuntime}
            className="px-4 py-2 rounded-lg bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 text-xs font-bold font-mono hover:bg-emerald-500/30 transition-all"
          >
            START PIPELINE
          </button>
        )}
      </div>

      {showConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-sm w-full p-6 space-y-4 shadow-2xl">
            <h4 className="text-sm font-bold text-white font-['Outfit']">Confirm Shutdown</h4>
            <p className="text-xs text-slate-300">
              Are you sure you want to stop all active multi-camera surveillance pipelines?
            </p>
            <div className="flex justify-end space-x-3 pt-2">
              <button
                onClick={() => setShowConfirm(false)}
                className="px-3 py-1.5 rounded-lg bg-slate-800 text-slate-300 text-xs font-medium hover:bg-slate-700"
              >
                Cancel
              </button>
              <button
                onClick={confirmStop}
                className="px-3 py-1.5 rounded-lg bg-rose-600 text-white text-xs font-bold hover:bg-rose-500"
              >
                Confirm Stop
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
