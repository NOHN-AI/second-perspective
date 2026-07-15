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
exports.Settings = void 0;
const vscode = __importStar(require("vscode"));
const SECRET_KEY = 'causalAudit.apiKey';
/** Thin wrapper over VS Code settings + SecretStorage (API key never in plaintext settings). */
class Settings {
    constructor(ctx) {
        this.ctx = ctx;
    }
    get config() {
        return vscode.workspace.getConfiguration('causalAudit');
    }
    async getApiKey() {
        const fromSecret = await this.ctx.secrets.get(SECRET_KEY);
        if (fromSecret) {
            return fromSecret;
        }
        return this.config.get('apiKey') || '';
    }
    async setApiKey(key) {
        await this.ctx.secrets.store(SECRET_KEY, key);
    }
    get enforceAuditBeforeApply() {
        return this.config.get('enforceAuditBeforeApply') ?? true;
    }
}
exports.Settings = Settings;
//# sourceMappingURL=settings.js.map