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
exports.activate = activate;
exports.deactivate = deactivate;
const vscode = __importStar(require("vscode"));
const auditBridge_1 = require("./audit/auditBridge");
const auditStore_1 = require("./audit/auditStore");
const settings_1 = require("./config/settings");
const auditViewProvider_1 = require("./ui/auditViewProvider");
const completionProvider_1 = require("./features/completionProvider");
const refactorProvider_1 = require("./features/refactorProvider");
function activate(context) {
    const settings = new settings_1.Settings(context);
    const bridge = auditBridge_1.AuditBridge.fromConfig();
    const store = new auditStore_1.AuditStore(context);
    const viewProvider = new auditViewProvider_1.AuditViewProvider(context, bridge, store, settings);
    context.subscriptions.push(vscode.window.registerWebviewViewProvider(auditViewProvider_1.AuditViewProvider.viewId, viewProvider, {
        webviewOptions: { retainContextWhenHidden: true },
    }));
    context.subscriptions.push(vscode.commands.registerCommand('secondPerspective.refresh', () => {
        viewProvider.requestRefresh();
    }));
    context.subscriptions.push(vscode.commands.registerCommand('secondPerspective.configure', async () => {
        const key = await vscode.window.showInputBox({
            prompt: '输入 LLM API Key（存入 SecretStorage，不落明文）',
            password: true,
        });
        if (key) {
            await settings.setApiKey(key);
            vscode.window.showInformationMessage('API Key 已存入 SecretStorage。下次聊天生效。');
        }
    }));
    // Local, offline audit of the current selection -> store + push to sidebar view.
    context.subscriptions.push(vscode.commands.registerCommand('secondPerspective.auditSelection', async () => {
        const editor = vscode.window.activeTextEditor;
        if (!editor) {
            return;
        }
        const text = editor.document.getText(editor.selection);
        if (!text) {
            vscode.window.showWarningMessage('请先选中代码再审计。');
            return;
        }
        try {
            const report = await bridge.audit({
                decision: text,
                context: '',
                metadata: { source: 'chat' },
            });
            store.add({
                source: 'chat',
                verdict: !!report.verdict,
                overall: report.overall_score ?? 0,
                decision: text.slice(0, 200),
                report,
            });
            await viewProvider.reveal();
            // store.onDidAdd inside AuditViewProvider will push history + report
        }
        catch (e) {
            vscode.window.showErrorMessage(`审计失败: ${e.message ?? e}`);
        }
    }));
    // LLM refactor of the selection, then local audit + diff before apply.
    context.subscriptions.push(vscode.commands.registerCommand('secondPerspective.refactorSelection', () => (0, refactorProvider_1.runRefactor)(context, bridge, store, settings, viewProvider)));
    // Inline completion (LLM-generated proposal; audit is advisory at the inline stage).
    context.subscriptions.push(vscode.languages.registerInlineCompletionItemProvider({ pattern: '**' }, new completionProvider_1.AuditInlineCompletionProvider(context, bridge)));
}
function deactivate() { }
//# sourceMappingURL=extension.js.map