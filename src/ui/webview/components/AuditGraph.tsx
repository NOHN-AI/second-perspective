import * as React from 'react';
import { AuditReport } from '../../../audit/auditTypes';

const ROW_H = 72;
const D_X = 16;
const A_X = 300;
const DD_X = 540;
const NODE_W = 200;
const DD_W = 224;
const NODE_H = 44;
const W = DD_X + DD_W + 16;

export function AuditGraph({ report }: { report: AuditReport | null }) {
  if (!report) {
    return (
      <div className="empty">
        暂无审计结果。在「聊天」里点「审计此回复」，或在编辑器选中代码后右键「Causal Audit: Audit Selection」。
      </div>
    );
  }

  const D = report.decision?.D ?? '(无)';
  const assumptions = report.assumptions ?? [];
  const branches = report.branch_logic ?? [];
  const scores = report.imda_scores;
  const aCount = Math.max(assumptions.length, 1);
  const height = Math.max(240, aCount * ROW_H + 40);
  const dY = height / 2 - NODE_H / 2;

  const aY = (i: number) => 20 + i * ROW_H;

  return (
    <div className="graph-wrap">
      <div>
        <div className="section-title">因果结构 (D / A / ΔD)</div>
        <svg viewBox={`0 0 ${W} ${height}`} width="100%" style={{ maxWidth: W }}>
          {/* edges: D -> A_i */}
          {assumptions.map((a, i) => (
            <line
              key={'e' + a.id}
              className="edge"
              x1={D_X + NODE_W}
              y1={dY + NODE_H / 2}
              x2={A_X}
              y2={aY(i) + NODE_H / 2}
            />
          ))}
          {/* edges: A_i -> ΔD_i (branch, ¬A_i) */}
          {branches.map((b, i) => (
            <g key={'b' + i}>
              <line
                className="edge"
                style={{ strokeDasharray: '4 3', stroke: 'var(--warn)' }}
                x1={A_X + NODE_W}
                y1={aY(i) + NODE_H / 2}
                x2={DD_X}
                y2={aY(i) + NODE_H / 2}
              />
              <text className="edge-label" x={(A_X + NODE_W + DD_X) / 2} y={aY(i) + NODE_H / 2 - 6}>
                {b.if}
              </text>
            </g>
          ))}

          {/* D node */}
          <g>
            <rect className="node-d" x={D_X} y={dY} width={NODE_W} height={NODE_H} rx={6} />
            <text className="node-text" x={D_X + 10} y={dY + 18} fontWeight={700}>
              D · 决策
            </text>
            <text className="node-text" x={D_X + 10} y={dY + 34}>
              {D.length > 24 ? D.slice(0, 24) + '…' : D}
            </text>
          </g>

          {/* A nodes */}
          {assumptions.map((a, i) => (
            <g key={a.id}>
              <rect className="node-a" x={A_X} y={aY(i)} width={NODE_W} height={NODE_H} rx={6} />
              <text className="node-text" x={A_X + 10} y={aY(i) + 18} fontWeight={700}>
                {a.id} · 前提
              </text>
              <text className="node-text" x={A_X + 10} y={aY(i) + 34}>
                {a.text.length > 24 ? a.text.slice(0, 24) + '…' : a.text}
              </text>
            </g>
          ))}

          {/* ΔD nodes */}
          {branches.map((b, i) => (
            <g key={'dd' + i}>
              <rect className="node-dd" x={DD_X} y={aY(i)} width={DD_W} height={NODE_H} rx={6} />
              <text className="node-text" x={DD_X + 10} y={aY(i) + 18} fontWeight={700}>
                ΔD · 回退/修正
              </text>
              <text className="node-text" x={DD_X + 10} y={aY(i) + 34}>
                {b.response.length > 26 ? b.response.slice(0, 26) + '…' : b.response}
              </text>
            </g>
          ))}
        </svg>
      </div>

      <div>
        <div className="section-title">IMDA 分数 (本地离线)</div>
        {scores && (
          <div className="scores">
            <ScoreRow label="interpretability" val={scores.interpretability} />
            <ScoreRow label="robustness" val={scores.robustness} />
            <ScoreRow label="accountability" val={scores.accountability} />
            <ScoreRow label="inclusiveness" val={scores.inclusiveness} />
            <ScoreRow label="overall" val={scores.overall} bold />
          </div>
        )}
      </div>

      <div>
        <div className="section-title">审计结论</div>
        <p className="verdict" style={{ color: report.verdict ? 'var(--good)' : 'var(--bad)' }}>
          verdict = {String(report.verdict)} · overall = {report.overall_score}
        </p>
        {report.disclaimer && <p className="empty">{report.disclaimer}</p>}
      </div>
    </div>
  );
}

function ScoreRow({ label, val, bold }: { label: string; val: number; bold?: boolean }) {
  return (
    <div className="score-row">
      <span className="score-label">{label}</span>
      <span className="score-bar-bg">
        <span className="score-bar" style={{ width: `${val}%` }} />
      </span>
      <span className="score-val" style={bold ? { fontWeight: 700 } : undefined}>
        {val}
      </span>
    </div>
  );
}
