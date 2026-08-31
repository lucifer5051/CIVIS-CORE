import React, { useState, useEffect } from 'react';
import {
  CameraStatus,
  PipelineEventMessage,
  RiskAlertItem,
  RiskAssessmentItem,
  TrackItem,
  IdentityItem,
  ReIDEntityItem,
} from '../types';
import { api } from '../api/client';

interface LiveMonitoringPageProps {
  cameras: CameraStatus[];
  events: PipelineEventMessage[];
  tracks: TrackItem[];
  identities: IdentityItem[];
  reidEntities: ReIDEntityItem[];
  risks: RiskAssessmentItem[];
  alerts: RiskAlertItem[];
  onRefreshData: () => void;
}

export const LiveMonitoringPage: React.FC<LiveMonitoringPageProps> = ({
  cameras,
  events,
  tracks: initialTracks,
  identities: initialIdentities,
  reidEntities: initialReidEntities,
  risks: initialRisks,
  alerts: initialAlerts,
  onRefreshData,
}) => {
  const defaultCam = cameras.length > 0 ? cameras[0].camera_id : 'CAM_01';
  const [selectedCamera, setSelectedCamera] = useState<string>(defaultCam);
  const [isStarting, setIsStarting] = useState(false);
  const [streamError, setStreamError] = useState(false);
  const [streamKey, setStreamKey] = useState(Date.now());

  // Dynamic state populated from real-time WebSocket telemetry
  const [liveTelemetry, setLiveTelemetry] = useState<{
    fps: number;
    latency_ms: number;
    stage_timings: Record<string, number>;
    tracks: any[];
    identities: any[];
    global_entities: any[];
    behavior_events: any[];
    risk_score: number;
    risk_alerts: any[];
  }>({
    fps: 0,
    latency_ms: 0,
    stage_timings: {},
    tracks: initialTracks,
    identities: initialIdentities,
    global_entities: initialReidEntities,
    behavior_events: [],
    risk_score: initialRisks.length > 0 ? Math.max(...initialRisks.map((r) => r.overall_score * 100)) : 0,
    risk_alerts: initialAlerts,
  });

  const activeCamStatus = cameras.find((c) => c.camera_id === selectedCamera);
  const isRunning = activeCamStatus?.is_running ?? false;
  const isPaused = activeCamStatus?.is_paused ?? false;

  // Listen for pipeline_telemetry WebSocket events
  useEffect(() => {
    if (!events.length) return;
    const latest = events[0];
    if (latest.event_type === 'pipeline_telemetry' && latest.camera_id === selectedCamera) {
      const d = latest.data;
      if (d) {
        setLiveTelemetry({
          fps: activeCamStatus?.current_fps ?? 0,
          latency_ms: Object.values(d.stage_timings_ms || {}).reduce((a: any, b: any) => a + b, 0) as number,
          stage_timings: d.stage_timings_ms || {},
          tracks: d.tracks || [],
          identities: d.identities || [],
          global_entities: d.global_entities || [],
          behavior_events: d.behavior_events || [],
          risk_score: d.risk_score || 0,
          risk_alerts: d.risk_alerts || [],
        });
      }
    }
  }, [events, selectedCamera, activeCamStatus]);

  // Camera Control Actions
  const handleStartCamera = async () => {
    try {
      setIsStarting(true);
      await api.startCamera(selectedCamera);
      setStreamError(false);
      setStreamKey(Date.now());
      setTimeout(() => {
        onRefreshData();
        setIsStarting(false);
      }, 1000);
    } catch (err) {
      console.error('Failed to start camera:', err);
      setIsStarting(false);
    }
  };

  const handleStopCamera = async () => {
    try {
      await api.stopCamera(selectedCamera);
      onRefreshData();
    } catch (err) {
      console.error('Failed to stop camera:', err);
    }
  };

  const handlePauseCamera = async () => {
    try {
      await api.pauseCamera(selectedCamera);
      onRefreshData();
    } catch (err) {
      console.error('Failed to pause camera:', err);
    }
  };

  const handleResumeCamera = async () => {
    try {
      await api.resumeCamera(selectedCamera);
      onRefreshData();
    } catch (err) {
      console.error('Failed to resume camera:', err);
    }
  };

  const streamUrl = `/api/cameras/${encodeURIComponent(selectedCamera)}/stream?t=${streamKey}`;

  return (
    <div className="p-6 space-y-6 max-w-[1750px] mx-auto">
      {/* 1. TOP CONTROL BAR */}
      <div className="bg-slate-900/90 backdrop-blur border border-slate-800 rounded-xl p-4 shadow-xl flex flex-wrap items-center justify-between gap-4">
        {/* Left: Camera Selector & Status */}
        <div className="flex items-center space-x-4">
          <div className="flex items-center space-x-2">
            <span className="text-xs text-slate-400 font-mono uppercase">Camera Feed:</span>
            <select
              value={selectedCamera}
              onChange={(e) => {
                setSelectedCamera(e.target.value);
                setStreamKey(Date.now());
              }}
              className="bg-slate-950 text-white font-mono text-sm border border-slate-700 rounded-lg px-3 py-1.5 focus:outline-none focus:border-cyan-500"
            >
              {cameras.length > 0 ? (
                cameras.map((c) => (
                  <option key={c.camera_id} value={c.camera_id}>
                    {c.camera_id} {c.is_running ? '(Live)' : '(Offline)'}
                  </option>
                ))
              ) : (
                <option value="CAM_01">CAM_01 (Laptop Webcam)</option>
              )}
            </select>
          </div>

          {/* Camera Status Badge */}
          <div className="flex items-center space-x-2">
            <span
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-bold font-mono tracking-wider ${
                isRunning && !isPaused
                  ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                  : isPaused
                  ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                  : isStarting
                  ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/30'
                  : 'bg-slate-800 text-slate-400 border border-slate-700'
              }`}
            >
              <span
                className={`w-2 h-2 rounded-full ${
                  isRunning && !isPaused
                    ? 'bg-emerald-400 animate-pulse'
                    : isPaused
                    ? 'bg-amber-400'
                    : isStarting
                    ? 'bg-cyan-400 animate-ping'
                    : 'bg-slate-500'
                }`}
              />
              {isRunning && !isPaused
                ? 'LIVE STREAMING'
                : isPaused
                ? 'PAUSED'
                : isStarting
                ? 'INITIALIZING'
                : 'OFFLINE'}
            </span>
          </div>

          {/* Privacy Guarantee Badge */}
          <div className="hidden lg:flex items-center space-x-1.5 bg-slate-950/80 px-2.5 py-1 rounded-md border border-slate-800 text-[11px] font-mono text-cyan-400">
            <span>🔒</span>
            <span>LOCAL ONLY • NO CLOUD RECORDING</span>
          </div>
        </div>

        {/* Center: Live Telemetry Chips */}
        <div className="flex items-center space-x-3 text-xs font-mono">
          <div className="bg-slate-950 px-3 py-1.5 rounded-lg border border-slate-800">
            <span className="text-slate-500">FPS: </span>
            <span className="text-emerald-400 font-bold">
              {activeCamStatus?.current_fps?.toFixed(1) || '0.0'}
            </span>
          </div>
          <div className="bg-slate-950 px-3 py-1.5 rounded-lg border border-slate-800">
            <span className="text-slate-500">LATENCY: </span>
            <span className="text-cyan-400 font-bold">
              {liveTelemetry.latency_ms > 0 ? `${liveTelemetry.latency_ms.toFixed(1)} ms` : '< 5 ms'}
            </span>
          </div>
          <div className="bg-slate-950 px-3 py-1.5 rounded-lg border border-slate-800">
            <span className="text-slate-500">FRAMES: </span>
            <span className="text-white font-bold">{activeCamStatus?.processed_frames || 0}</span>
          </div>
        </div>

        {/* Right: Camera Action Controls */}
        <div className="flex items-center space-x-2">
          {!isRunning ? (
            <button
              onClick={handleStartCamera}
              disabled={isStarting}
              className="bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs px-4 py-2 rounded-lg transition-all shadow-md shadow-emerald-950 flex items-center space-x-1.5 disabled:opacity-50"
            >
              <span>▶</span>
              <span>{isStarting ? 'Starting...' : 'Start Camera'}</span>
            </button>
          ) : (
            <>
              {isPaused ? (
                <button
                  onClick={handleResumeCamera}
                  className="bg-cyan-600 hover:bg-cyan-500 text-white font-semibold text-xs px-3 py-2 rounded-lg transition-all shadow-md"
                >
                  Resume
                </button>
              ) : (
                <button
                  onClick={handlePauseCamera}
                  className="bg-amber-600 hover:bg-amber-500 text-white font-semibold text-xs px-3 py-2 rounded-lg transition-all shadow-md"
                >
                  Pause
                </button>
              )}
              <button
                onClick={handleStopCamera}
                className="bg-rose-600 hover:bg-rose-500 text-white font-semibold text-xs px-4 py-2 rounded-lg transition-all shadow-md shadow-rose-950"
              >
                Stop Camera
              </button>
            </>
          )}
        </div>
      </div>

      {/* 2. MAIN WORKSPACE (LEFT: LIVE FEED, RIGHT: INTELLIGENCE PANEL) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* LEFT: LIVE VIDEO FEED CONTAINER */}
        <div className="lg:col-span-8 space-y-4">
          <div className="relative bg-slate-950 border border-slate-800 rounded-2xl overflow-hidden shadow-2xl aspect-video flex items-center justify-center group">
            {isRunning && !streamError ? (
              <img
                src={streamUrl}
                alt="CIVIS Live Camera Stream"
                className="w-full h-full object-contain bg-black"
                onError={() => setStreamError(true)}
              />
            ) : (
              <div className="text-center p-8 space-y-4">
                <div className="w-16 h-16 rounded-full bg-slate-900 border border-slate-800 flex items-center justify-center mx-auto text-2xl text-slate-500">
                  📹
                </div>
                <div>
                  <h3 className="text-base font-semibold text-slate-300">Camera Feed Inactive</h3>
                  <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
                    Click <strong>Start Camera</strong> above to initialize the webcam and begin real-time surveillance analytics.
                  </p>
                </div>
                {!isRunning && (
                  <button
                    onClick={handleStartCamera}
                    disabled={isStarting}
                    className="bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold text-xs px-5 py-2.5 rounded-lg transition-all shadow-lg"
                  >
                    {isStarting ? 'Initializing...' : 'Launch Live Camera Stream'}
                  </button>
                )}
              </div>
            )}

            {/* Overlaid Badges on Top of Video */}
            {isRunning && (
              <>
                {/* Top-Left Live Status Badge */}
                <div className="absolute top-4 left-4 bg-slate-950/80 backdrop-blur border border-slate-800/80 px-3 py-1.5 rounded-lg flex items-center space-x-2 pointer-events-none">
                  <span className="w-2.5 h-2.5 rounded-full bg-rose-500 animate-ping" />
                  <span className="text-xs font-mono font-bold text-white tracking-wider">LIVE</span>
                  <span className="text-[10px] text-slate-400 font-mono">| {selectedCamera}</span>
                </div>

                {/* Top-Right Risk Alert Badge */}
                {liveTelemetry.risk_score >= 40 && (
                  <div className="absolute top-4 right-4 bg-rose-950/90 border border-rose-500 text-rose-200 px-3.5 py-1.5 rounded-lg flex items-center space-x-2 shadow-lg shadow-rose-950/50 animate-pulse pointer-events-none">
                    <span className="text-sm font-bold">⚠️ RISK ALERT:</span>
                    <span className="text-xs font-bold font-mono">
                      {liveTelemetry.risk_score >= 70 ? 'CRITICAL' : 'HIGH'} ({liveTelemetry.risk_score.toFixed(0)})
                    </span>
                  </div>
                )}

                {/* Bottom-Left Overlay Telemetry */}
                <div className="absolute bottom-4 left-4 bg-slate-950/80 backdrop-blur border border-slate-800/80 px-3 py-1.5 rounded-lg flex items-center space-x-3 text-[11px] font-mono pointer-events-none">
                  <span className="text-slate-400">
                    TRACKS: <strong className="text-emerald-400">{liveTelemetry.tracks.length}</strong>
                  </span>
                  <span className="text-slate-600">•</span>
                  <span className="text-slate-400">
                    IDENTITIES: <strong className="text-cyan-400">{liveTelemetry.identities.length}</strong>
                  </span>
                  <span className="text-slate-600">•</span>
                  <span className="text-slate-400">
                    RE-ID: <strong className="text-purple-400">{liveTelemetry.global_entities.length}</strong>
                  </span>
                </div>
              </>
            )}
          </div>
        </div>

        {/* RIGHT: LIVE INTELLIGENCE PANEL */}
        <div className="lg:col-span-4 space-y-4">
          <div className="bg-slate-900/90 backdrop-blur border border-slate-800 rounded-2xl p-4 shadow-xl h-[560px] flex flex-col">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h2 className="text-sm font-bold text-white font-['Outfit'] flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-cyan-400" />
                LIVE INTELLIGENCE STREAM
              </h2>
              <span className="text-[10px] font-mono text-slate-500 uppercase">Real-Time Telemetry</span>
            </div>

            <div className="flex-1 overflow-y-auto mt-3 space-y-4 pr-1 scrollbar-thin scrollbar-thumb-slate-700">
              {/* Section 1: Active Tracks */}
              <div>
                <h3 className="text-[11px] font-mono font-bold text-slate-400 uppercase tracking-wider mb-2">
                  Active Tracks ({liveTelemetry.tracks.length})
                </h3>
                {liveTelemetry.tracks.length > 0 ? (
                  <div className="space-y-1.5">
                    {liveTelemetry.tracks.map((t, idx) => (
                      <div
                        key={idx}
                        className="bg-slate-950/80 border border-slate-800 rounded-lg p-2 flex items-center justify-between text-xs font-mono"
                      >
                        <div className="flex items-center space-x-2">
                          <span className="w-2 h-2 rounded-full bg-emerald-400" />
                          <span className="text-white font-semibold">#{t.track_id} {t.class_name}</span>
                        </div>
                        <span className="text-cyan-400 font-bold">
                          {(t.confidence * 100).toFixed(0)}%
                        </span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-slate-600 italic">No active tracks in field of view</p>
                )}
              </div>

              {/* Section 2: Biometric Identities */}
              <div>
                <h3 className="text-[11px] font-mono font-bold text-slate-400 uppercase tracking-wider mb-2">
                  Face & Identity ({liveTelemetry.identities.length})
                </h3>
                {liveTelemetry.identities.length > 0 ? (
                  <div className="space-y-1.5">
                    {liveTelemetry.identities.map((id, idx) => (
                      <div
                        key={idx}
                        className="bg-slate-950/80 border border-slate-800 rounded-lg p-2 flex items-center justify-between text-xs font-mono"
                      >
                        <div>
                          <div className="text-white font-semibold flex items-center gap-1.5">
                            <span>👤</span>
                            <span>{id.name || 'UNKNOWN'}</span>
                          </div>
                          <span className="text-[10px] text-slate-500">Track #{id.track_id}</span>
                        </div>
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                            id.state === 'known' || id.name !== 'UNKNOWN'
                              ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                              : 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                          }`}
                        >
                          {id.state || 'UNKNOWN'}
                        </span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-slate-600 italic">No faces detected</p>
                )}
              </div>

              {/* Section 3: Re-ID & Global Entities */}
              <div>
                <h3 className="text-[11px] font-mono font-bold text-slate-400 uppercase tracking-wider mb-2">
                  Cross-Camera Re-ID ({liveTelemetry.global_entities.length})
                </h3>
                {liveTelemetry.global_entities.length > 0 ? (
                  <div className="space-y-1.5">
                    {liveTelemetry.global_entities.map((g, idx) => (
                      <div
                        key={idx}
                        className="bg-slate-950/80 border border-slate-800 rounded-lg p-2 flex items-center justify-between text-xs font-mono"
                      >
                        <span className="text-purple-300 font-bold">
                          Global #{g.global_entity_id?.slice(-6) || 'ENT'}
                        </span>
                        <span className="text-[10px] text-slate-400">
                          {g.num_cameras || 1} Camera(s) Linked
                        </span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-slate-600 italic">No cross-camera matches active</p>
                )}
              </div>

              {/* Section 4: Behavior & Events */}
              <div>
                <h3 className="text-[11px] font-mono font-bold text-slate-400 uppercase tracking-wider mb-2">
                  Behavior Observations ({liveTelemetry.behavior_events.length})
                </h3>
                {liveTelemetry.behavior_events.length > 0 ? (
                  <div className="space-y-1.5">
                    {liveTelemetry.behavior_events.map((b, idx) => (
                      <div
                        key={idx}
                        className="bg-amber-950/30 border border-amber-500/30 rounded-lg p-2 text-xs font-mono text-amber-200"
                      >
                        <span className="font-bold">{b.event_type}</span>
                        {b.zone_id && <span className="text-[10px] text-amber-400 ml-2">({b.zone_id})</span>}
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-slate-600 italic">Normal movement detected</p>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 3. BOTTOM TELEMETRY BAR & SCROLLING AUDIT TIMELINE */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Latency Breakdown Bar */}
        <div className="lg:col-span-5 bg-slate-900/90 backdrop-blur border border-slate-800 rounded-xl p-4 shadow-xl space-y-3">
          <div className="flex items-center justify-between border-b border-slate-800 pb-2">
            <h3 className="text-xs font-mono font-bold text-white uppercase">Pipeline Stage Timings (ms)</h3>
            <span className="text-[10px] font-mono text-cyan-400">Real-Time Profiler</span>
          </div>

          <div className="grid grid-cols-3 gap-2 text-xs font-mono">
            {Object.entries(liveTelemetry.stage_timings).length > 0 ? (
              Object.entries(liveTelemetry.stage_timings).map(([stg, lat]) => (
                <div key={stg} className="bg-slate-950 p-2 rounded border border-slate-800">
                  <div className="text-[10px] text-slate-500 uppercase truncate">{stg}</div>
                  <div className="text-white font-bold">{lat.toFixed(2)} ms</div>
                </div>
              ))
            ) : (
              ['detection', 'tracking', 'identity', 'reid', 'behavior', 'risk'].map((stg) => (
                <div key={stg} className="bg-slate-950 p-2 rounded border border-slate-800">
                  <div className="text-[10px] text-slate-500 uppercase">{stg}</div>
                  <div className="text-slate-400 font-bold">&lt; 0.5 ms</div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Scrolling Event Timeline */}
        <div className="lg:col-span-7 bg-slate-900/90 backdrop-blur border border-slate-800 rounded-xl p-4 shadow-xl space-y-3">
          <div className="flex items-center justify-between border-b border-slate-800 pb-2">
            <h3 className="text-xs font-mono font-bold text-white uppercase flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              Live Audit Event Stream ({events.length})
            </h3>
            <span className="text-[10px] font-mono text-slate-500">WebSocket Multiplex</span>
          </div>

          <div className="h-28 overflow-y-auto space-y-1.5 font-mono text-xs scrollbar-thin scrollbar-thumb-slate-700">
            {events.length > 0 ? (
              events.slice(0, 30).map((ev, idx) => (
                <div
                  key={idx}
                  className="bg-slate-950/60 p-1.5 rounded border border-slate-800/80 flex items-center justify-between text-[11px]"
                >
                  <div className="flex items-center space-x-2 truncate">
                    <span className="text-slate-500">{new Date(ev.timestamp * 1000).toLocaleTimeString()}</span>
                    <span className="text-cyan-400 font-bold">[{ev.event_type}]</span>
                    <span className="text-slate-300 truncate">
                      {ev.data?.message || ev.data?.headline || JSON.stringify(ev.data).slice(0, 50)}
                    </span>
                  </div>
                  <span className="text-[10px] text-slate-500 ml-2">{ev.camera_id}</span>
                </div>
              ))
            ) : (
              <p className="text-xs text-slate-600 italic py-4 text-center">
                Waiting for pipeline telemetry events...
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
