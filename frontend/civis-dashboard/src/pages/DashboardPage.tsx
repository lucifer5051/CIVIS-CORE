import React, { useState } from 'react';
import { CameraGrid } from '../components/CameraGrid';
import { RiskPanel } from '../components/RiskPanel';
import { EventTimeline } from '../components/EventTimeline';
import { CameraDetailModal } from '../components/CameraDetailModal';
import { EntityDetailModal } from '../components/EntityDetailModal';
import { EvidenceViewer } from '../components/EvidenceViewer';
import { RuntimeControls } from '../components/RuntimeControls';
import { SystemDiagnostics } from '../components/SystemDiagnostics';
import {
  CameraStatus,
  EvidenceItem,
  IdentityItem,
  PipelineEventMessage,
  ReIDEntityItem,
  RiskAlertItem,
  RiskAssessmentItem,
  RuntimeStatusResponse,
  TrackItem,
} from '../types';
import { api } from '../api/client';

interface DashboardPageProps {
  cameras: CameraStatus[];
  risks: RiskAssessmentItem[];
  alerts: RiskAlertItem[];
  evidenceList: EvidenceItem[];
  tracks: TrackItem[];
  identities: IdentityItem[];
  reidEntities: ReIDEntityItem[];
  runtimeStatus: RuntimeStatusResponse | null;
  detailedHealth: Record<string, any> | null;
  events: PipelineEventMessage[];
  onClearEvents: () => void;
  onRefreshData: () => void;
}

export const DashboardPage: React.FC<DashboardPageProps> = ({
  cameras,
  risks,
  alerts,
  evidenceList,
  tracks,
  identities,
  reidEntities,
  runtimeStatus,
  detailedHealth,
  events,
  onClearEvents,
  onRefreshData,
}) => {
  const [selectedCameraId, setSelectedCameraId] = useState<string | null>(null);
  const [selectedEntityKey, setSelectedEntityKey] = useState<string | null>(null);

  const selectedCamera = cameras.find((c) => c.camera_id === selectedCameraId) || null;

  // Find entity track/identity/reid details
  const entityTrack = tracks.find((t) => `${t.camera_id}_tr_${t.track_id}` === selectedEntityKey) || null;
  const entityIdentity = identities.find((i) => i.camera_id === selectedCameraId) || null;
  const entityReID = reidEntities.find((r) => r.camera_id === selectedCameraId) || null;

  const handleStartCamera = async (camId: string) => {
    await api.startCamera(camId);
    onRefreshData();
  };

  const handleStopCamera = async (camId: string) => {
    await api.stopCamera(camId);
    onRefreshData();
  };

  const handlePauseCamera = async (camId: string) => {
    await api.pauseCamera(camId);
    onRefreshData();
  };

  const handleResumeCamera = async (camId: string) => {
    await api.resumeCamera(camId);
    onRefreshData();
  };

  const handleStartRuntime = async () => {
    await api.startRuntime();
    onRefreshData();
  };

  const handleStopRuntime = async () => {
    await api.stopRuntime();
    onRefreshData();
  };

  return (
    <div className="p-6 space-y-6">
      {/* Top Runtime Controls & Diagnostics */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <RuntimeControls
            runtimeStatus={runtimeStatus}
            onStartRuntime={handleStartRuntime}
            onStopRuntime={handleStopRuntime}
          />
        </div>
        <div>
          <SystemDiagnostics detailedHealth={detailedHealth} />
        </div>
      </div>

      {/* Center Grid: Video Feeds & Risk Assessments */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold uppercase tracking-wider text-slate-300 font-mono">
              Live Surveillance Grid
            </h2>
            <span className="text-xs font-mono text-slate-500">
              Click a feed to configure controls
            </span>
          </div>
          <CameraGrid
            cameras={cameras}
            selectedCameraId={selectedCameraId}
            onSelectCamera={setSelectedCameraId}
          />
        </div>

        <div>
          <RiskPanel
            risks={risks}
            alerts={alerts}
            onSelectEntity={setSelectedEntityKey}
          />
        </div>
      </div>

      {/* Bottom Row: Live Event Timeline & Forensic Evidence Ledger */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 h-96">
        <EventTimeline
          events={events}
          onClear={onClearEvents}
        />
        <EvidenceViewer
          evidenceList={evidenceList}
          onRefresh={onRefreshData}
        />
      </div>

      {/* Modals */}
      <CameraDetailModal
        camera={selectedCamera}
        onClose={() => setSelectedCameraId(null)}
        onStart={handleStartCamera}
        onStop={handleStopCamera}
        onPause={handlePauseCamera}
        onResume={handleResumeCamera}
      />

      <EntityDetailModal
        entityKey={selectedEntityKey}
        track={entityTrack}
        identity={entityIdentity}
        reidEntity={entityReID}
        onClose={() => setSelectedEntityKey(null)}
      />
    </div>
  );
};
