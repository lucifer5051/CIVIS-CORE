import React, { useEffect, useState } from 'react';
import { Header } from './components/Header';
import { DashboardPage } from './pages/DashboardPage';
import { ConfigPage } from './pages/ConfigPage';
import { useWebSocket } from './hooks/useWebSocket';
import {
  CameraStatus,
  EvidenceItem,
  HealthResponse,
  IdentityItem,
  ReIDEntityItem,
  RiskAlertItem,
  RiskAssessmentItem,
  RuntimeStatusResponse,
  TrackItem,
} from './types';
import { api } from './api/client';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'dashboard' | 'config'>('dashboard');
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [detailedHealth, setDetailedHealth] = useState<Record<string, any> | null>(null);
  const [cameras, setCameras] = useState<CameraStatus[]>([]);
  const [risks, setRisks] = useState<RiskAssessmentItem[]>([]);
  const [alerts, setAlerts] = useState<RiskAlertItem[]>([]);
  const [evidenceList, setEvidenceList] = useState<EvidenceItem[]>([]);
  const [tracks, setTracks] = useState<TrackItem[]>([]);
  const [identities, setIdentities] = useState<IdentityItem[]>([]);
  const [reidEntities, setReidEntities] = useState<ReIDEntityItem[]>([]);
  const [runtimeStatus, setRuntimeStatus] = useState<RuntimeStatusResponse | null>(null);

  // WebSocket Live Stream with automatic reconnection
  const wsUrl = `ws://${window.location.host}/ws/events`;
  const { events, connectionState, clearEvents } = useWebSocket({ url: wsUrl });

  const fetchData = async () => {
    try {
      const [
        h,
        dh,
        cams,
        rsk,
        alt,
        ev,
        trk,
        id,
        reid,
        rt,
      ] = await Promise.all([
        api.getHealth().catch(() => null),
        api.getDetailedHealth().catch(() => null),
        api.getCameras().catch(() => []),
        api.getRisks().catch(() => []),
        api.getRiskAlerts().catch(() => []),
        api.getEvidence().catch(() => []),
        api.getTracks().catch(() => []),
        api.getIdentities().catch(() => []),
        api.getReIDEntities().catch(() => []),
        api.getRuntimeStatus().catch(() => null),
      ]);

      if (h) setHealth(h);
      if (dh) setDetailedHealth(dh);
      setCameras(cams);
      setRisks(rsk);
      setAlerts(alt);
      setEvidenceList(ev);
      setTracks(trk);
      setIdentities(id);
      setReidEntities(reid);
      if (rt) setRuntimeStatus(rt);
    } catch (err) {
      console.error('Error fetching dashboard data:', err);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 3000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-cyan-500 selection:text-slate-950">
      <Header
        health={health}
        wsState={connectionState}
        activeTab={activeTab}
        onTabChange={setActiveTab}
      />

      <main className="flex-1 overflow-x-hidden">
        {activeTab === 'dashboard' ? (
          <DashboardPage
            cameras={cameras}
            risks={risks}
            alerts={alerts}
            evidenceList={evidenceList}
            tracks={tracks}
            identities={identities}
            reidEntities={reidEntities}
            runtimeStatus={runtimeStatus}
            detailedHealth={detailedHealth}
            events={events}
            onClearEvents={clearEvents}
            onRefreshData={fetchData}
          />
        ) : (
          <ConfigPage />
        )}
      </main>
    </div>
  );
};

export default App;
