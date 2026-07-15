#!/usr/bin/env python3
"""Local causal audit CLI for the VS Code Second-Person Causal Audit Copilot.

Reads a JSON decision context from stdin, runs the LOCAL second-person
decomposer (offline, neutral, no network), and prints a structured audit
report as JSON to stdout.

I/O is done through the binary buffers with explicit UTF-8 so the engine
works regardless of the host console codepage (Windows GBK/cmd, etc.).

Input JSON (minimum):
{
  "decision": "the concrete suggestion / code / action to audit",
  "context": "optional surrounding context",
  "metadata": { "source": "completion|refactor|chat", "language": "python" }
}

The core audit NEVER leaves the machine. The LLM (used by the extension
host) is only for optional narrative polish, never for the audit verdict.
"""
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from decomposer.causal_decomposer import CausalDecomposer


def _emit(obj: dict) -> None:
    data = json.dumps(obj, ensure_ascii=False, indent=2).encode('utf-8')
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.write(b'\n')
    sys.stdout.buffer.flush()


def main() -> int:
    raw_bytes = sys.stdin.buffer.read()
    raw = raw_bytes.decode('utf-8', errors='strict')

    try:
        context = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as e:
        _emit({"error": f"invalid json: {e}"})
        return 2

    if not isinstance(context, dict):
        context = {"decision": str(context)}

    decomposer = CausalDecomposer(
        strictness=os.environ.get('CA_STRICTNESS', 'standard')
    )
    report = decomposer.audit(context)
    _emit(report)
    return 0


if __name__ == '__main__':
    sys.exit(main())
