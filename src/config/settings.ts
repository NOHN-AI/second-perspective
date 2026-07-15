import * as vscode from 'vscode';

const SECRET_KEY = 'causalAudit.apiKey';

/** Thin wrapper over VS Code settings + SecretStorage (API key never in plaintext settings). */
export class Settings {
  constructor(private ctx: vscode.ExtensionContext) {}

  get config(): vscode.WorkspaceConfiguration {
    return vscode.workspace.getConfiguration('causalAudit');
  }

  async getApiKey(): Promise<string> {
    const fromSecret = await this.ctx.secrets.get(SECRET_KEY);
    if (fromSecret) {
      return fromSecret;
    }
    return this.config.get<string>('apiKey') || '';
  }

  async setApiKey(key: string): Promise<void> {
    await this.ctx.secrets.store(SECRET_KEY, key);
  }

  get enforceAuditBeforeApply(): boolean {
    return this.config.get<boolean>('enforceAuditBeforeApply') ?? true;
  }
}
