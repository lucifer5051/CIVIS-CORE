import React from 'react';
import { RiskAlertItem, RiskAssessmentItem, SeverityLevel } from '../types';

interface RiskPanelProps {
  risks: RiskAssessmentItem[];
  alerts: RiskAlertItem[];
  onSelectEntity?: (entityKey: string) => void;
  onSelectEvidence?: (evidenceId: string) => void;
}

const severityOrder: Record<SeverityLevel, number> = {
  critical: 4,
  high: 3,
  medium: 2,
  low: 1,
};

const severityBadgeStyles: Record<SeverityLevel, string> = {
  critical: 'bg-rose-500/20 text-rose-400 border-rose-500/40 ring-1 ring-rose-500/30',
  high: 'bg-orange-500/20 text-orange-400 border-orange-500/40',
  medium: 'bg-amber-500/20 text-amber-400 border-amber-500/40',
  low: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/40',
};

export const RiskPanel: React.FC<RiskPanelProps> = ({
  risks,
  alerts,
  onSelectEntity,
}) => {
  // Sort assessments highest severity and score first
  const sortedRisks = [...risks].sort((a, b) => {
    const diff = (severityOrder[b.severity] || 0) - (severityOrder[a.severity] || 0);
    return diff !== 0 ? diff : b.overall_score - a.overall_score;
  });

  return (
    <div className="bg-slate-900/70 backdrop-blur border border-slate-800 rounded-xl flex flex-col h-full overflow-hidden shadow-lg">
      <div className="px-4 py-3 border-b border-slate-800 flex items-center justify-between bg-slate-950/40">
        <div className="flex items-center space-x-2">
          <div className="w-2 h-2 rounded-full bg-rose-500 animate-pulse" />
          <h2 className="text-sm font-semibold text-white tracking-wide font-['Outfit']">Explainable Risk Feed</h2>
        </div>
        <div className="flex items-center space-x-2">
          {alerts.length > 0 && (
            <span className="text-xs font-mono px-2 py-0.5 rounded bg-rose-950 border border-rose-500/50 text-rose-300 font-bold">
              {alerts.length} Alerts
            </span>
          )}
          <span className="text-xs font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300">
            {sortedRisks.length} Assessments
          </span>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-3 divide-y divide-slate-800/40">
        {sortedRisks.length === 0 ? (
          <div className="text-center py-8 text-slate-500 text-xs font-mono">
            No elevated security risks detected.
          </div>
        ) : (
          sortedRisks.map((rsk) => (
            <div
              key={rsk.assessment_id}
              className="pt-3 first:pt-0 group hover:bg-slate-800/30 p-2.5 rounded-lg transition-colors cursor-pointer"
              onClick={() => onSelectEntity && onSelectEntity(rsk.entity_key)}
            >
              <div className="flex items-start justify-between gap-2 mb-1.5">
                <span
                  className={`text-[10px] uppercase font-mono font-bold px-2 py-0.5 rounded border ${
                    severityBadgeStyles[rsk.severity] || severityBadgeStyles.low
                  }`}
                >
                  {rsk.severity} ({(rsk.overall_score * 100).toFixed(0)}%)
                </span>
                <span className="text-[10px] font-mono text-slate-400">
                  {new Date(rsk.timestamp * 1000).toLocaleTimeString()}
                </span>
              </div>

              <h4 className="text-xs font-semibold text-slate-200 mb-1 leading-snug">{rsk.summary}</h4>

              <div className="flex items-center justify-between text-[10px] font-mono text-slate-400 mt-2">
                <span className="bg-slate-950 px-2 py-0.5 rounded border border-slate-800 text-cyan-400">
                  {rsk.camera_id}
                </span>
                <span className="bg-slate-950 px-2 py-0.5 rounded border border-slate-800 text-slate-300">
                  {rsk.entity_key}
                </span>
                <span className="text-emerald-400">Conf: {(rsk.confidence * 100).toFixed(0)}%</span>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
