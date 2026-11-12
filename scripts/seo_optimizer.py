#!/usr/bin/env python3
"""Analyze basic on-page SEO signals in Markdown or text.

This is an editorial checklist aid, not a search-engine ranking predictor.
It does not fetch pages, alter files, or promise ranking improvements.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

WORD_RE = re.compile(r"[\w'-]+", re.UNICODE)
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$", re.MULTILINE)


def normalize(value: str) -> str:
    return " ".join(WORD_RE.findall(value.lower()))


def phrase_count(text: str, phrase: str) -> int:
    normalized_text = f" {normalize(text)} "
    normalized_phrase = f" {normalize(phrase)} "
    if not normalized_phrase.strip():
        return 0
    return normalized_text.count(normalized_phrase)


def _average_sentence_words(text: str) -> float:
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    lengths = [len(WORD_RE.findall(s)) for s in sentences]
    lengths = [length for length in lengths if length]
    return sum(lengths) / len(lengths) if lengths else 0.0


def _check(checks: list[dict[str, Any]], label: str, passed: bool, points: int) -> None:
    checks.append({"check": label, "passed": passed, "points": points if passed else 0})


def analyze(content: str, primary_keyword: str | None, secondary_keywords: list[str]) -> dict[str, Any]:
    frontmatter = ""
    body = content
    if content.startswith("---\n"):
        parts = content.split("---", 2)
        if len(parts) == 3:
            frontmatter, body = parts[1], parts[2]

    tokens = WORD_RE.findall(body)
    word_count = len(tokens)
    headings = HEADING_RE.findall(body)
    heading_texts = [heading.strip() for _, heading in headings]
    h1s = [heading for level, heading in headings if len(level) == 1]
    paragraphs = [
        block.strip()
        for block in re.split(r"\n\s*\n", body)
        if block.strip()
        and not re.match(r"^\s*#", block)
        and not block.strip().startswith("~~~")
    ]
    intro = " ".join(paragraphs[:2]) if paragraphs else ""
    title = h1s[0] if h1s else ""
    description_match = re.search(
        r"(?im)^\s*(?:description|meta_description)\s*:\s*['\"]?(.*?)['\"]?\s*$",
        frontmatter,
    )
    meta_description = description_match.group(1).strip() if description_match else ""

    primary_count = phrase_count(body, primary_keyword) if primary_keyword else 0
    primary_density = primary_count / word_count * 100 if word_count and primary_keyword else 0.0
    secondary = {term: phrase_count(body, term) for term in secondary_keywords if term.strip()}
    external_links = len(re.findall(r"\]\(https?://", body, re.IGNORECASE))
    internal_links = len(re.findall(r"\]\((?!https?://|#)[^)]+\)", body, re.IGNORECASE))
    avg_sentence_words = _average_sentence_words(body)

    checks: list[dict[str, Any]] = []
    _check(checks, "Clear main heading", bool(title), 10)
    _check(checks, "Single H1 heading", len(h1s) == 1, 10)
    _check(checks, "Primary keyword in title", bool(primary_keyword and phrase_count(title, primary_keyword)), 15)
    _check(checks, "Primary keyword appears early", bool(primary_keyword and phrase_count(intro, primary_keyword)), 15)
    _check(checks, "Descriptive section headings", len(heading_texts) >= 3, 10)
    _check(checks, "Secondary terms used naturally", bool(secondary and any(secondary.values())), 10)
    _check(checks, "Meta description supplied", bool(meta_description), 10)
    _check(checks, "Internal links present", internal_links > 0, 5)
    _check(checks, "Relevant external references present", external_links > 0, 5)
    _check(checks, "Readable sentence length", 8 <= avg_sentence_words <= 28 or word_count < 80, 10)
    score = sum(item["points"] for item in checks if item["passed"])

    recommendations = []
    if not title:
        recommendations.append("Add one clear H1 that describes the page's primary topic.")
    if len(h1s) != 1:
        recommendations.append("Review heading hierarchy and use one clear top-level heading.")
    if primary_keyword and not phrase_count(title, primary_keyword):
        recommendations.append("Consider whether the primary topic belongs naturally in the main heading.")
    if primary_keyword and not phrase_count(intro, primary_keyword):
        recommendations.append("Make the opening paragraph clearly address the primary topic.")
    if not meta_description:
        recommendations.append("Write a concise, accurate meta description if the publishing system supports it.")
    if avg_sentence_words > 28:
        recommendations.append("Break up dense sentences where doing so improves comprehension.")
    if primary_keyword and primary_density > 3:
        recommendations.append("Primary phrase repetition is high; remove forced repetitions and prioritize natural language.")
    if not internal_links:
        recommendations.append("Add useful internal links to relevant pages where they help the reader.")
    if not external_links:
        recommendations.append("Cite reliable external sources for claims that need evidence.")
    if not recommendations:
        recommendations.append("No major checklist gaps were detected. Review usefulness and factual accuracy manually.")

    return {
        "score": score,
        "word_count": word_count,
        "title": title,
        "heading_count": len(headings),
        "h1_count": len(h1s),
        "average_sentence_words": round(avg_sentence_words, 2),
        "primary_keyword": {
            "term": primary_keyword,
            "occurrences": primary_count,
            "density_percent": round(primary_density, 2) if primary_keyword else None,
        },
        "secondary_keywords": secondary,
        "links": {"internal": internal_links, "external": external_links},
        "meta_description": {
            "present": bool(meta_description),
            "characters": len(meta_description),
            "text": meta_description,
        },
        "checks": checks,
        "recommendations": recommendations,
        "limitations": [
            "The score is a local editorial checklist, not a search-engine score or ranking prediction.",
            "Keyword density is descriptive only; do not force repetitions to reach a target.",
            "Search intent, usefulness, originality, factual accuracy, and page experience require human review.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze on-page content signals without modifying a file.")
    parser.add_argument("file", type=Path, help="Markdown or text file")
    parser.add_argument("primary_keyword", nargs="?", help="Optional primary phrase")
    parser.add_argument("secondary_keywords", nargs="?", default="", help="Optional comma-separated phrases")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args()

    try:
        source_text = args.file.read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"Error: file not found: {args.file}", file=sys.stderr)
        return 2
    except (OSError, UnicodeError) as exc:
        print(f"Error: could not read input file ({exc})", file=sys.stderr)
        return 2

    secondary = [term.strip() for term in args.secondary_keywords.split(",") if term.strip()]
    result = analyze(source_text, args.primary_keyword, secondary)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"On-page content review: {args.file}")
        print(f"Checklist score: {result['score']}/100")
        print(f"Words: {result['word_count']} | Headings: {result['heading_count']} | H1: {result['h1_count']}")
        print(f"Average sentence length: {result['average_sentence_words']} words")
        print(f"Primary keyword: {result['primary_keyword']['term'] or 'not supplied'}")
        print(f"Primary occurrences: {result['primary_keyword']['occurrences']}")
        print(f"Primary density: {result['primary_keyword']['density_percent']}")
        print(f"Links: {result['links']}")
        print("\nChecks:")
        for item in result["checks"]:
            status = "PASS" if item["passed"] else "REVIEW"
            print(f"- {status}: {item['check']} ({item['points']} points)")
        print("\nRecommendations:")
        for item in result["recommendations"]:
            print(f"- {item}")
        print("\nLimitations:")
        for item in result["limitations"]:
            print(f"- {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
