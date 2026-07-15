import * as React from 'react';
import { ChatMsg } from '../../messages';

interface Props {
  messages: ChatMsg[];
  onSend: (text: string) => void;
  onAudit: (content: string) => void;
  busy: boolean;
}

export function ChatPanel({ messages, onSend, onAudit, busy }: Props) {
  const [text, setText] = React.useState('');
  const endRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const submit = () => {
    const t = text.trim();
    if (!t || busy) return;
    onSend(t);
    setText('');
  };

  return (
    <div className="chat">
      <div className="messages">
        {messages.map((m, i) => (
          <div key={i} className={'msg ' + m.role}>
            {m.content}
            {m.role === 'assistant' && i > 0 && (
              <div className="meta">
                <button className="audit-btn" onClick={() => onAudit(m.content)}>
                  审计此回复
                </button>
              </div>
            )}
          </div>
        ))}
        <div ref={endRef} />
      </div>
      <div className="composer">
        <textarea
          value={text}
          placeholder="向 LLM 提问…（Enter 发送，Shift+Enter 换行）"
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              submit();
            }
          }}
        />
        <button className="send" disabled={busy || !text.trim()} onClick={submit}>
          发送
        </button>
      </div>
    </div>
  );
}
