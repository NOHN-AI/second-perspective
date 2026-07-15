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
exports.AuditStore = void 0;
const vscode = __importStar(require("vscode"));
/** Persisted audit history (globalState) shared by the sidebar webview. */
class AuditStore {
    constructor(ctx) {
        this.ctx = ctx;
        this.key = 'causalAudit.history';
        this._onDidAdd = new vscode.EventEmitter();
        this.onDidAdd = this._onDidAdd.event;
    }
    add(entry) {
        const full = {
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
    all() {
        return this.ctx.globalState.get(this.key, []);
    }
}
exports.AuditStore = AuditStore;
//# sourceMappingURL=auditStore.js.map