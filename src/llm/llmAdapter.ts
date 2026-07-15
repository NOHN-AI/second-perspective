import OpenAI from 'openai';
import * as vscode from 'vscode';

export type ChatRole = 'system' | 'user' | 'assistant';
export interface ChatMessage {
  role: ChatRole;
  content: string;
}

/**
 * OpenAI-compatible LLM adapter. The base URL is overridable so the same
 * code serves OpenAI, Azure OpenAI, and local models (Ollama / vLLM / LM Studio).
 * The adapter ONLY generates; it never decides. Audit is the local engine's job.
 */
export class LlmAdapter {
  private client: OpenAI;
  private model: string;
  private temperature: number;
  private maxTokens: number;

  constructor(opts: {
    apiKey: string;
    baseUrl: string;
    model: string;
    temperature?: number;
    maxTokens?: number;
  }) {
    this.client = new OpenAI({ apiKey: opts.apiKey, baseURL: opts.baseUrl });
    this.model = opts.model;
    this.temperature = opts.temperature ?? 0.2;
    this.maxTokens = opts.maxTokens ?? 2048;
  }

  static async fromConfig(secrets: vscode.SecretStorage): Promise<LlmAdapter> {
    const cfg = vscode.workspace.getConfiguration('causalAudit');
    const apiKey =
      (await secrets.get('causalAudit.apiKey')) || cfg.get<string>('apiKey') || '';
    if (!apiKey) {
      throw new Error('LLM API key 未配置（SecretStorage: causalAudit.apiKey）');
    }
    const baseUrl = cfg.get<string>('baseUrl') || 'https://api.openai.com/v1';
    const model = cfg.get<string>('model') || 'gpt-4o-mini';
    const temperature = cfg.get<number>('temperature') ?? 0.2;
    const maxTokens = cfg.get<number>('maxTokens') ?? 2048;
    return new LlmAdapter({ apiKey, baseUrl, model, temperature, maxTokens });
  }

  async chat(messages: ChatMessage[]): Promise<string> {
    const resp = await this.client.chat.completions.create({
      model: this.model,
      messages: messages as OpenAI.Chat.Completions.ChatCompletionMessageParam[],
      temperature: this.temperature,
      max_tokens: this.maxTokens,
    });
    return resp.choices[0]?.message?.content ?? '';
  }

  async complete(prefix: string, suffix: string, language: string): Promise<string> {
    const system = `你是一个代码补全引擎。只输出紧接着的代码片段，不要解释，不要 markdown 代码块。语言: ${language}。`;
    const user = `前文:\n${prefix}\n\n后文:\n${suffix}\n\n请补全中间部分:`;
    return this.chat([
      { role: 'system', content: system },
      { role: 'user', content: user },
    ]);
  }

  async refactor(code: string, instruction: string, language: string): Promise<string> {
    const system = `你是一个重构引擎。输出完整重构后的代码，不要解释，不要 markdown 代码块。语言: ${language}。`;
    const user = `重构指令: ${instruction}\n\n原代码:\n${code}`;
    return this.chat([
      { role: 'system', content: system },
      { role: 'user', content: user },
    ]);
  }
}
