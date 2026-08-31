import React from 'react';
import { CameraStatus } from '../types';

interface CameraDetailModalProps {
  camera: CameraStatus | null;
  onClose: () => void;
  onStart: (cameraId: string) => void;
  onStop: (cameraId: string) => void;
  onPause: (cameraId: string) => void;
  onResume: (cameraId: string) => void;
}

export const CameraDetailModal: React.FC<CameraDetailModalProps> = ({
  camera,
  onClose,
  onStart,
  onStop,
  onPause,
  onResume,
}) => {
  if (!camera) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-xl w-full overflow-hidden shadow-2xl">
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between bg-slate-950/40">
          <div className="flex items-center space-x-3">
            <div className="w-3 h-3 rounded-full bg-cyan-400" />
            <h3 className="text-base font-bold text-white font-['Outfit']">Feed Control: {camera.camera_id}</h3>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white text-lg font-mono p-1"
          >
            ✕
          </button>
        </div>

        <div className="p-6 space-y-6">
          <div className="grid grid-cols-2 gap-4 text-xs font-mono">
            <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
              <span className="text-slate-500 block mb-1">State:</span>
              <span className="text-white font-bold text-sm">
                {camera.is_running ? 'RUNNING' : camera.is_paused ? 'PAUSED' : 'STOPPED'}
              </span>
            </div>
            <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
              <span className="text-slate-500 block mb-1">FPS:</span>
              <span className="text-cyan-400 font-bold text-sm">{camera.current_fps.toFixed(1)}</span>
            </div>
            <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
              <span className="text-slate-500 block mb-1">Processed Frames:</span>
              <span className="text-slate-200 font-bold text-sm">{camera.processed_frames}</span>
            </div>
            <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
              <span className="text-slate-500 block mb-1">Dropped Frames:</span>
              <span className="text-amber-400 font-bold text-sm">{camera.dropped_frames}</span>
            </div>
          </div>

          <div className="border-t border-slate-800 pt-4 flex items-center justify-end space-x-3">
            {camera.is_running ? (
              <>
                <button
                  onClick={() => onPause(camera.camera_id)}
                  className="px-4 py-2 rounded-lg bg-amber-500/20 text-amber-300 border border-amber-500/40 text-xs font-semibold hover:bg-amber-500/30 transition-all"
                >
                  Pause Stream
                </button>
                <button
                  onClick={() => onStop(camera.camera_id)}
                  className="px-4 py-2 rounded-lg bg-rose-500/20 text-rose-300 border border-rose-500/40 text-xs font-semibold hover:bg-rose-500/30 transition-all"
                >
                  Stop Stream
                </button>
              </>
            ) : camera.is_paused ? (
              <button
                onClick={() => onResume(camera.camera_id)}
                className="px-4 py-2 rounded-lg bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 text-xs font-semibold hover:bg-emerald-500/30 transition-all"
              >
                Resume Stream
              </button>
            ) : (
              <button
                onClick={() => onStart(camera.camera_id)}
                className="px-4 py-2 rounded-lg bg-cyan-500 text-slate-950 font-bold text-xs hover:bg-cyan-400 transition-all"
              >
                Start Stream
              </button>
            )}
            <button
              onClick={onClose}
              className="px-4 py-2 rounded-lg bg-slate-800 text-slate-300 text-xs font-medium hover:bg-slate-700 transition-all"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
