"""Model-arm collector — freeze real model verdicts into the run_test.py contract.

One request per corpus item (no shared context), temperature 0, repeats via
``--runs``; each reply is parsed to one of the four structural states and
appended verbatim to ``out/model_responses_<name>.jsonl``::

    {"sample_id": "QLT-HAL-0001", "run": 1, "state": "anchored",
     "raw": "<verbatim model output>", "model": "<model id>",
     "temperature": 0, "prompt_version": "t1-classify-v1",
     "prompt_sha256": "<sha256 of the exact messages>", "ts": "<utc iso>"}

``run_test.py`` consumes the frozen file only (its SHA-256 is pinned into the
audit chain), so any tool that writes this format works as an arm — including
manual or platform exports (e.g. WorkBuddy). The endpoint here is the default
plug: any OpenAI-compatible chat API.

Usage:
  python examples/hallucination_3_1/collect_model_responses.py \
      --model gpt-4o --base-url https://api.example.com/v1 \
      --api-key-env MODEL_API_KEY --runs 3 --name model-a

  --limit N    collect only the first N items (subset pilot)
  --resume     skip (sample_id, run) rows already present after an interruption
  --dry-run    print the first prompt and exit (no key needed)

Exit code: 0 all good, 1 some calls failed (re-run with --resume), 2 usage.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).parent
DEFAULT_TESTSET = HERE / "hallucination_testset_v1.json"
DEFAULT_OUT_DIR = HERE / "out"

CLASSES = ("anchored", "floating", "opaque", "hollow")

PROMPT_VERSION = "t1-classify-v1"

SYSTEM_PROMPT = (
    "你是结构审计员，执行 T1 结构标注。给定一个问答样本的输入与模型回答，"
    "判断回答的结构状态，四选一：\n"
    "anchored：回答声明了所依赖的假设，并给出了失败分支；\n"
    "floating：回答声明了假设，但未给出失败分支；\n"
    "opaque：回答给出了失败分支，但未声明假设；\n"
    "hollow：回答既未声明假设，也未给出失败分支。\n"
    '只输出一个 JSON 对象：{"state": "<anchored|floating|opaque|hollow>"}'
)


def build_messages(payload: dict) -> list[dict]:
    user = f"输入：{payload['input']}\n回答：{payload['response_text']}"
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]


def prompt_sha256(messages: list[dict]) -> str:
    blob = json.dumps(messages, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def call_model(
    base_url: str, api_key: str, model: str, messages: list[dict], timeout: int
) -> str:
    body = json.dumps(
        {
            "model": model,
            "messages": messages,
            "temperature": 0,
            "max_tokens": 64,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = json.loads(response.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"]


def parse_state(raw: str) -> str:
    """Deterministic extraction of the state from a model reply."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.startswith("json"):
            text = text[4:].strip()
    try:
        state = str(json.loads(text).get("state", "")).strip().lower()
        if state in CLASSES:
            return state
    except (json.JSONDecodeError, AttributeError):
        pass
    lowered = text.lower()
    for state in CLASSES:
        if state in lowered:
            return state
    return "invalid"


def _load_completed(path: Path) -> set[tuple[str, int]]:
    done: set[tuple[str, int]] = set()
    if not path.exists():
        return done
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        done.add((str(row["sample_id"]), int(row.get("run", 1))))
    return done


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model", required=True, help="model id sent to the endpoint")
    parser.add_argument(
        "--base-url",
        required=True,
        help="OpenAI-compatible base url, e.g. https://api.example.com/v1",
    )
    parser.add_argument("--api-key", default=None, help="API key (or use --api-key-env)")
    parser.add_argument("--api-key-env", default=None, help="env var holding the API key")
    parser.add_argument(
        "--name",
        default=None,
        help="arm name -> out/model_responses_<name>.jsonl (default: sanitized model id)",
    )
    parser.add_argument("--runs", type=int, default=1, help="repeat observations per item")
    parser.add_argument("--limit", type=int, default=None, help="collect only the first N items")
    parser.add_argument("--testset", type=Path, default=DEFAULT_TESTSET)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--timeout", type=int, default=60, help="per-request timeout (seconds)")
    parser.add_argument("--sleep", type=float, default=0.0, help="seconds between calls")
    parser.add_argument(
        "--resume", action="store_true", help="skip (sample_id, run) rows already in the file"
    )
    parser.add_argument("--dry-run", action="store_true", help="print the first prompt and exit")
    args = parser.parse_args()

    if args.runs < 1:
        parser.error("--runs must be >= 1")

    corpus = json.loads(Path(args.testset).read_text(encoding="utf-8"))
    items = sorted(corpus["items"], key=lambda item: item["id"])
    if args.limit is not None:
        items = items[: args.limit]
    if not items:
        parser.error("no items to collect")

    name = args.name or "".join(
        ch if (ch.isalnum() or ch in "-_") else "-" for ch in args.model.lower()
    )
    out_path = Path(args.out_dir) / f"model_responses_{name}.jsonl"

    if args.dry_run:
        messages = build_messages(items[0]["payload"])
        print(json.dumps(messages, ensure_ascii=False, indent=2))
        print(f"prompt_version: {PROMPT_VERSION}")
        print(f"prompt_sha256: {prompt_sha256(messages)}")
        print(f"would write: {out_path}")
        return 0

    api_key = args.api_key or (os.environ.get(args.api_key_env) if args.api_key_env else None)
    if not api_key:
        print("error: provide --api-key or --api-key-env", file=sys.stderr)
        return 2

    out_path.parent.mkdir(parents=True, exist_ok=True)
    done = _load_completed(out_path) if args.resume else set()

    ok = failed = skipped = 0
    with out_path.open("a", encoding="utf-8") as handle:
        for item in items:
            messages = build_messages(item["payload"])
            sha = prompt_sha256(messages)
            for run in range(1, args.runs + 1):
                if (item["id"], run) in done:
                    skipped += 1
                    continue
                try:
                    raw = call_model(args.base_url, api_key, args.model, messages, args.timeout)
                except (urllib.error.URLError, OSError, KeyError, json.JSONDecodeError) as exc:
                    failed += 1
                    print(f"[fail] {item['id']} run {run}: {exc}", file=sys.stderr)
                    continue
                row = {
                    "sample_id": item["id"],
                    "run": run,
                    "state": parse_state(raw),
                    "raw": raw,
                    "model": args.model,
                    "temperature": 0,
                    "prompt_version": PROMPT_VERSION,
                    "prompt_sha256": sha,
                    "ts": datetime.now(timezone.utc).isoformat(),
                }
                handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
                handle.flush()
                ok += 1
                if ok % 25 == 0:
                    print(f"… {ok} rows written ({item['id']} run {run})")
                if args.sleep:
                    time.sleep(args.sleep)

    print(f"written {ok} · skipped {skipped} · failed {failed} -> {out_path}")
    if failed:
        print("re-run with --resume to fill the gaps", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
