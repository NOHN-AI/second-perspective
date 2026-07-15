"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.AuditGraph = AuditGraph;
const jsx_runtime_1 = require("react/jsx-runtime");
const ROW_H = 72;
const D_X = 16;
const A_X = 300;
const DD_X = 540;
const NODE_W = 200;
const DD_W = 224;
const NODE_H = 44;
const W = DD_X + DD_W + 16;
function AuditGraph({ report }) {
    if (!report) {
        return ((0, jsx_runtime_1.jsx)("div", { className: "empty", children: "\u6682\u65E0\u5BA1\u8BA1\u7ED3\u679C\u3002\u5728\u300C\u804A\u5929\u300D\u91CC\u70B9\u300C\u5BA1\u8BA1\u6B64\u56DE\u590D\u300D\uFF0C\u6216\u5728\u7F16\u8F91\u5668\u9009\u4E2D\u4EE3\u7801\u540E\u53F3\u952E\u300CCausal Audit: Audit Selection\u300D\u3002" }));
    }
    const D = report.decision?.D ?? '(无)';
    const assumptions = report.assumptions ?? [];
    const branches = report.branch_logic ?? [];
    const scores = report.imda_scores;
    const aCount = Math.max(assumptions.length, 1);
    const height = Math.max(240, aCount * ROW_H + 40);
    const dY = height / 2 - NODE_H / 2;
    const aY = (i) => 20 + i * ROW_H;
    return ((0, jsx_runtime_1.jsxs)("div", { className: "graph-wrap", children: [(0, jsx_runtime_1.jsxs)("div", { children: [(0, jsx_runtime_1.jsx)("div", { className: "section-title", children: "\u56E0\u679C\u7ED3\u6784 (D / A / \u0394D)" }), (0, jsx_runtime_1.jsxs)("svg", { viewBox: `0 0 ${W} ${height}`, width: "100%", style: { maxWidth: W }, children: [assumptions.map((a, i) => ((0, jsx_runtime_1.jsx)("line", { className: "edge", x1: D_X + NODE_W, y1: dY + NODE_H / 2, x2: A_X, y2: aY(i) + NODE_H / 2 }, 'e' + a.id))), branches.map((b, i) => ((0, jsx_runtime_1.jsxs)("g", { children: [(0, jsx_runtime_1.jsx)("line", { className: "edge", style: { strokeDasharray: '4 3', stroke: 'var(--warn)' }, x1: A_X + NODE_W, y1: aY(i) + NODE_H / 2, x2: DD_X, y2: aY(i) + NODE_H / 2 }), (0, jsx_runtime_1.jsx)("text", { className: "edge-label", x: (A_X + NODE_W + DD_X) / 2, y: aY(i) + NODE_H / 2 - 6, children: b.if })] }, 'b' + i))), (0, jsx_runtime_1.jsxs)("g", { children: [(0, jsx_runtime_1.jsx)("rect", { className: "node-d", x: D_X, y: dY, width: NODE_W, height: NODE_H, rx: 6 }), (0, jsx_runtime_1.jsx)("text", { className: "node-text", x: D_X + 10, y: dY + 18, fontWeight: 700, children: "D \u00B7 \u51B3\u7B56" }), (0, jsx_runtime_1.jsx)("text", { className: "node-text", x: D_X + 10, y: dY + 34, children: D.length > 24 ? D.slice(0, 24) + '…' : D })] }), assumptions.map((a, i) => ((0, jsx_runtime_1.jsxs)("g", { children: [(0, jsx_runtime_1.jsx)("rect", { className: "node-a", x: A_X, y: aY(i), width: NODE_W, height: NODE_H, rx: 6 }), (0, jsx_runtime_1.jsxs)("text", { className: "node-text", x: A_X + 10, y: aY(i) + 18, fontWeight: 700, children: [a.id, " \u00B7 \u524D\u63D0"] }), (0, jsx_runtime_1.jsx)("text", { className: "node-text", x: A_X + 10, y: aY(i) + 34, children: a.text.length > 24 ? a.text.slice(0, 24) + '…' : a.text })] }, a.id))), branches.map((b, i) => ((0, jsx_runtime_1.jsxs)("g", { children: [(0, jsx_runtime_1.jsx)("rect", { className: "node-dd", x: DD_X, y: aY(i), width: DD_W, height: NODE_H, rx: 6 }), (0, jsx_runtime_1.jsx)("text", { className: "node-text", x: DD_X + 10, y: aY(i) + 18, fontWeight: 700, children: "\u0394D \u00B7 \u56DE\u9000/\u4FEE\u6B63" }), (0, jsx_runtime_1.jsx)("text", { className: "node-text", x: DD_X + 10, y: aY(i) + 34, children: b.response.length > 26 ? b.response.slice(0, 26) + '…' : b.response })] }, 'dd' + i)))] })] }), (0, jsx_runtime_1.jsxs)("div", { children: [(0, jsx_runtime_1.jsx)("div", { className: "section-title", children: "IMDA \u5206\u6570 (\u672C\u5730\u79BB\u7EBF)" }), scores && ((0, jsx_runtime_1.jsxs)("div", { className: "scores", children: [(0, jsx_runtime_1.jsx)(ScoreRow, { label: "interpretability", val: scores.interpretability }), (0, jsx_runtime_1.jsx)(ScoreRow, { label: "robustness", val: scores.robustness }), (0, jsx_runtime_1.jsx)(ScoreRow, { label: "accountability", val: scores.accountability }), (0, jsx_runtime_1.jsx)(ScoreRow, { label: "inclusiveness", val: scores.inclusiveness }), (0, jsx_runtime_1.jsx)(ScoreRow, { label: "overall", val: scores.overall, bold: true })] }))] }), (0, jsx_runtime_1.jsxs)("div", { children: [(0, jsx_runtime_1.jsx)("div", { className: "section-title", children: "\u5BA1\u8BA1\u7ED3\u8BBA" }), (0, jsx_runtime_1.jsxs)("p", { className: "verdict", style: { color: report.verdict ? 'var(--good)' : 'var(--bad)' }, children: ["verdict = ", String(report.verdict), " \u00B7 overall = ", report.overall_score] }), report.disclaimer && (0, jsx_runtime_1.jsx)("p", { className: "empty", children: report.disclaimer })] })] }));
}
function ScoreRow({ label, val, bold }) {
    return ((0, jsx_runtime_1.jsxs)("div", { className: "score-row", children: [(0, jsx_runtime_1.jsx)("span", { className: "score-label", children: label }), (0, jsx_runtime_1.jsx)("span", { className: "score-bar-bg", children: (0, jsx_runtime_1.jsx)("span", { className: "score-bar", style: { width: `${val}%` } }) }), (0, jsx_runtime_1.jsx)("span", { className: "score-val", style: bold ? { fontWeight: 700 } : undefined, children: val })] }));
}
//# sourceMappingURL=AuditGraph.js.map