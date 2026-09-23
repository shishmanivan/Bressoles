"""Display-only localization for legacy UI text outside Lang.csv.

Card IDs, save data, names entered by players and game rules are never translated.
The active locale is changed only by the main application, not by catalog reads.
"""
import csv
import json
import re
from functools import lru_cache
from pathlib import Path
from string import Formatter

SUPPORTED_LANGUAGES = ('RU', 'ENG', 'DE', 'HU')
_active_language = 'RU'


def set_language(code):
    global _active_language
    if code not in SUPPORTED_LANGUAGES:
        raise ValueError('Unsupported language')
    _active_language = code


def get_language():
    return _active_language


def translate(text):
    if not isinstance(text, str):
        return text
    return _translate(text, _active_language)


@lru_cache(maxsize=len(SUPPORTED_LANGUAGES))
def _catalog(language):
    path = Path(__file__).parent / 'locales' / 'ui.json'
    data = {}
    with (path.parent.parent / 'Lang.csv').open(encoding='utf-8-sig', newline='') as source:
        for row in csv.DictReader(source, delimiter=';'):
            for code in SUPPORTED_LANGUAGES:
                data[row[code]] = row[language]
    for row in json.loads(path.read_text(encoding='utf-8')):
        for code in ('Source', *SUPPORTED_LANGUAGES):
            data[row[code]] = row[language]
    templates = []
    # Specific messages must win over generic templates such as "Card {v0}".
    ordered = sorted(data.items(), key=lambda pair: sum(len(literal) for literal, _, _, _ in Formatter().parse(pair[0])), reverse=True)
    for source, target in ordered:
        parts = list(Formatter().parse(source))
        if not any(field is not None for _, field, _, _ in parts):
            continue
        pattern = ''
        fields = []
        for literal, field, _, _ in parts:
            pattern += re.escape(literal)
            if field is not None:
                pattern += '(.+?)'
                fields.append(field)
        templates.append((re.compile(pattern, re.DOTALL), fields, target))
    # Long descriptions can be followed by a separate, dynamic effect summary.
    prefixes = sorted((key for key in data if len(key) > 30 and '{' not in key), key=len, reverse=True)
    return data, templates, prefixes


@lru_cache(maxsize=2048)
def _translate(text, language):
    data, templates, prefixes = _catalog(language)
    if text in data:
        return data[text]
    for pattern, fields, target in templates:
        match = pattern.fullmatch(text)
        if match:
            values = {field: _translate(value, language) for field, value in zip(fields, match.groups())}
            return target.format(**values)
    for source in prefixes:
        if text.startswith(source + ' '):
            return data[source] + ' ' + _translate(text[len(source) + 1:], language)
    return text
