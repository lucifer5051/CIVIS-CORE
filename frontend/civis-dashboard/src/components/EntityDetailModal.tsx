import React from 'react';
import { IdentityItem, ReIDEntityItem, TrackItem } from '../types';

interface EntityDetailModalProps {
  entityKey: string | null;
  track?: TrackItem | null;
  identity?: IdentityItem | null;
  reidEntity?: ReIDEntityItem | null;
  onClose: () => void;
}

export const EntityDetailModal: React.FC<EntityDetailModalProps> = ({
  entityKey,
  track,
  identity,
  reidEntity,
  onClose,
}) => {
  if (!entityKey) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-xl w-full overflow-hidden shadow-2xl">
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between bg-slate-950/40">
          <div className="flex items-center space-x-3">
            <div className="w-3 h-3 rounded-full bg-cyan-400" />
            <h3 className="text-base font-bold text-white font-['Outfit']">Entity Intelligence: {entityKey}</h3>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white text-lg font-mono p-1"
          >
            ✕
          </button>
        </div>

        <div className="p-6 space-y-4 text-xs font-mono">
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
              <span className="text-slate-500 block mb-1">Global Re-ID:</span>
              <span className="text-cyan-400 font-bold">{reidEntity?.global_id || 'N/A'}</span>
            </div>
            <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
              <span className="text-slate-500 block mb-1">Appearance Match:</span>
              <span className="text-emerald-400 font-bold">
                {reidEntity ? `${(reidEntity.similarity * 100).toFixed(1)}%` : 'Local only'}
              </span>
            </div>
            <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
              <span className="text-slate-500 block mb-1">Verified Identity:</span>
              <span className="text-white font-bold">{identity?.name || 'Unregistered / Unknown'}</span>
            </div>
            <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
              <span className="text-slate-500 block mb-1">Track Confidence:</span>
              <span className="text-slate-200 font-bold">
                {track ? `${(track.confidence * 100).toFixed(0)}%` : 'N/A'}
              </span>
            </div>
          </div>

          <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
            <span className="text-slate-500 block mb-1">Track History:</span>
            <p className="text-slate-300">
              {track ? `Track #${track.track_id} on ${track.camera_id} (${track.hits} hits, age ${track.age} frames)` : 'No active track history.'}
            </p>
          </div>

          <div className="border-t border-slate-800 pt-4 flex justify-end">
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
