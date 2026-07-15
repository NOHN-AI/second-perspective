import * as vscode from 'vscode';
import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { AuditBridge } from '../audit/auditBridge';
import { LlmAdapter } from '../llm/llmAdapter';
import { Settings } from '../config/settings';
import { AuditStore } from '../audit/auditStore';
import { AuditViewProvider } from '../ui/auditViewProvider';

/** Refactor the selection via LLM, audit locally, show a diff, then optionally apply. */
export async function runRefactor(
  ctx: vscode.ExtensionContext,
  bridge: AuditBridge,
  store: AuditStore,
  settings: Settings,
  viewProvider: AuditViewProvider
) {
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
    const llm = await LlmAdapter.fromConfig(ctx.secrets);
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
      vscode.window.showWarningMessage(
        `审计未通过 (overall=${report.overall_score})，已阻止自动应用。可在侧边栏因果图查看原因。`
      );
    }

    const ext = editor.document.languageId;
    const origPath = path.join(os.tmpdir(), `causal-audit-orig-${Date.now()}.${ext}`);
    const newPath = path.join(os.tmpdir(), `causal-audit-new-${Date.now()}.${ext}`);
    fs.writeFileSync(origPath, code);
    fs.writeFileSync(newPath, rewritten);
    await vscode.commands.executeCommand(
      'vscode.diff',
      vscode.Uri.file(origPath),
      vscode.Uri.file(newPath),
      'Causal Audit · 重构对比'
    );

    const apply = await vscode.window.showInformationMessage(
      `重构完成 (verdict=${report.verdict}, overall=${report.overall_score})。是否替换选区？`,
      { modal: false },
      '替换',
      '仅查看'
    );
    if (apply === '替换') {
      await editor.edit((b) => b.replace(selection, rewritten));
    }
    try {
      fs.unlinkSync(origPath);
      fs.unlinkSync(newPath);
    } catch {
      /* ignore */
    }
  } catch (e: any) {
    vscode.window.showErrorMessage(`重构失败: ${e.message}`);
  }
}
