# -*- coding: utf-8 -*-
"""Shared runtime language state for the integrated PileAnalysis desktop."""

from __future__ import annotations

import os


LANGUAGE_ENV_KEY = "PILE_UI_LANGUAGE"
DEFAULT_LANGUAGE = "en"
SUPPORTED_LANGUAGES = {"en", "zh"}


def normalize_language(language: str | None) -> str:
    if not language:
        return DEFAULT_LANGUAGE
    language = str(language).strip().lower()
    if language.startswith("zh"):
        return "zh"
    if language.startswith("en"):
        return "en"
    return DEFAULT_LANGUAGE


def set_language(language: str | None) -> str:
    normalized = normalize_language(language)
    os.environ[LANGUAGE_ENV_KEY] = normalized
    return normalized


def get_language() -> str:
    return normalize_language(os.environ.get(LANGUAGE_ENV_KEY, DEFAULT_LANGUAGE))


def is_chinese() -> bool:
    return get_language() == "zh"


def is_english() -> bool:
    return get_language() == "en"
