"""Spot text that is keyboard mashing rather than real words.

Used on titles, authors, chapter names and lesson names, both inline (the
family sees "That doesn't look like a real title. Fix it?") and by the
community catalog's checks. Deliberately cautious: it only fires on strong
signals, so real titles in other languages ("Lingua Latina"), codes ("Saxon
5/4", "BJU") and odd-but-real words pass.
"""

from __future__ import annotations

import re

_VOWELS = set("aeiouy")
_KEY_ROWS = ("qwertyuiop", "asdfghjkl", "zxcvbnm", "1234567890")
_WORD = re.compile(r"[a-z]+")


def _longest_consonant_run(word: str) -> int:
    longest = run = 0
    for char in word:
        run = 0 if char in _VOWELS else run + 1
        longest = max(longest, run)
    return longest


def _keyboard_run(word: str, length: int = 5) -> bool:
    for row in _KEY_ROWS:
        for start in range(len(row) - length + 1):
            chunk = row[start : start + length]
            if chunk in word or chunk[::-1] in word:
                return True
    return False


def _repeating_pattern(word: str) -> bool:
    """'sdfsdfsdf', 'abababab': a short chunk repeated to fill a long word."""
    if len(word) < 8:
        return False
    for size in (2, 3, 4):
        chunk = word[:size]
        if chunk * (len(word) // size) == word[: size * (len(word) // size)] and len(word) // size >= 3:
            return True
    return False


def keyboard_mash_reason(text: str | None) -> str | None:
    """Why ``text`` looks like keyboard mashing, or None when it looks like words."""
    if not text:
        return None
    lowered = text.lower()
    if re.search(r"(.)\1{4,}", lowered):
        return "the same character repeats"
    for word in _WORD.findall(lowered):
        if len(word) < 6:
            continue
        if _longest_consonant_run(word) >= 6:
            return f'"{word}" has no vowels where real words have them'
        if _keyboard_run(word):
            return f'"{word}" runs along the keyboard'
        if _repeating_pattern(word):
            return f'"{word}" repeats the same few letters'
        if len(word) >= 10 and sum(char in _VOWELS for char in word) / len(word) < 0.2:
            return f'"{word}" has too few vowels to be a word'
    return None
