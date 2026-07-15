import { AuditReport } from '../audit/auditTypes';

export interface ChatMsg { role: 'system' | 'user' | 'assistant'; content: string; }

export interface HistoryEntry {
  id: string; ts: number; source: string;
  verdict: boolean; overall: number; decision: string; report: AuditReport;
}

export interface StatusSnapshot {
  engine: 'ok' | 'offline' | 'error';
  auditLayer: 'ready' | 'busy';
  llm: 'configured' | 'missing';
  apiKeySource: 'secret' | 'settings' | 'none';
  baseUrl: string; model: string; provider: string;
}

export interface LlmConfig {
  provider: 'openai' | 'anthropic' | 'ollama' | 'custom';
  apiKey: string; baseUrl: string; model: string;
}

export type ToExtension =
  | { type: 'ready' }
  | { type: 'chat'; messages: ChatMsg[]; requestId: string }
  | { type: 'audit'; decision: string; context?: string; source?: string; requestId?: string }
  | { type: 'requestHistory' }
  | { type: 'requestStatus' }
  | { type: 'saveLlmConfig'; config: LlmConfig };

export type FromExtension =
  | { type: 'chatResponse'; requestId: string; content: string }
  | { type: 'chatError'; requestId: string; message: string }
  | { type: 'auditResult'; requestId?: string; report: AuditReport }
  | { type: 'showReport'; report: AuditReport }
  | { type: 'history'; entries: HistoryEntry[] }
  | { type: 'status'; snapshot: StatusSnapshot }
  | { type: 'llmConfigSaved'; success: boolean; message?: string }
  | { type: 'error'; message: string };
