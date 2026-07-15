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
exports.AuditInlineCompletionProvider = void 0;
const vscode = __importStar(require("vscode"));
const llmAdapter_1 = require("../llm/llmAdapter");
/** Inline completion: LLM proposes the next code; the audit layer is advisory here. */
class AuditInlineCompletionProvider {
    constructor(ctx, bridge) {
        this.ctx = ctx;
        this.bridge = bridge;
    }
    async provideInlineCompletionItems(document, position, _context, token) {
        try {
            const prefix = document.getText(new vscode.Range(new vscode.Position(0, 0), position));
            const end = document.lineAt(document.lineCount - 1).range.end;
            const suffix = document.getText(new vscode.Range(position, end));
            const llm = await llmAdapter_1.LlmAdapter.fromConfig(this.ctx.secrets);
            const text = await llm.complete(prefix, suffix, document.languageId);
            if (!text || token.isCancellationRequested) {
                return [];
            }
            return [new vscode.InlineCompletionItem(text, new vscode.Range(position, position))];
        }
        catch {
            return [];
        }
    }
}
exports.AuditInlineCompletionProvider = AuditInlineCompletionProvider;
//# sourceMappingURL=completionProvider.js.map