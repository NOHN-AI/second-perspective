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
exports.runRefactor = runRefactor;
const vscode = __importStar(require("vscode"));
const fs = __importStar(require("fs"));
const os = __importStar(require("os"));
const path = __importStar(require("path"));
const llmAdapter_1 = require("../llm/llmAdapter");
/** Refactor the selection via LLM, audit locally, show a diff, then optionally apply. */
async function runRefactor(ctx, bridge, store, settings, viewProvider) {
    const editor = vscode.window.activeTextEditor;
    if (!editor) {
        return;
    }
    const selection = editor.selection;
    const code = editor.document.getText(selection);
    if (!code) {
        vscode.window.showWarningMessage('请先选中代码再重构。');
        return;
    }
    const instruction = await vscode.window.showInputBox({ prompt: '重构指令', value: '提升可读性' });
    if (!instruction) {
        return;
    }
    try {
        const llm = await llmAdapter_1.LlmAdapter.fromConfig(ctx.secrets);
        const rewritten = await llm.refactor(code, instruction, editor.document.languageId);
        const report = await bridge.audit({
            decision: rewritten,
            context: code,
            metadata: { source: 'refactor', language: editor.document.languageId },
        });
        store.add({
            source: 'refactor',
            verdict: !!report.verdict,
            overall: report.overall_score ?? 0,
            decision: code.slice(0, 200),
            report,
        });
        await viewProvider.reveal();
        // store.onDidAdd inside AuditViewProvider will push history + showReport
        if (settings.enforceAuditBeforeApply && report.verdict === false) {
            vscode.window.showWarningMessage(`审计未通过 (overall=${report.overall_score})，已阻止自动应用。可在侧边栏因果图查看原因。`);
        }
        const ext = editor.document.languageId;
        const origPath = path.join(os.tmpdir(), `causal-audit-orig-${Date.now()}.${ext}`);
        const newPath = path.join(os.tmpdir(), `causal-audit-new-${Date.now()}.${ext}`);
        fs.writeFileSync(origPath, code);
        fs.writeFileSync(newPath, rewritten);
        await vscode.commands.executeCommand('vscode.diff', vscode.Uri.file(origPath), vscode.Uri.file(newPath), 'Causal Audit · 重构对比');
        const apply = await vscode.window.showInformationMessage(`重构完成 (verdict=${report.verdict}, overall=${report.overall_score})。是否替换选区？`, { modal: false }, '替换', '仅查看');
        if (apply === '替换') {
            await editor.edit((b) => b.replace(selection, rewritten));
        }
        try {
            fs.unlinkSync(origPath);
            fs.unlinkSync(newPath);
        }
        catch {
            /* ignore */
        }
    }
    catch (e) {
        vscode.window.showErrorMessage(`重构失败: ${e.message}`);
    }
}
//# sourceMappingURL=refactorProvider.js.map