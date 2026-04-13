from __future__ import annotations

import argparse
from pathlib import Path

from qa_agent.chat.agent import ChatAgent


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Interactive chat over the sanmou QA knowledge base.")
    parser.add_argument(
        "--knowledge-dir",
        default="knowledge_sources",
        help="Path (absolute or relative to qa-agent package root) to knowledge_sources.",
    )
    parser.add_argument(
        "--question",
        help="If provided, answer this single question and exit (non-interactive mode).",
    )
    parser.add_argument(
        "--show-evidence",
        action="store_true",
        help="Print retrieved evidence blocks before the answer.",
    )
    return parser


def _resolve_knowledge_dir(raw: str) -> Path:
    path = Path(raw)
    if path.is_absolute():
        return path
    package_root = Path(__file__).resolve().parents[3]
    return (package_root / raw).resolve()


def _print_reply(reply, show_evidence: bool) -> None:
    if show_evidence:
        print("\n--- queries ---")
        for q in reply.queries:
            print(f"  · {q}")
        print("\n--- evidence ---")
        if not reply.evidence:
            print("  (none)")
        for chunk in reply.evidence:
            print(f"  [{chunk.entry.id}] {chunk.entry.topic} ({chunk.entry.domain.value}, score={chunk.score:.2f})")
        print("\n--- answer ---")
    print(reply.answer)
    print(
        f"\n[tokens prompt={reply.prompt_tokens} output={reply.output_tokens} elapsed={reply.elapsed_s:.2f}s]"
    )


def main() -> None:
    args = _build_parser().parse_args()
    knowledge_dir = _resolve_knowledge_dir(args.knowledge_dir)
    if not knowledge_dir.exists():
        raise SystemExit(f"knowledge_sources not found at {knowledge_dir}")

    agent = ChatAgent.from_knowledge_dir(knowledge_dir)

    if args.question:
        reply = agent.ask(args.question)
        _print_reply(reply, args.show_evidence)
        return

    print("三谋 QA Chat — 输入 /reset 清空对话，/quit 退出")
    while True:
        try:
            question = input("\n你> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not question:
            continue
        if question in {"/quit", "/exit"}:
            break
        if question == "/reset":
            agent.reset()
            print("(对话已重置)")
            continue
        try:
            reply = agent.ask(question)
        except Exception as exc:  # noqa: BLE001
            print(f"[error] {exc}")
            continue
        print()
        _print_reply(reply, args.show_evidence)


if __name__ == "__main__":
    main()
