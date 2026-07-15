import * as vscode from 'vscode';
import { AuditBridge } from '../audit/auditBridge';
import { LlmAdapter } from '../llm/llmAdapter';

/** Inline completion: LLM proposes the next code; the audit layer is advisory here. */
export class AuditInlineCompletionProvider implements vscode.InlineCompletionItemProvider {
  constructor(private ctx: vscode.ExtensionContext, private bridge: AuditBridge) {}

  async provideInlineCompletionItems(
    document: vscode.TextDocument,
    position: vscode.Position,
    _context: vscode.InlineCompletionContext,
    token: vscode.CancellationToken
  ): Promise<vscode.InlineCompletionItem[]> {
    try {
      const prefix = document.getText(new vscode.Range(new vscode.Position(0, 0), position));
      const end = document.lineAt(document.lineCount - 1).range.end;
      const suffix = document.getText(new vscode.Range(position, end));
      const llm = await LlmAdapter.fromConfig(this.ctx.secrets);
      const text = await llm.complete(prefix, suffix, document.languageId);
      if (!text || token.isCancellationRequested) {
        return [];
      }
      return [new vscode.InlineCompletionItem(text, new vscode.Range(position, position))];
    } catch {
      return [];
    }
  }
}
