// Minimal typings for the VS Code webview API (avoids pulling @types/vscode into the web bundle).
declare function acquireVsCodeApi(): {
  postMessage(message: unknown): void;
  getState(): unknown;
  setState(state: unknown): void;
};

export const vscode = acquireVsCodeApi();
