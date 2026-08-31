import {
  CameraStatus,
  CorrelatedEventItem,
  EvidenceItem,
  EvidenceVerifyResponse,
  HealthResponse,
  IdentityItem,
  ReIDEntityItem,
  RiskAlertItem,
  RiskAssessmentItem,
  RuntimeStatusResponse,
  TrackItem,
} from '../types';

export class CivisApiClient {
  private baseUrl: string;
  private apiKey: string | null;

  constructor(baseUrl: string = '', apiKey: string | null = null) {
    this.baseUrl = baseUrl.replace(/\/$/, '');
    this.apiKey = apiKey;
  }

  public setApiKey(key: string | null) {
    this.apiKey = key;
  }

  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const url = `${this.baseUrl}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(options.headers as Record<string, string>),
    };

    if (this.apiKey) {
      headers['X-API-Key'] = this.apiKey;
    }

    const response = await fetch(url, { ...options, headers });
    if (!response.ok) {
      let errMessage = `HTTP error ${response.status}`;
      try {
        const errJson = await response.json();
        if (errJson.detail) errMessage = errJson.detail;
      } catch {
        // Fallback
      }
      throw new Error(errMessage);
    }
    return response.json();
  }

  // Health
  async getHealth(): Promise<HealthResponse> {
    return this.request<HealthResponse>('/health');
  }

  async getDetailedHealth(): Promise<Record<string, any>> {
    return this.request<Record<string, any>>('/health/detailed');
  }

  // Cameras
  async getCameras(): Promise<CameraStatus[]> {
    return this.request<CameraStatus[]>('/cameras');
  }

  async startCamera(cameraId: string): Promise<any> {
    return this.request(`/cameras/${encodeURIComponent(cameraId)}/start`, { method: 'POST' });
  }

  async stopCamera(cameraId: string): Promise<any> {
    return this.request(`/cameras/${encodeURIComponent(cameraId)}/stop`, { method: 'POST' });
  }

  async pauseCamera(cameraId: string): Promise<any> {
    return this.request(`/cameras/${encodeURIComponent(cameraId)}/pause`, { method: 'POST' });
  }

  async resumeCamera(cameraId: string): Promise<any> {
    return this.request(`/cameras/${encodeURIComponent(cameraId)}/resume`, { method: 'POST' });
  }

  // Analytics
  async getTracks(cameraId?: string): Promise<TrackItem[]> {
    const query = cameraId ? `?camera_id=${encodeURIComponent(cameraId)}` : '';
    return this.request<TrackItem[]>(`/tracks${query}`);
  }

  async getIdentities(cameraId?: string): Promise<IdentityItem[]> {
    const query = cameraId ? `?camera_id=${encodeURIComponent(cameraId)}` : '';
    return this.request<IdentityItem[]>(`/identities${query}`);
  }

  async getReIDEntities(): Promise<ReIDEntityItem[]> {
    return this.request<ReIDEntityItem[]>('/reid/entities');
  }

  async getEvents(severity?: string): Promise<CorrelatedEventItem[]> {
    const query = severity ? `?severity=${encodeURIComponent(severity)}` : '';
    return this.request<CorrelatedEventItem[]>(`/events${query}`);
  }

  async getRisks(severity?: string): Promise<RiskAssessmentItem[]> {
    const query = severity ? `?severity=${encodeURIComponent(severity)}` : '';
    return this.request<RiskAssessmentItem[]>(`/risks${query}`);
  }

  async getRiskAlerts(): Promise<RiskAlertItem[]> {
    return this.request<RiskAlertItem[]>('/risks/alerts');
  }

  // Evidence
  async getEvidence(cameraId?: string): Promise<EvidenceItem[]> {
    const query = cameraId ? `?camera_id=${encodeURIComponent(cameraId)}` : '';
    return this.request<EvidenceItem[]>(`/evidence${query}`);
  }

  async verifyEvidence(evidenceId: string): Promise<EvidenceVerifyResponse> {
    return this.request<EvidenceVerifyResponse>(`/evidence/${encodeURIComponent(evidenceId)}/verify`);
  }

  // Runtime
  async getRuntimeStatus(): Promise<RuntimeStatusResponse> {
    return this.request<RuntimeStatusResponse>('/runtime/status');
  }

  async startRuntime(): Promise<any> {
    return this.request('/runtime/start', { method: 'POST' });
  }

  async stopRuntime(): Promise<any> {
    return this.request('/runtime/stop', { method: 'POST' });
  }

  // Config
  async getConfig(): Promise<Record<string, any>> {
    return this.request<Record<string, any>>('/config');
  }

  async getConfigSnapshot(): Promise<Record<string, any>> {
    return this.request<Record<string, any>>('/config/snapshot');
  }
}

export const api = new CivisApiClient('/api');
