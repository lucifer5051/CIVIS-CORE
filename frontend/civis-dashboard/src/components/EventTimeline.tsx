import React, { useState } from 'react';
import { PipelineEventMessage } from '../types';

interface EventTimelineProps {
  events: PipelineEventMessage[];
  onClear?: () => void;
}

export const EventTimeline: React.FC<EventTimelineProps> = ({ events, onClear }) => {
  const [filterType, setFilterType] = useState<string>('all');

  const filteredEvents = events.filter((e) => {
    if (filterType === 'all') return true;
    return e.event_type.toLowerCase().includes(filterType.toLowerCase());
  });

  return (
    <div className="bg-slate-900/70 backdrop-blur border border-slate-800 rounded-xl flex flex-col h-full overflow-hidden shadow-lg">
      <div className="px-4 py-3 border-b border-slate-800 flex items-center justify-between bg-slate-950/40">
        <div className="flex items-center space-x-2">
          <div className="w-2 h-2 rounded-full bg-cyan-400 animate-ping" />
          <h2 className="text-sm font-semibold text-white tracking-wide font-['Outfit']">Live Event Timeline</h2>
        </div>

        <div className="flex items-center space-x-2">
          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
            className="bg-slate-950 border border-slate-800 text-[10px] font-mono text-slate-300 rounded px-2 py-1 focus:outline-none focus:border-cyan-500"
          >
            <option value="all">All Events</option>
            <option value="risk">Risk</option>
            <option value="behavior">Behavior</option>
            <option value="frame">Frames</option>
            <option value="error">Errors</option>
          </select>
          {onClear && (
            <button
              onClick={onClear}
              className="text-[10px] font-mono text-slate-500 hover:text-slate-300 px-2 py-1 rounded hover:bg-slate-800 transition-colors"
            >
              Clear
            </button>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-2 font-mono text-xs">
        {filteredEvents.length === 0 ? (
          <div className="text-center py-8 text-slate-500 text-xs">
            Waiting for live pipeline events on /ws/events ...
          </div>
        ) : (
          filteredEvents.map((evt, idx) => {
            const isError = evt.event_type.toLowerCase().includes('error') || evt.event_type.toLowerCase().includes('drop');
            const isRisk = evt.event_type.toLowerCase().includes('risk') || evt.event_type.toLowerCase().includes('alert');

            return (
              <div
                key={`${evt.timestamp}-${idx}`}
                className="bg-slate-950/60 border border-slate-800/80 rounded-lg p-2.5 flex items-start justify-between gap-3 hover:border-slate-700 transition-colors"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span
                      className={`text-[10px] px-1.5 py-0.5 rounded font-bold uppercase ${
                        isError
                          ? 'bg-rose-500/20 text-rose-400 border border-rose-500/30'
                          : isRisk
                          ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                          : 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/30'
                      }`}
                    >
                      {evt.event_type}
                    </span>
                    {evt.camera_id && (
                      <span className="text-[10px] text-slate-400 bg-slate-900 px-1.5 py-0.5 rounded border border-slate-800">
                        {evt.camera_id}
                      </span>
                    )}
                  </div>
                  <p className="text-[11px] text-slate-300 break-words font-sans">
                    {typeof evt.data === 'string' ? evt.data : JSON.stringify(evt.data)}
                  </p>
                </div>
                <span className="text-[10px] text-slate-400 shrink-0">
                  {new Date(evt.timestamp * 1000).toLocaleTimeString()}
                </span>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
