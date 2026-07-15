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
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.LlmAdapter = void 0;
const openai_1 = __importDefault(require("openai"));
const vscode = __importStar(require("vscode"));
/**
 * OpenAI-compatible LLM adapter. The base URL is overridable so the same
 * code serves OpenAI, Azure OpenAI, and local models (Ollama / vLLM / LM Studio).
 * The adapter ONLY generates; it never decides. Audit is the local engine's job.
 */
class LlmAdapter {
    constructor(opts) {
        this.client = new openai_1.default({ apiKey: opts.apiKey, baseURL: opts.baseUrl });
        this.model = opts.model;
        this.temperature = opts.temperature ?? 0.2;
        this.maxTokens = opts.maxTokens ?? 2048;
    }
    static async fromConfig(secrets) {
        const cfg = vscode.workspace.getConfiguration('causalAudit');
        const apiKey = (await secrets.get('causalAudit.apiKey')) || cfg.get('apiKey') || '';
        if (!apiKey) {
            throw new Error('LLM API key 未配置（SecretStorage: causalAudit.apiKey）');
        }
        const baseUrl = cfg.get('baseUrl') || 'https://api.openai.com/v1';
        const model = cfg.get('model') || 'gpt-4o-mini';
        const temperature = cfg.get('temperature') ?? 0.2;
        const maxTokens = cfg.get('maxTokens') ?? 2048;
        return new LlmAdapter({ apiKey, baseUrl, model, temperature, maxTokens });
    }
    async chat(messages) {
        const resp = await this.client.chat.completions.create({
            model: this.model,
            messages: messages,
            temperature: this.temperature,
            max_tokens: this.maxTokens,
        });
        return resp.choices[0]?.message?.content ?? '';
    }
    async complete(prefix, suffix, language) {
        const system = `你是一个代码补全引擎。只输出紧接着的代码片段，不要解释，不要 markdown 代码块。语言: ${language}。`;
        const user = `前文:\n${prefix}\n\n后文:\n${suffix}\n\n请补全中间部分:`;
        return this.chat([
            { role: 'system', content: system },
            { role: 'user', content: user },
        ]);
    }
    async refactor(code, instruction, language) {
        const system = `你是一个重构引擎。输出完整重构后的代码，不要解释，不要 markdown 代码块。语言: ${language}。`;
        const user = `重构指令: ${instruction}\n\n原代码:\n${code}`;
        return this.chat([
            { role: 'system', content: system },
            { role: 'user', content: user },
        ]);
    }
}
exports.LlmAdapter = LlmAdapter;
//# sourceMappingURL=llmAdapter.js.map