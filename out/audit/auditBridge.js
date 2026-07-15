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
exports.AuditBridge = void 0;
const child_process_1 = require("child_process");
const path = __importStar(require("path"));
const vscode = __importStar(require("vscode"));
/**
 * Bridges the extension host to the LOCAL Python audit engine.
 * The engine runs as a subprocess (offline, neutral, no network).
 */
class AuditBridge {
    constructor(pythonPath, engineDir) {
        this.pythonPath = pythonPath;
        this.engineDir = engineDir;
    }
    static fromConfig() {
        const cfg = vscode.workspace.getConfiguration('causalAudit');
        const pythonPath = cfg.get('pythonPath') ||
            (process.platform === 'win32' ? 'py' : 'python3');
        const engineDir = cfg.get('engineDir') ||
            path.join(__dirname, '..', 'python-engine');
        return new AuditBridge(pythonPath, engineDir);
    }
    async audit(ctx, timeoutMs = 15000) {
        const cli = path.join(this.engineDir, 'audit_cli.py');
        const strictness = vscode.workspace.getConfiguration('causalAudit').get('strictness') || 'standard';
        return new Promise((resolve, reject) => {
            const proc = (0, child_process_1.spawn)(this.pythonPath, [cli], {
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
                    resolve(JSON.parse(out));
                }
                catch (e) {
                    reject(new Error(`invalid audit output: ${out || err}`));
                }
            });
            proc.stdin.write(JSON.stringify(ctx));
            proc.stdin.end();
        });
    }
}
exports.AuditBridge = AuditBridge;
//# sourceMappingURL=auditBridge.js.map