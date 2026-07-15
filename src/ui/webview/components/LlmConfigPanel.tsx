import * as React from 'react';
import { vscode } from '../vscodeApi';
import { LlmConfig } from '../../messages';

const PRESETS: Record<string, { baseUrl: string; model: string }> = {
  openai:     { baseUrl: 'https://api.openai.com/v1',        model: 'gpt-4o-mini' },
  anthropic:  { baseUrl: 'https://api.anthropic.com/v1',     model: 'claude-3-5-sonnet-20241022' },
  ollama:     { baseUrl: 'http://localhost:11434/v1',        model: 'llama3.2' },
};

interface Props {
  current: Partial<LlmConfig>;
}

export function LlmConfigPanel({ current }: Props) {
  const [provider, setProvider] = React.useState<string>(current.provider || 'openai');
  const [apiKey,    setApiKey]    = React.useState(current.apiKey || '');
  const [baseUrl,   setBaseUrl]   = React.useState(current.baseUrl || PRESETS.openai.baseUrl);
  const [model,     setModel]     = React.useState(current.model || PRESETS.openai.model);
  const [showKey,   setShowKey]   = React.useState(false);
  const [saved,     setSaved]     = React.useState(false);

  React.useEffect(() => {
    const preset = PRESETS[provider];
    if (preset) setBaseUrl(preset.baseUrl);
  }, [provider]);

  const save = () => {
    vscode.postMessage({
      type: 'saveLlmConfig',
      config: { provider: provider as LlmConfig['provider'], apiKey, baseUrl, model },
    });
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div className="llm-config">
      <h3>模型配置</h3>
      <div className="field">
        <label>API 提供方</label>
        <select value={provider} onChange={(e) => { setProvider(e.target.value); setSaved(false); }}>
          <option value="openai">OpenAI</option>
          <option value="anthropic">Anthropic / Claude</option>
          <option value="ollama">Ollama (本地)</option>
          <option value="custom">自定义</option>
        </select>
      </div>
      <div className="field">
        <label>API Key</label>
        <div className="pw-row">
          <input type={showKey ? 'text' : 'password'} value={apiKey}
            placeholder={provider === 'custom' ? '输入 API Key' : 'sk-...'}
            onChange={(e) => { setApiKey(e.target.value); setSaved(false); }} />
          <span className="toggle" onClick={() => setShowKey(!showKey)}>{showKey ? '隐藏' : '显示'}</span>
        </div>
      </div>
      <div className="row">
        <div className="field">
          <label>Base URL</label>
          <input value={baseUrl} readOnly={provider !== 'custom'}
            onChange={(e) => { setBaseUrl(e.target.value); setSaved(false); }}
            placeholder="https://api.openai.com/v1" />
        </div>
        <div className="field">
          <label>模型</label>
          <input value={model}
            onChange={(e) => { setModel(e.target.value); setSaved(false); }}
            placeholder="gpt-4o-mini" />
        </div>
      </div>
      {provider === 'custom' && (
        <div className="hint">
          自定义提供方需兼容 OpenAI API (/v1/chat/completions)。<br/>
          本地模型：Ollama http://localhost:11434/v1，vLLM http://localhost:8000/v1
        </div>
      )}
      <div className="actions">
        <button className="primary" disabled={!provider || !model} onClick={save}>保存配置</button>
        {saved && <span className="saved">已保存</span>}
      </div>
      {apiKey && (
        <div className="status-line"><span>Key 已填</span><span className="ok">· 首次聊天时自动连接</span></div>
      )}
    </div>
  );
}
