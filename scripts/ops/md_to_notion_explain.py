"""docs/explain/*.md → Notion-flavored Markdown 변환기.

변환 규칙
- inline math `$...$` → `$`...`$` (Notion은 inline math를 backtick으로 감싸야 함). `$$` 블록은 건드리지 않음.
- 로컬 그림 `![cap](path)` → callout 텍스트 (Notion이 로컬 파일을 못 읽으므로 경로만 보존).
- 상대 .md 링크 `[text](NN_*.md)` → 일반 텍스트 (생성 시점에 대상 페이지 URL을 모름).
- code fence(```...```) 안은 변환하지 않음.
- mermaid / `$$` 블록 / GFM 표는 그대로 둠.

출력은 stdout. 단일 파일 경로를 인자로 받는다.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


def convert_inline_math(line: str) -> str:
    # $$...$$ 한 줄은 건드리지 않음
    if line.strip().startswith("$$"):
        return line
    # 짝이 맞는 단일 $...$ 를 $`...`$ 로. $$ 는 제외.
    # 음수/통화가 아니라 수식만 잡도록, $ 사이에 개행 없는 비탐욕 매칭.
    def repl(m: re.Match) -> str:
        inner = m.group(1)
        return f"$`{inner}`$"

    # (?<!\$) 앞이 $ 아님, \$ ... \$ 사이에 $ 없음, (?!\$) 뒤가 $ 아님
    return re.sub(r"(?<!\$)\$(?!\$)([^$\n]+?)\$(?!\$)", repl, line)


def convert_local_image(line: str) -> str:
    # ![cap](url) — http(s)면 유지, 아니면 callout 텍스트로
    def repl(m: re.Match) -> str:
        cap, url = m.group(1), m.group(2)
        if url.startswith("http"):
            return m.group(0)
        label = cap.strip() or "그림"
        return f'<callout icon="📊">그림(로컬): {label} — `{url}`</callout>'

    return re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", repl, line)


def convert_relative_md_link(line: str) -> str:
    # [text](something.md) 또는 [text](something.md#anchor) → text (코드 외부에서만)
    def repl(m: re.Match) -> str:
        return m.group(1)

    return re.sub(r"\[([^\]]+)\]\((?!https?://)[^)]+?\.md(?:#[^)]*)?\)", repl, line)


def convert(text: str) -> str:
    out: list[str] = []
    in_fence = False
    in_math_block = False
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            out.append(line)
            continue
        if in_fence:
            out.append(line)
            continue
        # $$ 블록 토글
        if stripped.startswith("$$"):
            in_math_block = not in_math_block
            out.append(line)
            continue
        if in_math_block:
            out.append(line)
            continue
        line = convert_local_image(line)
        line = convert_relative_md_link(line)
        line = convert_inline_math(line)
        out.append(line)
    return "\n".join(out)


def main() -> None:
    path = Path(sys.argv[1])
    sys.stdout.write(convert(path.read_text(encoding="utf-8")))


if __name__ == "__main__":
    main()
