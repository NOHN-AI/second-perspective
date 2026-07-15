"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.App = App;
const jsx_runtime_1 = require("react/jsx-runtime");
const React = __importStar(require("react"));
const vscodeApi_1 = require("./vscodeApi");
const ChatPanel_1 = require("./components/ChatPanel");
const AuditGraph_1 = require("./components/AuditGraph");
const HistoryPanel_1 = require("./components/HistoryPanel");
function App() {
    const [tab, setTab] = React.useState('chat');
    const [messages, setMessages] = React.useState([
        {
            role: 'assistant',
            content: '我是第二视角因果审计副驾。提问会发给 LLM 生成，本地离线引擎对输出做因果审计（D/A/ΔD，¬A⇒ΔD）。点「审计此回复」查看因果图。',
        },
    ]);
    const [report, setReport] = React.useState(null);
    const [history, setHistory] = React.useState([]);
    const [status, setStatus] = React.useState(null);
    const [error, setError] = React.useState(null);
    const [sending, setSending] = React.useState(false);
    React.useEffect(() => {
        const handler = (e) => {
            const m = e.data;
            switch (m.type) {
                case 'chatResponse':
                    setMessages((prev) => [...prev, { role: 'assistant', content: m.content }]);
                    setSending(false);
                    break;
                case 'chatError':
                    setError(m.message);
                    setSending(false);
                    break;
                case 'auditResult':
                    setReport(m.report);
                    setTab('graph');
                    break;
                case 'showReport':
                    setReport(m.report);
                    setTab('graph');
                    break;
                case 'history':
                    setHistory(m.entries);
                    break;
                case 'status':
                    setStatus(m.snapshot);
                    break;
                case 'error':
                    setError(m.message);
                    break;
            }
        };
        window.addEventListener('message', handler);
        vscodeApi_1.vscode.postMessage({ type: 'ready' });
        return () => window.removeEventListener('message', handler);
    }, []);
    const sendChat = (text) => {
        if (sending)
            return;
        const next = [...messages, { role: 'user', content: text }];
        setMessages(next);
        setSending(true);
        vscodeApi_1.vscode.postMessage({ type: 'chat', messages: next, requestId: Date.now().toString(36) });
    };
    const auditMessage = (content) => {
        vscodeApi_1.vscode.postMessage({ type: 'audit', decision: content, source: 'chat' });
    };
    const refreshStatus = () => {
        vscodeApi_1.vscode.postMessage({ type: 'requestStatus' });
    };
    return ((0, jsx_runtime_1.jsxs)("div", { className: "app", children: [(0, jsx_runtime_1.jsx)(StatusBar, { status: status, onRefresh: refreshStatus }), (0, jsx_runtime_1.jsxs)("div", { className: "tabs", children: [(0, jsx_runtime_1.jsx)("div", { className: 'tab' + (tab === 'chat' ? ' active' : ''), onClick: () => setTab('chat'), children: "\u804A\u5929" }), (0, jsx_runtime_1.jsx)("div", { className: 'tab' + (tab === 'graph' ? ' active' : ''), onClick: () => setTab('graph'), children: "\u56E0\u679C\u56FE" }), (0, jsx_runtime_1.jsxs)("div", { className: 'tab' + (tab === 'history' ? ' active' : ''), onClick: () => setTab('history'), children: ["\u5386\u53F2", history.length > 0 && (0, jsx_runtime_1.jsx)("span", { className: "badge", children: history.length })] })] }), (0, jsx_runtime_1.jsxs)("div", { className: "content", children: [error && ((0, jsx_runtime_1.jsxs)("div", { className: "error", children: ["\u9519\u8BEF\uFF1A", error, (0, jsx_runtime_1.jsx)("button", { className: "link", onClick: () => setError(null), children: "\u00D7" })] })), tab === 'chat' && ((0, jsx_runtime_1.jsx)(ChatPanel_1.ChatPanel, { messages: messages, onSend: sendChat, onAudit: auditMessage, busy: sending })), tab === 'graph' && (0, jsx_runtime_1.jsx)(AuditGraph_1.AuditGraph, { report: report }), tab === 'history' && ((0, jsx_runtime_1.jsx)(HistoryPanel_1.HistoryPanel, { entries: history, onSelect: (e) => {
                            setReport(e.report);
                            setTab('graph');
                        } }))] })] }));
}
function StatusBar({ status, onRefresh, }) {
    const engineCls = status?.engine === 'ok' ? 'pill ok' : status?.engine === 'offline' ? 'pill bad' : 'pill warn';
    const auditCls = status?.auditLayer === 'ready' ? 'pill ok' : 'pill warn';
    const llmCls = status?.llm === 'configured' ? 'pill ok' : 'pill bad';
    return ((0, jsx_runtime_1.jsxs)("div", { className: "status-bar", children: [(0, jsx_runtime_1.jsxs)("span", { className: engineCls, title: "\u672C\u5730 Python \u5BA1\u8BA1\u5F15\u64CE", children: ["\u5F15\u64CE ", status ? status.engine : '…'] }), (0, jsx_runtime_1.jsx)("span", { className: auditCls, title: "\u56E0\u679C\u5BA1\u8BA1\u5C42 D/A/\u0394D", children: "\u5BA1\u8BA1\u5C42" }), (0, jsx_runtime_1.jsxs)("span", { className: llmCls, title: `${status?.baseUrl ?? ''} · ${status?.model ?? ''}`, children: ["LLM ", status ? status.llm : '…'] }), (0, jsx_runtime_1.jsx)("button", { className: "link", onClick: onRefresh, title: "\u5237\u65B0\u72B6\u6001", children: "\u21BB" })] }));
}
//# sourceMappingURL=App.js.map