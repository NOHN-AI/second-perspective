import * as React from 'react';
import { vscode } from './vscodeApi';
import { ChatMsg, FromExtension, HistoryEntry, LlmConfig, StatusSnapshot } from '../messages';
import { AuditReport } from '../../audit/auditTypes';
import { ChatPanel } from './components/ChatPanel';
import { AuditGraph } from './components/AuditGraph';
import { HistoryPanel } from './components/HistoryPanel';
import { LlmConfigPanel } from './components/LlmConfigPanel';

type Tab = 'chat' | 'graph' | 'history' | 'config';

export function App() {
  const [tab, setTab] = React.useState<Tab>('chat');
  const [messages, setMessages] = React.useState<ChatMsg[]>([
    {
      role: 'assistant',
      content:
        '我是第二视角因果审计副驾。提问会发给 LLM 生成，本地离线引擎对输出做因果审计（D/A/ΔD，?A?ΔD）。点「审计此回复」查看因果图。',
    },
  ]);
  const [report, setReport] = React.useState<AuditReport | null>(null);
  const [history, setHistory] = React.useState<HistoryEntry[]>([]);
  const [status, setStatus] = React.useState<StatusSnapshot | null>(null);
  const [config, setConfig] = React.useState<Partial<LlmConfig>>({
    provider: 'openai',
    baseUrl: 'https://api.openai.com/v1',
    model: 'gpt-4o-mini',
  });
  const [error, setError] = React.useState<string | null>(null);
  const [sending, setSending] = React.useState(false);

  React.useEffect(() => {
    const handler = (e: MessageEvent) => {
      const m = e.data as FromExtension;
      switch (m.type) {
        case 'chatResponse':
          setMessages((prev) => [...prev, { role: 'assistant', content: m.content }]);
          setSending(false);
          break;
        case 'chatError':
          setError(m.message);
          setSending(false);
          break;
        case 'auditResult':
          setReport(m.report);
          setTab('graph');
          break;
        case 'showReport':
          setReport(m.report);
          setTab('graph');
          break;
        case 'history':
          setHistory(m.entries);
          break;
        case 'status':
          setStatus(m.snapshot);
          setConfig({
            provider: (m.snapshot.provider as LlmConfig['provider']) || 'openai',
            baseUrl: m.snapshot.baseUrl || 'https://api.openai.com/v1',
            model: m.snapshot.model || 'gpt-4o-mini',
          });
          break;
        case 'llmConfigSaved':
          if (m.success) {
            vscode.postMessage({ type: 'requestStatus' });
          } else {
            setError(m.message || '保存失败');
          }
          break;
        case 'error':
          setError(m.message);
          break;
      }
    };
    window.addEventListener('message', handler);
    vscode.postMessage({ type: 'ready' });
    return () => window.removeEventListener('message', handler);
  }, []);

  const sendChat = (text: string) => {
    if (sending) return;
    const next: ChatMsg[] = [...messages, { role: 'user', content: text }];
    setMessages(next);
    setSending(true);
    vscode.postMessage({ type: 'chat', messages: next, requestId: Date.now().toString(36) });
  };

  const auditMessage = (content: string) => {
    vscode.postMessage({ type: 'audit', decision: content, source: 'chat' });
  };

  const refreshStatus = () => {
    vscode.postMessage({ type: 'requestStatus' });
  };

  return (
    <div className="app">
      <StatusBar status={status} onRefresh={refreshStatus} />
      <div className="tabs">
        <div className={'tab' + (tab === 'chat' ? ' active' : '')} onClick={() => setTab('chat')}>聊天</div>
        <div className={'tab' + (tab === 'graph' ? ' active' : '')} onClick={() => setTab('graph')}>因果图</div>
        <div className={'tab' + (tab === 'history' ? ' active' : '')} onClick={() => setTab('history')}>
          历史{history.length > 0 && <span className="badge">{history.length}</span>}
        </div>
        <div className={'tab' + (tab === 'config' ? ' active' : '')} onClick={() => setTab('config')}>模型</div>
      </div>
      <div className="content">
        {error && (
          <div className="error">
            {error}
            <button className="link" onClick={() => setError(null)}>×</button>
          </div>
        )}
        {tab === 'chat' && (
          <ChatPanel messages={messages} onSend={sendChat} onAudit={auditMessage} busy={sending} />
        )}
        {tab === 'graph' && <AuditGraph report={report} />}
        {tab === 'history' && (
          <HistoryPanel entries={history} onSelect={(e) => { setReport(e.report); setTab('graph'); }} />
        )}
        {tab === 'config' && <LlmConfigPanel current={config} />}
      </div>
    </div>
  );
}

function StatusBar({ status, onRefresh }: { status: StatusSnapshot | null; onRefresh: () => void }) {
  const cls = (v?: string) =>
    v === 'ok' ? 'pill ok' : v === 'offline' || v === 'missing' ? 'pill bad' : 'pill warn';
  return (
    <div className="status-bar">
      <span className={cls(status?.engine)} title="本地 Python 审计引擎">引擎 {status ? status.engine : '…'}</span>
      <span className={cls(status?.auditLayer)} title="因果审计层 D/A/ΔD">审计层</span>
      <span className={cls(status?.llm)} title={status ? status.baseUrl + ' · ' + status.model : ''}>LLM {status ? status.llm : '…'}</span>
      <button className="link" onClick={onRefresh} title="刷新状态">↻</button>
    </div>
  );
}
