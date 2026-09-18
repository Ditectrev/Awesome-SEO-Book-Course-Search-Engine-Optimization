#!/usr/bin/env python3
"""Generate reveal.js slides from README.md following the HTML book pattern."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
OUT = Path(__file__).resolve().parent / "index.html"

SLIDE_SUFFIX = ' <!-- .slide: data-transition="zoom" data-transition-speed="slow" -->'
FRAGMENT = ' <!-- .element: class="fragment custom blur highlight-current-blue fade-up" -->'

CODESANDBOX_RE = re.compile(
    r'\[\!\[Edit ([^\]]+)\]\(images/codesandbox\.svg\)\]\((https://codesandbox\.io/[^)]+)\)'
)
FOOTNOTE_RE = re.compile(
    r'\[\^\d+\]:\[CodeSandbox: ([^\]]+)\]\((https://[^)]+csb\.app/)[^)]*\)'
)


def parse_sections(text: str):
    """Split README into heading-delimited sections from Introduction onward."""
    start = text.find("## Introduction to Web Accessibility")
    if start == -1:
        raise SystemExit("Could not find start of book content")
    text = text[start:]

    pattern = re.compile(r'^(#{2,4})\s+(.+)$', re.MULTILINE)
    matches = list(pattern.finditer(text))
    sections = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections.append({
            "level": len(m.group(1)),
            "title": m.group(2).strip(),
            "body": text[m.end():end].strip(),
        })
    return sections


def extract_codesandbox(body: str):
    m = CODESANDBOX_RE.search(body)
    if not m:
        return None
    title = m.group(1)
    # strip leading number prefix like "001-"
    short = re.sub(r'^\d+-', '', title)
    fm = FOOTNOTE_RE.search(body)
    live = fm.group(2) if fm else None
    live_title = fm.group(1) if fm else short
    return {
        "edit_title": title,
        "sandbox_url": m.group(2),
        "live_url": live,
        "live_title": live_title,
    }


def extract_code_blocks(body: str):
    blocks = []
    for m in re.finditer(r'```(\w*)\n(.*?)```', body, re.DOTALL):
        lang = m.group(1) or "html"
        blocks.append((lang, m.group(2).rstrip("\n")))
    blocks.sort(key=lambda b: (0 if b[0] == "html" else 1))
    return blocks


def strip_style_script(code: str) -> str:
    code = re.sub(r'<style[^>]*>.*?</style>\s*', '', code, flags=re.DOTALL | re.IGNORECASE)
    code = re.sub(r'<script[^>]*>.*?</script>\s*', '', code, flags=re.DOTALL | re.IGNORECASE)
    # Remove inline style attributes (not needed on slides)
    code = re.sub(r'\s+style="[^"]*"', '', code)
    code = re.sub(r"\s+style='[^']*'", '', code)
    return code


def trim_code(code: str, lang: str = "html") -> str:
    code = strip_style_script(code)
    lines = code.split("\n")

    # Drop boilerplate wrapper lines for full documents
    drop_prefixes = (
        "<!DOCTYPE", "<html", "</html>", "<head>", "</head>", "<body>", "</body>",
        '<meta charset', "<title>", "</title>",
    )
    filtered = []
    for line in lines:
        s = line.strip()
        if not s:
            if filtered and filtered[-1] != "":
                filtered.append("")
            continue
        if any(s.startswith(p) for p in drop_prefixes):
            continue
        if s.startswith("<!--") and ("Demo only" in s or "demo" in s.lower()):
            continue
        filtered.append(line.rstrip())

    # Collapse multiple blank lines
    out = []
    for line in filtered:
        if line == "" and out and out[-1] == "":
            continue
        out.append(line)
    while out and out[0] == "":
        out.pop(0)
    while out and out[-1] == "":
        out.pop()

    max_lines = 22
    if len(out) > max_lines:
        # Keep first portion; add ellipsis comment
        out = out[: max_lines - 1] + ["<!-- … -->"]

    return "\n".join(out)


def make_highlights(line_count: int, lang: str = "html") -> str:
    if line_count <= 0:
        return lang
    if line_count <= 14:
        steps = [str(i) for i in range(1, line_count + 1)]
    else:
        steps = []
        i = 1
        while i <= line_count:
            if i + 2 <= line_count and (line_count - i) > 4:
                steps.append(f"{i}-{i+2}")
                i += 3
            else:
                steps.append(str(i))
                i += 1
    return f"{lang}[{'|' + '|'.join(steps) if steps else ''}]"


def slide_heading(level: int, title: str) -> str:
    """Reduce heading by one level for ####; cap at ### for slide titles."""
    if level >= 4:
        level = 3
    elif level == 2:
        level = 2
    hashes = "#" * level
    return f"{hashes} {title}{SLIDE_SUFFIX}"


def extract_bullet_items(body: str, max_items: int = 8):
    items = []
    in_bullets = False
    for line in body.splitlines():
        stripped = line.strip()
        m = re.match(r'^[-*]\s+(.+)$', stripped)
        if m:
            in_bullets = True
            text = m.group(1).strip()
            # Skip nested sub-bullets for slide brevity
            if not line.startswith("  "):
                items.append(text)
        elif in_bullets and stripped == "":
            continue
        elif in_bullets and stripped and not stripped.startswith("-"):
            break
        if len(items) >= max_items:
            break
    return items


def format_codesandbox(cs: dict) -> str:
    lines = [
        f"[![Edit {cs['edit_title']}](images/codesandbox.svg)]({cs['sandbox_url']})",
        "",
    ]
    if cs.get("live_url"):
        lines.append(f"[CodeSandbox: {cs['live_title']}]({cs['live_url']}).")
    return "\n".join(lines)


def format_list_slide(items: list[str]) -> str:
    return "\n".join(f"* {item}{FRAGMENT}" for item in items)


def content_slide(sec) -> list[str]:
    level = 3 if sec["level"] >= 4 else sec["level"]
    parts = [slide_heading(level, sec["title"]), ""]
    body = sec["body"]
    cs = extract_codesandbox(body)
    codes = extract_code_blocks(body)
    bullets = extract_bullet_items(body)

    if codes:
        lang, raw = codes[0]
        trimmed = trim_code(raw, lang)
        if trimmed:
            lc = len(trimmed.splitlines())
            parts.append(f"```{make_highlights(lc, lang)}")
            parts.append(trimmed)
            parts.append("```")
            parts.append("")

    if cs:
        parts.append(format_codesandbox(cs))
        parts.append("")
    elif bullets and not codes:
        parts.append(format_list_slide(bullets))
        parts.append("")

    return parts


def build_slides_v2(sections):
    slides = [f"# Welcome{SLIDE_SUFFIX}", ""]
    i = 0
    while i < len(sections):
        sec = sections[i]
        level = sec["level"]
        title = sec["title"]

        if level == 2:
            if title.startswith("Summary:"):
                pass  # handled at level 3
            slides.append("---")
            slides.append(slide_heading(2, title))
            slides.append("")
            i += 1
            continue

        if level == 3:
            if title.startswith("Summary:"):
                slides.append("---")
                slides.append(slide_heading(3, title))
                slides.append("")
                i += 1
                continue

            # Collect consecutive #### children
            j = i + 1
            children = []
            while j < len(sections) and sections[j]["level"] == 4:
                children.append(sections[j])
                j += 1

            if children:
                slides.append("---")
                slides.append(slide_heading(3, title))
                slides.append("")
                for child in children:
                    slides.append("---")
                    slides.extend(content_slide(child))
                i = j
                continue

            slides.append("---")
            slides.extend(content_slide(sec))
            i += 1
            continue

        # Orphan #### (shouldn't happen)
        i += 1

    return slides


def render_html(slide_md: str) -> str:
    template = """<!doctype html>
<html lang="en">
\t<head>
\t\t<meta charset="utf-8">
\t\t<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">

\t\t<title>Awesome A11Y Book & Course: Web Accessibility (A11Y)</title>

\t\t<link rel="stylesheet" href="dist/reset.css">
\t\t<link rel="stylesheet" href="dist/reveal.css">
\t\t<link rel="stylesheet" href="dist/theme/serif.css">

\t\t<!-- Theme used for syntax highlighted code -->
\t\t<link rel="stylesheet" href="plugin/highlight/monokai.css">

\t\t<style>
\t\t\t.fragment.blur {
\t\t\t\tfilter: blur(1rem);
\t\t\t}

\t\t\t.fragment.blur.visible {
\t\t\t\tfilter: none;
\t\t\t}
\t\t</style>
\t</head>
\t<body>
\t\t<div class="reveal">
\t\t\t<div class="slides">
\t\t\t\t<section data-markdown>
\t\t\t\t\t<textarea data-template>
__SLIDES__
\t\t\t\t\t</textarea>
\t\t\t\t</section>
\t\t\t</div>
\t\t</div>

\t\t<script src="dist/reveal.js"></script>
\t\t<script src="plugin/notes/notes.js"></script>
\t\t<script src="plugin/markdown/markdown.js"></script>
\t\t<script src="plugin/highlight/highlight.js"></script>
\t\t<script>
\t\t\tReveal.initialize({
\t\t\t\thash: true,
\t\t\t\tslideNumber: 'c/t',
\t\t\t\tplugins: [ RevealMarkdown, RevealHighlight, RevealNotes ]
\t\t\t});
\t\t</script>
\t</body>
</html>
"""
    return template.replace("__SLIDES__", slide_md.rstrip())


def main():
    text = README.read_text(encoding="utf-8")
    sections = parse_sections(text)
    slides = build_slides_v2(sections)
    md = "\n".join(slides)
    OUT.write_text(render_html(md), encoding="utf-8")
    print(f"Wrote {OUT} ({len(slides)} lines, {md.count('---')} slides)")


if __name__ == "__main__":
    main()
