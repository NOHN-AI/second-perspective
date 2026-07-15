import * as vscode from 'vscode';
import { AuditBridge } from '../audit/auditBridge';
import { LlmAdapter } from '../llm/llmAdapter';
import { AuditStore } from '../audit/auditStore';
import { AuditReport } from '../audit/auditTypes';
import { Settings } from '../config/settings';
import { FromExtension, ToExtension, StatusSnapshot } from './messages';

/**
 * Single sidebar webview that hosts the chat / causal-graph / history UI.
 * Replaces the previous trio of (status tree, history tree, separate panel).
 */
export class AuditViewProvider implements vscode.WebviewViewProvider {
  public static readonly viewId = 'secondPerspective.audit';

  private view: vscode.WebviewView | undefined;
  private pendingReport: AuditReport | undefined;

  constructor(
    private readonly ctx: vscode.ExtensionContext,
    private readonly bridge: AuditBridge,
    private readonly store: AuditStore,
    private readonly settings: Settings
  ) {
    // Whenever a new audit is recorded, push the report to the webview
    // and refresh the history list. The webview may not exist yet —
    // pendingReport buffers the next show until the view resolves.
    this._disposables.push(this.store.onDidAdd((entry) => this.handleNewEntry(entry)));
  }

  private _disposables: vscode.Disposable[] = [];

  resolveWebviewView(webviewView: vscode.WebviewView): void {
    this.view = webviewView;
    webviewView.webview.options = {
      enableScripts: true,
      localResourceRoots: [vscode.Uri.joinPath(this.ctx.extensionUri, 'dist')],
    };
    webviewView.webview.html = this.getHtml(webviewView.webview);

    webviewView.onDidDispose(() => {
      this.view = undefined;
    });

    webviewView.webview.onDidReceiveMessage((msg: ToExtension) => {
      this.handleMessage(msg).catch((e) => this.postError(e));
    });

    // Flush queued report once the view is alive.
    if (this.pendingReport) {
      this.postMessage({ type: 'showReport', report: this.pendingReport });
      this.pendingReport = undefined;
    }
  }

  /** Push a fresh audit report. Reveal the sidebar first so the user sees it. */
  pushReport(report: AuditReport): void {
    if (this.view) {
      this.postMessage({ type: 'showReport', report });
    } else {
      this.pendingReport = report;
    }
  }

  /** Make sure the sidebar view is visible. */
  async reveal(): Promise<void> {
    await vscode.commands.executeCommand(
      `workbench.view.extension.${AuditViewProvider.viewId.split('.')[0]}`
    );
  }

  /** Triggered by the title-bar refresh button: re-push history + status. */
  async requestRefresh(): Promise<void> {
    if (!this.view) {
      return;
    }
    this.postMessage({ type: 'history', entries: this.store.all() });
    this.postMessage({ type: 'status', snapshot: await this.collectStatus() });
  }

  dispose(): void {
    this._disposables.forEach((d) => d.dispose());
  }

  // ---- internals ----

  private handleNewEntry(entry: { report: AuditReport }) {
    this.postMessage({ type: 'history', entries: this.store.all() });
    this.pushReport(entry.report);
  }

  private async handleMessage(msg: ToExtension): Promise<void> {
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
      case 'saveLlmConfig': {
        const apiKey = msg.config.apiKey;
        if (apiKey) {
          await this.settings.setApiKey(apiKey);
        }
        const providerMap: Record<string, string> = { openai: 'openai', anthropic: 'anthropic', ollama: 'ollama', custom: 'custom' };
        await this.settings.config.update('llmProvider', providerMap[msg.config.provider] || 'openai', true);
        await this.settings.config.update('baseUrl', msg.config.baseUrl, true);
        await this.settings.config.update('model', msg.config.model, true);
        this.postMessage({ type: 'llmConfigSaved', success: true });
        this.postMessage({ type: 'status', snapshot: await this.collectStatus() });
        return;
      }

      case 'chat': {
        const llm = await LlmAdapter.fromConfig(this.ctx.secrets);
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

  private postMessage(msg: FromExtension) {
    this.view?.webview.postMessage(msg);
  }

  private postError(e: unknown) {
    this.postMessage({ type: 'error', message: String((e as Error)?.message ?? e) });
  }

  private async collectStatus(): Promise<StatusSnapshot> {
    const cfg = this.settings.config;
    const baseUrl = cfg.get<string>('baseUrl') || 'https://api.openai.com/v1';
    const model = cfg.get<string>('model') || 'gpt-4o-mini';
    const provider = cfg.get<string>('llmProvider') || 'openai';
    const fromSecret = !!(await this.ctx.secrets.get('causalAudit.apiKey'));
    const fromSettings = !!cfg.get<string>('apiKey');
    const apiKeySource: StatusSnapshot['apiKeySource'] = fromSecret
      ? 'secret'
      : fromSettings
      ? 'settings'
      : 'none';
    let engine: StatusSnapshot['engine'] = 'ok';
    try {
      // Quick engine probe; ignore the result, just check it doesn't throw.
      await this.bridge.audit({ decision: '__ping__', context: '', metadata: {} });
    } catch {
      engine = 'offline';
    }
    return {
      engine,
      auditLayer: 'ready',
      llm: apiKeySource === 'none' ? 'missing' : 'configured',
      provider,
      apiKeySource,
      baseUrl,
      model,
    };
  }

  private getHtml(webview: vscode.Webview): string {
    const scriptUri = webview.asWebviewUri(
      vscode.Uri.joinPath(this.ctx.extensionUri, 'dist', 'webview.js')
    );
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

  private nonce(): string {
    const c = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
    let t = '';
    for (let i = 0; i < 32; i++) {
      t += c.charAt(Math.floor(Math.random() * c.length));
    }
    return t;
  }
}
