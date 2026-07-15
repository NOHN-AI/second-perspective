import * as React from 'react';
import { HistoryEntry } from '../../messages';

interface Props {
  entries: HistoryEntry[];
  onSelect: (e: HistoryEntry) => void;
}

export function HistoryPanel({ entries, onSelect }: Props) {
  if (!entries.length) {
    return <div className="empty">还没有审计记录。</div>;
  }
  return (
    <div>
      {entries.map((e) => (
        <div key={e.id} className="hist-item" onClick={() => onSelect(e)}>
          <div>{e.decision.length > 80 ? e.decision.slice(0, 80) + '…' : e.decision}</div>
          <div className="hist-meta">
            <span>{new Date(e.ts).toLocaleString()}</span>
            <span className="verdict" style={{ color: e.verdict ? 'var(--good)' : 'var(--bad)' }}>
              {e.verdict ? '通过' : '未通过'}
            </span>
            <span>overall {e.overall}</span>
            <span>{e.source}</span>
          </div>
        </div>
      ))}
    </div>
  );
}
