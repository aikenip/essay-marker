#!/usr/bin/env python3
"""Save marking text for a submission (for teacher or Grok Bot).

Examples:
  python scripts/save_marking.py --id 3 --file /tmp/marking.md
  python scripts/save_marking.py --id 3 --text "# 總評\\n..."
  cat marking.md | python scripts/save_marking.py --id 3 --stdin
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running from project root
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from emarker import db  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Save marking for a submission")
    parser.add_argument("--id", type=int, required=True, help="Submission ID")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", type=Path, help="Path to markdown/text file")
    group.add_argument("--text", type=str, help="Marking text inline")
    group.add_argument(
        "--stdin", action="store_true", help="Read marking text from stdin"
    )
    args = parser.parse_args()

    db.init_db()
    row = db.get_submission(args.id)
    if not row:
        print(f"ERROR: submission #{args.id} not found", file=sys.stderr)
        return 1

    if args.file:
        if not args.file.is_file():
            print(f"ERROR: file not found: {args.file}", file=sys.stderr)
            return 1
        text = args.file.read_text(encoding="utf-8")
    elif args.stdin:
        text = sys.stdin.read()
    else:
        text = args.text or ""

    if not text.strip():
        print("ERROR: marking text is empty", file=sys.stderr)
        return 1

    ok = db.save_marking(args.id, text)
    if not ok:
        print(f"ERROR: failed to update submission #{args.id}", file=sys.stderr)
        return 1

    print(f"OK: submission #{args.id} marked ({len(text)} chars)")
    print(f"  student: {row['username']}")
    print(f"  note: {row['student_note'] or '—'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
