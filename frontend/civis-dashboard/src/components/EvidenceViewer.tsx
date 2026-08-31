import React, { useState } from 'react';
import { EvidenceItem, EvidenceVerifyResponse } from '../types';
import { api } from '../api/client';

interface EvidenceViewerProps {
  evidenceList: EvidenceItem[];
  onRefresh?: () => void;
}

export const EvidenceViewer: React.FC<EvidenceViewerProps> = ({ evidenceList, onRefresh }) => {
  const [verifyingId, setVerifyingId] = useState<string | null>(null);
  const [verifyResult, setVerifyResult] = useState<Record<string, EvidenceVerifyResponse>>({});

  const handleVerify = async (evidenceId: string) => {
    try {
      setVerifyingId(evidenceId);
      const res = await api.verifyEvidence(evidenceId);
      setVerifyResult((prev) => ({ ...prev, [evidenceId]: res }));
    } catch (err: any) {
      alert(`Verification failed: ${err.message}`);
    } finally {
      setVerifyingId(null);
    }
  };

  return (
    <div className="bg-slate-900/70 backdrop-blur border border-slate-800 rounded-xl flex flex-col h-full overflow-hidden shadow-lg">
      <div className="px-4 py-3 border-b border-slate-800 flex items-center justify-between bg-slate-950/40">
        <div className="flex items-center space-x-2">
          <div className="w-2 h-2 rounded-full bg-emerald-400" />
          <h2 className="text-sm font-semibold text-white tracking-wide font-['Outfit']">Forensic Evidence Ledger</h2>
        </div>
        {onRefresh && (
          <button
            onClick={onRefresh}
            className="text-[10px] font-mono text-slate-400 hover:text-white px-2 py-1 rounded hover:bg-slate-800 transition-colors"
          >
            Refresh
          </button>
        )}
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-2 font-mono text-xs">
        {evidenceList.length === 0 ? (
          <div className="text-center py-8 text-slate-500 text-xs">
            No forensic evidence records logged.
          </div>
        ) : (
          evidenceList.map((ev) => {
            const vRes = verifyResult[ev.evidence_id];
            return (
              <div
                key={ev.evidence_id}
                className="bg-slate-950/60 border border-slate-800/80 rounded-lg p-3 space-y-2 hover:border-slate-700 transition-colors"
              >
                <div className="flex items-center justify-between">
                  <span className="text-cyan-400 font-bold">{ev.evidence_id}</span>
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-900 text-slate-400 border border-slate-800 uppercase">
                    {ev.source_type}
                  </span>
                </div>

                <div className="text-[10px] text-slate-400 break-all bg-slate-900 p-1.5 rounded border border-slate-800/60">
                  SHA-256: {ev.sha256_hash}
                </div>

                <div className="flex items-center justify-between pt-1">
                  <span className="text-[10px] text-slate-400">
                    {new Date(ev.timestamp * 1000).toLocaleString()}
                  </span>
                  <button
                    onClick={() => handleVerify(ev.evidence_id)}
                    disabled={verifyingId === ev.evidence_id}
                    className="px-2 py-1 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 text-[10px] font-semibold hover:bg-cyan-500/30 transition-all disabled:opacity-50"
                  >
                    {verifyingId === ev.evidence_id ? 'Verifying...' : 'Verify Hash'}
                  </button>
                </div>

                {vRes && (
                  <div
                    className={`mt-2 p-2 rounded text-[10px] border ${
                      vRes.is_valid
                        ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                        : 'bg-rose-500/10 text-rose-400 border-rose-500/30'
                    }`}
                  >
                    {vRes.message}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
