#!/usr/bin/env python3
"""Heuristic brand-voice and readability analyzer.

This tool provides lightweight editorial signals. It does not determine brand
identity or sentiment with the reliability of a trained human reviewer.
It uses only the Python standard library.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from pathlib import Path
from typing import Any

WORD_RE = re.compile(r"[A-Za-z]+(?:['’-][A-Za-z]+)?")
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
FIRST_PERSON = {"i", "we", "me", "us", "our", "ours", "my", "mine"}
SECOND_PERSON = {"you", "your", "yours"}
FORMAL_SIGNALS = {"therefore", "however", "furthermore", "moreover", "nevertheless"}
CASUAL_SIGNALS = {"yeah", "okay", "ok", "awesome", "cool", "gonna", "wanna", "yep"}
POSITIVE_WORDS = {"good", "great", "useful", "clear", "helpful", "effective", "easy", "strong"}
NEGATIVE_WORDS = {"bad", "poor", "difficult", "hard", "weak", "slow", "unclear", "broken"}


def words(text: str) -> list[str]:
    return [item.lower().replace("’", "'") for item in WORD_RE.findall(text)]


def split_sentences(text: str) -> list[str]:
    return [part.strip() for part in SENTENCE_RE.split(text.strip()) if part.strip()]


def syllable_estimate(word: str) -> int:
    """Return a rough English syllable estimate for readability diagnostics."""
    value = re.sub(r"[^a-z]", "", word.lower())
    if not value:
        return 0
    groups = re.findall(r"[aeiouy]+", value)
    count = len(groups)
    if value.endswith("e") and count > 1 and not value.endswith(("le", "ye")):
        count -= 1
    return max(1, count)


def _recommendations(
    word_count: int,
    average_sentence: float,
    flesch: float | None,
    second_person: int,
    exclamations: int,
) -> list[str]:
    suggestions: list[str] = []
    if word_count < 80:
        suggestions.append("The sample is short; analyze several representative pieces for a stronger baseline.")
    if average_sentence > 25:
        suggestions.append("Consider splitting long sentences where this improves clarity.")
    if flesch is not None and flesch < 40:
        suggestions.append("Review dense passages and explain specialist terms for the intended audience.")
    if second_person == 0:
        suggestions.append("Check whether directly addressing the reader would make the content more useful.")
    if exclamations > max(3, word_count // 100):
        suggestions.append("Review repeated exclamation marks and keep emphasis intentional.")
    if not suggestions:
        suggestions.append("No major heuristic warning was triggered. Compare the sample with approved brand examples.")
    return suggestions


def analyze(text: str) -> dict[str, Any]:
    tokens = words(text)
    sentences = split_sentences(text)
    count = len(tokens)
    sentence_count = len(sentences)
    sentence_lengths = [len(words(sentence)) for sentence in sentences]
    avg_sentence = statistics.mean(sentence_lengths) if sentence_lengths else 0.0
    avg_word_length = statistics.mean([len(w) for w in tokens]) if tokens else 0.0
    syllables = sum(syllable_estimate(w) for w in tokens)
    positive = sum(token in POSITIVE_WORDS for token in tokens)
    negative = sum(token in NEGATIVE_WORDS for token in tokens)
    first_person = sum(token in FIRST_PERSON for token in tokens)
    second_person = sum(token in SECOND_PERSON for token in tokens)
    contractions = len(re.findall(r"\b\w+(?:'t|'re|'ve|'ll|'d|'m)\b", text.lower()))
    exclamations = text.count("!")
    questions = text.count("?")
    formal_hits = sum(token in FORMAL_SIGNALS for token in tokens)
    casual_hits = sum(token in CASUAL_SIGNALS for token in tokens)

    flesch = (
        206.835 - 1.015 * (count / sentence_count) - 84.6 * (syllables / count)
        if count and sentence_count else None
    )

    if formal_hits > casual_hits:
        formality = "more formal signals"
    elif casual_hits > formal_hits or contractions:
        formality = "more conversational signals"
    else:
        formality = "mixed or neutral signals"

    if positive > negative:
        sentiment_hint = "more positive vocabulary"
    elif negative > positive:
        sentiment_hint = "more critical vocabulary"
    else:
        sentiment_hint = "balanced or neutral vocabulary"

    return {
        "word_count": count,
        "sentence_count": sentence_count,
        "average_words_per_sentence": round(avg_sentence, 2),
        "average_word_length": round(avg_word_length, 2),
        "flesch_reading_ease_estimate": round(flesch, 1) if flesch is not None else None,
        "lexical_diversity": round(len(set(tokens)) / count, 3) if count else 0,
        "signals": {
            "formality": formality,
            "vocabulary_tone": sentiment_hint,
            "first_person_references": first_person,
            "second_person_references": second_person,
            "contractions": contractions,
            "exclamation_marks": exclamations,
            "questions": questions,
            "formal_transitions": formal_hits,
            "casual_expressions": casual_hits,
        },
        "recommendations": _recommendations(count, avg_sentence, flesch, second_person, exclamations),
        "limitations": [
            "All style and tone indicators are heuristic, not a definitive brand-voice classification.",
            "Readability estimates are intended for English text and may be inaccurate for names, code, or specialist terminology.",
            "Review samples in context before changing a brand's voice.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze style and readability signals in a text file.")
    parser.add_argument("input_file", type=Path, help="UTF-8 text or Markdown file to analyze")
    parser.add_argument("format", nargs="?", choices=("json", "text"), default="text", help="Output format")
    args = parser.parse_args()

    try:
        source_text = args.input_file.read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"Error: file not found: {args.input_file}", file=sys.stderr)
        return 2
    except (OSError, UnicodeError) as exc:
        print(f"Error: could not read input file ({exc})", file=sys.stderr)
        return 2

    result = analyze(source_text)
    if args.format == "json":
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"Brand voice analysis: {args.input_file}")
        print(f"Words: {result['word_count']} | Sentences: {result['sentence_count']}")
        print(f"Average words per sentence: {result['average_words_per_sentence']}")
        print(f"Average word length: {result['average_word_length']}")
        print(f"Flesch reading ease estimate: {result['flesch_reading_ease_estimate']}")
        print(f"Lexical diversity: {result['lexical_diversity']}")
        for key, value in result["signals"].items():
            print(f"{key.replace('_', ' ').title()}: {value}")
        print("\nRecommendations:")
        for item in result["recommendations"]:
            print(f"- {item}")
        print("\nLimitations:")
        for item in result["limitations"]:
            print(f"- {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
