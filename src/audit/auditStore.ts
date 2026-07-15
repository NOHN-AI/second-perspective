import * as vscode from 'vscode';
import { HistoryEntry } from '../ui/messages';

/** Persisted audit history (globalState) shared by the sidebar webview. */
export class AuditStore {
  private key = 'causalAudit.history';
  private _onDidAdd = new vscode.EventEmitter<HistoryEntry>();
  readonly onDidAdd: vscode.Event<HistoryEntry> = this._onDidAdd.event;

  constructor(private ctx: vscode.ExtensionContext) {}

  add(entry: Omit<HistoryEntry, 'id' | 'ts'>): HistoryEntry {
    const full: HistoryEntry = {
      ...entry,
      id: Date.now().toString(36) + Math.random().toString(36).slice(2, 6),
      ts: Date.now(),
    };
    const list = this.all();
    list.unshift(full);
    void this.ctx.globalState.update(this.key, list.slice(0, 200));
    this._onDidAdd.fire(full);
    return full;
  }

  all(): HistoryEntry[] {
    return this.ctx.globalState.get<HistoryEntry[]>(this.key, []);
  }
}
