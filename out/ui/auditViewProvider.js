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
exports.AuditViewProvider = void 0;
const vscode = __importStar(require("vscode"));
const llmAdapter_1 = require("../llm/llmAdapter");
/**
 * Single sidebar webview that hosts the chat / causal-graph / history UI.
 * Replaces the previous trio of (status tree, history tree, separate panel).
 */
class AuditViewProvider {
    constructor(ctx, bridge, store, settings) {
        this.ctx = ctx;
        this.bridge = bridge;
        this.store = store;
        this.settings = settings;
        this._disposables = [];
        // Whenever a new audit is recorded, push the report to the webview
        // and refresh the history list. The webview may not exist yet —
        // pendingReport buffers the next show until the view resolves.
        this._disposables.push(this.store.onDidAdd((entry) => this.handleNewEntry(entry)));
    }
    resolveWebviewView(webviewView) {
        this.view = webviewView;
        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [vscode.Uri.joinPath(this.ctx.extensionUri, 'dist')],
        };
        webviewView.webview.html = this.getHtml(webviewView.webview);
        webviewView.onDidDispose(() => {
            this.view = undefined;
        });
        webviewView.webview.onDidReceiveMessage((msg) => {
            this.handleMessage(msg).catch((e) => this.postError(e));
        });
        // Flush queued report once the view is alive.
        if (this.pendingReport) {
            this.postMessage({ type: 'showReport', report: this.pendingReport });
            this.pendingReport = undefined;
        }
    }
    /** Push a fresh audit report. Reveal the sidebar first so the user sees it. */
    pushReport(report) {
        if (this.view) {
            this.postMessage({ type: 'showReport', report });
        }
        else {
            this.pendingReport = report;
        }
    }
    /** Make sure the sidebar view is visible. */
    async reveal() {
        await vscode.commands.executeCommand(`workbench.view.extension.${AuditViewProvider.viewId.split('.')[0]}`);
    }
    /** Triggered by the title-bar refresh button: re-push history + status. */
    async requestRefresh() {
        if (!this.view) {
            return;
        }
        this.postMessage({ type: 'history', entries: this.store.all() });
        this.postMessage({ type: 'status', snapshot: await this.collectStatus() });
    }
    dispose() {
        this._disposables.forEach((d) => d.dispose());
    }
    // ---- internals ----
    handleNewEntry(entry) {
        this.postMessage({ type: 'history', entries: this.store.all() });
        this.pushReport(entry.report);
    }
    async handleMessage(msg) {
        switch (msg.type) {
            case 'ready':
            case 'requestHistory': {
                this.postMessage({ type: 'history', entries: this.store.all() });
                this.postMessage({ type: 'status', snapshot: await this.collectStatus() });
                if (this.pendingReport) {
                    this.postMessage({ type: 'showReport', report: this.pendingReport });
                    this.pendingReport = undefined;
                }
                return;
            }
            case 'requestStatus': {
                this.postMessage({ type: 'status', snapshot: await this.collectStatus() });
                return;
            }
            case 'chat': {
                const llm = await llmAdapter_1.LlmAdapter.fromConfig(this.ctx.secrets);
                const text = await llm.chat(msg.messages);
                this.postMessage({ type: 'chatResponse', requestId: msg.requestId, content: text });
                return;
            }
            case 'audit': {
                const report = await this.bridge.audit({
                    decision: msg.decision,
                    context: msg.context ?? '',
                    metadata: { source: msg.source ?? 'chat' },
                });
                this.store.add({
                    source: msg.source ?? 'chat',
                    verdict: !!report.verdict,
                    overall: report.overall_score ?? 0,
                    decision: msg.decision.slice(0, 200),
                    report,
                });
                // store.onDidAdd will push history + showReport
                return;
            }
        }
    }
    postMessage(msg) {
        this.view?.webview.postMessage(msg);
    }
    postError(e) {
        this.postMessage({ type: 'error', message: String(e?.message ?? e) });
    }
    async collectStatus() {
        const cfg = this.settings.config;
        const baseUrl = cfg.get('baseUrl') || 'https://api.openai.com/v1';
        const model = cfg.get('model') || 'gpt-4o-mini';
        const fromSecret = !!(await this.ctx.secrets.get('causalAudit.apiKey'));
        const fromSettings = !!cfg.get('apiKey');
        const apiKeySource = fromSecret
            ? 'secret'
            : fromSettings
                ? 'settings'
                : 'none';
        let engine = 'ok';
        try {
            // Quick engine probe; ignore the result, just check it doesn't throw.
            await this.bridge.audit({ decision: '__ping__', context: '', metadata: {} });
        }
        catch {
            engine = 'offline';
        }
        return {
            engine,
            auditLayer: 'ready',
            llm: apiKeySource === 'none' ? 'missing' : 'configured',
            apiKeySource,
            baseUrl,
            model,
        };
    }
    getHtml(webview) {
        const scriptUri = webview.asWebviewUri(vscode.Uri.joinPath(this.ctx.extensionUri, 'dist', 'webview.js'));
        const nonce = this.nonce();
        return `<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8"/>
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src ${webview.cspSource} https: data:; style-src ${webview.cspSource} 'unsafe-inline'; script-src ${webview.cspSource} 'nonce-${nonce}';"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
</head>
<body>
<div id="root"></div>
<script nonce="${nonce}" src="${scriptUri}"></script>
</body>
</html>`;
    }
    nonce() {
        const c = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
        let t = '';
        for (let i = 0; i < 32; i++) {
            t += c.charAt(Math.floor(Math.random() * c.length));
        }
        return t;
    }
}
exports.AuditViewProvider = AuditViewProvider;
AuditViewProvider.viewId = 'secondPerspective.audit';
//# sourceMappingURL=auditViewProvider.js.map