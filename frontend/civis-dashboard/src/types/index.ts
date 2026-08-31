export type SeverityLevel = 'low' | 'medium' | 'high' | 'critical';

export interface HealthResponse {
  status: string;
  uptime_seconds: number;
  timestamp: number;
  active_cameras: number;
  total_cameras: number;
}

export interface CameraStatus {
  camera_id: string;
  is_running: boolean;
  is_paused: boolean;
  processed_frames: number;
  dropped_frames: number;
  current_fps: number;
  error_count: number;
}

export interface DetectionItem {
  detection_id: string;
  camera_id: string;
  class_name: string;
  class_id: number;
  confidence: number;
  bbox: [number, number, number, number];
  timestamp: number;
}

export interface TrackItem {
  track_id: number;
  camera_id: string;
  class_name: string;
  confidence: number;
  bbox: [number, number, number, number];
  age: number;
  hits: number;
  timestamp: number;
}

export interface IdentityItem {
  identity_id: string;
  camera_id: string;
  track_id: number;
  name: string;
  confidence: number;
  status: string;
  timestamp: number;
}

export interface ReIDEntityItem {
  global_id: string;
  camera_id: string;
  track_id: number;
  similarity: number;
  matched_global_id?: string;
  timestamp: number;
}

export interface BehaviorEventItem {
  behavior_type: string;
  camera_id: string;
  track_id: number;
  confidence: number;
  duration_frames: number;
  timestamp: number;
}

export interface CorrelatedEventItem {
  event_id: string;
  event_type: string;
  camera_id: string;
  confidence: number;
  severity: SeverityLevel;
  timestamp: number;
  summary: string;
}

export interface RiskAssessmentItem {
  assessment_id: string;
  camera_id: string;
  entity_key: string;
  overall_score: number;
  severity: SeverityLevel;
  confidence: number;
  summary: string;
  timestamp: number;
}

export interface RiskAlertItem {
  alert_id: string;
  assessment_id: string;
  camera_id: string;
  severity: SeverityLevel;
  confidence: number;
  explanation: string;
  timestamp: number;
}

export interface EvidenceItem {
  evidence_id: string;
  camera_id: string;
  source_type: string;
  sha256_hash: string;
  timestamp: number;
  verified: boolean;
  metadata: Record<string, any>;
}

export interface EvidenceVerifyResponse {
  evidence_id: string;
  is_valid: boolean;
  computed_hash: string;
  stored_hash: string;
  message: string;
}

export interface RuntimeStatusResponse {
  state: string;
  uptime_seconds: number;
  active_cameras: number;
  total_cameras: number;
  per_camera_status: Record<string, {
    is_running: boolean;
    is_paused: boolean;
    processed_frames: number;
    dropped_frames: number;
  }>;
}

export interface PipelineEventMessage {
  event_type: string;
  camera_id: string;
  timestamp: number;
  data: Record<string, any>;
}
