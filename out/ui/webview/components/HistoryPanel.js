"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.HistoryPanel = HistoryPanel;
const jsx_runtime_1 = require("react/jsx-runtime");
function HistoryPanel({ entries, onSelect }) {
    if (!entries.length) {
        return (0, jsx_runtime_1.jsx)("div", { className: "empty", children: "\u8FD8\u6CA1\u6709\u5BA1\u8BA1\u8BB0\u5F55\u3002" });
    }
    return ((0, jsx_runtime_1.jsx)("div", { children: entries.map((e) => ((0, jsx_runtime_1.jsxs)("div", { className: "hist-item", onClick: () => onSelect(e), children: [(0, jsx_runtime_1.jsx)("div", { children: e.decision.length > 80 ? e.decision.slice(0, 80) + '…' : e.decision }), (0, jsx_runtime_1.jsxs)("div", { className: "hist-meta", children: [(0, jsx_runtime_1.jsx)("span", { children: new Date(e.ts).toLocaleString() }), (0, jsx_runtime_1.jsx)("span", { className: "verdict", style: { color: e.verdict ? 'var(--good)' : 'var(--bad)' }, children: e.verdict ? '通过' : '未通过' }), (0, jsx_runtime_1.jsxs)("span", { children: ["overall ", e.overall] }), (0, jsx_runtime_1.jsx)("span", { children: e.source })] })] }, e.id))) }));
}
//# sourceMappingURL=HistoryPanel.js.map