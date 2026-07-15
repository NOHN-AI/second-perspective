import { spawn } from 'child_process';
import * as path from 'path';
import * as vscode from 'vscode';
import { AuditReport, DecisionContext } from './auditTypes';

/**
 * Bridges the extension host to the LOCAL Python audit engine.
 * The engine runs as a subprocess (offline, neutral, no network).
 */
export class AuditBridge {
  constructor(private pythonPath: string, private engineDir: string) {}

  static fromConfig(): AuditBridge {
    const cfg = vscode.workspace.getConfiguration('causalAudit');
    const pythonPath =
      cfg.get<string>('pythonPath') ||
      (process.platform === 'win32' ? 'py' : 'python3');
    const engineDir =
      cfg.get<string>('engineDir') ||
      path.join(__dirname, '..', 'python-engine');
    return new AuditBridge(pythonPath, engineDir);
  }

  async audit(ctx: DecisionContext, timeoutMs = 15000): Promise<AuditReport> {
    const cli = path.join(this.engineDir, 'audit_cli.py');
    const strictness = vscode.workspace.getConfiguration('causalAudit').get<string>('strictness') || 'standard';
    return new Promise<AuditReport>((resolve, reject) => {
      const proc = spawn(this.pythonPath, [cli], {
        cwd: this.engineDir,
        env: { ...process.env, CA_STRICTNESS: strictness },
      });
      let out = '';
      let err = '';
      const timer = setTimeout(() => {
        proc.kill('SIGKILL');
        reject(new Error('audit engine timeout'));
      }, timeoutMs);

      proc.stdout.on('data', (d) => (out += d.toString()));
      proc.stderr.on('data', (d) => (err += d.toString()));
      proc.on('error', (e) => {
        clearTimeout(timer);
        reject(new Error(`failed to start audit engine: ${e.message}`));
      });
      proc.on('close', () => {
        clearTimeout(timer);
        if (err && !out) {
          reject(new Error(`audit engine error: ${err}`));
          return;
        }
        try {
          resolve(JSON.parse(out) as AuditReport);
        } catch (e) {
          reject(new Error(`invalid audit output: ${out || err}`));
        }
      });

      proc.stdin.write(JSON.stringify(ctx));
      proc.stdin.end();
    });
  }
}
