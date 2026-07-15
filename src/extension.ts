import * as vscode from 'vscode';
import { AuditBridge } from './audit/auditBridge';
import { AuditStore } from './audit/auditStore';
import { Settings } from './config/settings';
import { AuditViewProvider } from './ui/auditViewProvider';
import { AuditInlineCompletionProvider } from './features/completionProvider';
import { runRefactor } from './features/refactorProvider';

export function activate(context: vscode.ExtensionContext) {
  const settings = new Settings(context);
  const bridge = AuditBridge.fromConfig();
  const store = new AuditStore(context);

  const viewProvider = new AuditViewProvider(context, bridge, store, settings);
  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider(AuditViewProvider.viewId, viewProvider, {
      webviewOptions: { retainContextWhenHidden: true },
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand('secondPerspective.refresh', () => {
      viewProvider.requestRefresh();
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand('secondPerspective.configure', async () => {
      const key = await vscode.window.showInputBox({
        prompt: '输入 LLM API Key（存入 SecretStorage，不落明文）',
        password: true,
      });
      if (key) {
        await settings.setApiKey(key);
        vscode.window.showInformationMessage('API Key 已存入 SecretStorage。下次聊天生效。');
      }
    })
  );

  // Local, offline audit of the current selection -> store + push to sidebar view.
  context.subscriptions.push(
    vscode.commands.registerCommand('secondPerspective.auditSelection', async () => {
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
      } catch (e: any) {
        vscode.window.showErrorMessage(`审计失败: ${e.message ?? e}`);
      }
    })
  );

  // LLM refactor of the selection, then local audit + diff before apply.
  context.subscriptions.push(
    vscode.commands.registerCommand('secondPerspective.refactorSelection', () =>
      runRefactor(context, bridge, store, settings, viewProvider)
    )
  );

  // Inline completion (LLM-generated proposal; audit is advisory at the inline stage).
  context.subscriptions.push(
    vscode.languages.registerInlineCompletionItemProvider(
      { pattern: '**' },
      new AuditInlineCompletionProvider(context, bridge)
    )
  );
}

export function deactivate() {}
