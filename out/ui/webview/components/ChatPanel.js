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
exports.ChatPanel = ChatPanel;
const jsx_runtime_1 = require("react/jsx-runtime");
const React = __importStar(require("react"));
function ChatPanel({ messages, onSend, onAudit, busy }) {
    const [text, setText] = React.useState('');
    const endRef = React.useRef(null);
    React.useEffect(() => {
        endRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);
    const submit = () => {
        const t = text.trim();
        if (!t || busy)
            return;
        onSend(t);
        setText('');
    };
    return ((0, jsx_runtime_1.jsxs)("div", { className: "chat", children: [(0, jsx_runtime_1.jsxs)("div", { className: "messages", children: [messages.map((m, i) => ((0, jsx_runtime_1.jsxs)("div", { className: 'msg ' + m.role, children: [m.content, m.role === 'assistant' && i > 0 && ((0, jsx_runtime_1.jsx)("div", { className: "meta", children: (0, jsx_runtime_1.jsx)("button", { className: "audit-btn", onClick: () => onAudit(m.content), children: "\u5BA1\u8BA1\u6B64\u56DE\u590D" }) }))] }, i))), (0, jsx_runtime_1.jsx)("div", { ref: endRef })] }), (0, jsx_runtime_1.jsxs)("div", { className: "composer", children: [(0, jsx_runtime_1.jsx)("textarea", { value: text, placeholder: "\u5411 LLM \u63D0\u95EE\u2026\uFF08Enter \u53D1\u9001\uFF0CShift+Enter \u6362\u884C\uFF09", onChange: (e) => setText(e.target.value), onKeyDown: (e) => {
                            if (e.key === 'Enter' && !e.shiftKey) {
                                e.preventDefault();
                                submit();
                            }
                        } }), (0, jsx_runtime_1.jsx)("button", { className: "send", disabled: busy || !text.trim(), onClick: submit, children: "\u53D1\u9001" })] })] }));
}
//# sourceMappingURL=ChatPanel.js.map