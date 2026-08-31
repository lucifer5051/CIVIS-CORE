import React from 'react';
import { CameraStatus } from '../types';

interface CameraGridProps {
  cameras: CameraStatus[];
  selectedCameraId: string | null;
  onSelectCamera: (cameraId: string) => void;
}

export const CameraGrid: React.FC<CameraGridProps> = ({
  cameras,
  selectedCameraId,
  onSelectCamera,
}) => {
  if (!cameras || cameras.length === 0) {
    return (
      <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-8 text-center text-slate-500 font-mono">
        No video feeds currently configured or registered.
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {cameras.map((cam) => {
        const isSelected = cam.camera_id === selectedCameraId;
        return (
          <div
            key={cam.camera_id}
            onClick={() => onSelectCamera(cam.camera_id)}
            className={`cursor-pointer group relative overflow-hidden rounded-xl border transition-all duration-200 ${
              isSelected
                ? 'bg-slate-900 border-cyan-500 shadow-[0_0_20px_rgba(6,182,212,0.25)] ring-1 ring-cyan-500'
                : 'bg-slate-900/60 border-slate-800/80 hover:border-slate-700 hover:bg-slate-900'
            }`}
          >
            {/* Camera Viewport / Simulated Stream Frame */}
            <div className="aspect-video bg-slate-950 flex flex-col items-center justify-center relative overflow-hidden">
              <div className="absolute inset-0 bg-[radial-gradient(#1e293b_1px,transparent_1px)] [background-size:16px_16px] opacity-40" />

              {/* Feed Crosshair Graphics */}
              <div className="absolute inset-4 border border-dashed border-slate-800 pointer-events-none opacity-40" />
              <div className="absolute top-2 left-2 flex items-center gap-1.5 px-2 py-1 rounded bg-slate-900/90 backdrop-blur border border-slate-800 text-[10px] font-mono text-slate-300">
                <span
                  className={`w-1.5 h-1.5 rounded-full ${
                    cam.is_running
                      ? 'bg-emerald-400 animate-pulse'
                      : cam.is_paused
                      ? 'bg-amber-400'
                      : 'bg-slate-600'
                  }`}
                />
                {cam.camera_id}
              </div>

              <div className="absolute top-2 right-2 px-2 py-1 rounded bg-slate-900/90 backdrop-blur border border-slate-800 text-[10px] font-mono text-cyan-400 font-bold">
                {cam.current_fps.toFixed(1)} FPS
              </div>

              <div className="z-10 flex flex-col items-center">
                <div className="w-12 h-12 rounded-full bg-slate-900/80 border border-slate-800 flex items-center justify-center text-slate-500 mb-2">
                  <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                  </svg>
                </div>
                <span className="text-xs font-mono text-slate-400">
                  {cam.is_running ? 'STREAM ACTIVE' : cam.is_paused ? 'STREAM PAUSED' : 'STREAM IDLE'}
                </span>
              </div>

              {/* Bottom Metrics Overlay */}
              <div className="absolute bottom-0 inset-x-0 bg-slate-950/90 backdrop-blur border-t border-slate-800/80 px-3 py-1.5 flex items-center justify-between text-[10px] font-mono text-slate-400">
                <span>PROC: <strong className="text-slate-200">{cam.processed_frames}</strong></span>
                <span>DROP: <strong className={cam.dropped_frames > 0 ? 'text-amber-400' : 'text-slate-400'}>{cam.dropped_frames}</strong></span>
                <span>ERR: <strong className={cam.error_count > 0 ? 'text-rose-400' : 'text-slate-400'}>{cam.error_count}</strong></span>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
};
