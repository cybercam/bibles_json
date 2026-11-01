#!/usr/bin/env python3
"""Split the big bible_<version>.json files into one small JSON file per chapter.

Why: the website Worker (bsws-bible-dynamic) parsed a whole 4-12 MB Bible on every request and
ran over Cloudflare's free CPU limit. With this, it fetches only ~5-20 KB per page:

  chapters/<version>/index.json           [{"b": 1, "n": "Genesis", "chapters": 50}, ...]
  chapters/<version>/<b>/<c>.json         {"b": 1, "n": "Genesis", "c": 1, "v": {"1": "...", ...}}
  crossrefs/<b>/<c>.json                  {"<verse>": ["2_20_11", ...], ...}   (if crossrefs_mobile.json is given)

Book numbering matches the Worker's normalizeBibleData(): "Book12" keys, English names, else file order.
Usage: python3 scripts/split_chapters.py [--crossrefs path/to/crossrefs_mobile.json]
"""
import argparse
import glob
import json
import os
import re
import shutil

ENGLISH_BOOK_NUM = {n: i + 1 for i, n in enumerate([
    'Genesis', 'Exodus', 'Leviticus', 'Numbers', 'Deuteronomy', 'Joshua', 'Judges', 'Ruth', '1 Samuel', '2 Samuel',
    '1 Kings', '2 Kings', '1 Chronicles', '2 Chronicles', 'Ezra', 'Nehemiah', 'Esther', 'Job', 'Psalms', 'Proverbs',
    'Ecclesiastes', 'Song of Solomon', 'Isaiah', 'Jeremiah', 'Lamentations', 'Ezekiel', 'Daniel', 'Hosea', 'Joel',
    'Amos', 'Obadiah', 'Jonah', 'Micah', 'Nahum', 'Habakkuk', 'Zephaniah', 'Haggai', 'Zechariah', 'Malachi',
    'Matthew', 'Mark', 'Luke', 'John', 'Acts', 'Romans', '1 Corinthians', '2 Corinthians', 'Galatians', 'Ephesians',
    'Philippians', 'Colossians', '1 Thessalonians', '2 Thessalonians', '1 Timothy', '2 Timothy', 'Titus', 'Philemon',
    'Hebrews', 'James', '1 Peter', '2 Peter', '1 John', '2 John', '3 John', 'Jude', 'Revelation'])}
ENGLISH_BOOK_NUM.update({'Psalm': 19, 'Song of Songs': 22})


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, separators=(',', ':'))


def split_bible(src, out_root):
    version = re.match(r'bible_(.+)\.json$', os.path.basename(src)).group(1)
    with open(src, encoding='utf-8') as f:
        raw = json.load(f)
    out = os.path.join(out_root, 'chapters', version)
    shutil.rmtree(out, ignore_errors=True)
    index = []
    # Already-normalized files: {"books": [{"b": 1, "n": "Genesis", "ch": [{"c": 1, "v": {...}}]}]}
    if isinstance(raw, dict) and isinstance(raw.get('books'), list):
        for book in raw['books']:
            b = int(book.get('b'))
            count = 0
            for ch in book.get('ch') or []:
                c = int(ch.get('c'))
                v = {str(k): str(t).strip() for k, t in (ch.get('v') or {}).items() if str(t or '').strip()}
                write_json(os.path.join(out, str(b), f'{c}.json'), {'b': b, 'n': book.get('n'), 'c': c, 'v': v})
                count = max(count, c)
            index.append({'b': b, 'n': book.get('n'), 'chapters': count})
        index.sort(key=lambda x: x['b'])
        write_json(os.path.join(out, 'index.json'), index)
        return version, len(index)
    for seq, (book_key, chapters) in enumerate(raw.items(), start=1):
        m = re.match(r'^Book(\d+)$', book_key, re.I)
        b = int(m.group(1)) if m else ENGLISH_BOOK_NUM.get(book_key, seq)
        count = 0
        for c_key, verses in (chapters or {}).items():
            if not str(c_key).isdigit() or int(c_key) < 1:
                continue
            v = {str(int(k)): str(t).strip() for k, t in (verses or {}).items()
                 if str(k).isdigit() and int(k) >= 1 and str(t or '').strip()}
            write_json(os.path.join(out, str(b), f'{int(c_key)}.json'), {'b': b, 'n': book_key, 'c': int(c_key), 'v': v})
            count = max(count, int(c_key))
        index.append({'b': b, 'n': book_key, 'chapters': count})
    index.sort(key=lambda x: x['b'])
    write_json(os.path.join(out, 'index.json'), index)
    return version, len(index)


def split_crossrefs(src, out_root):
    with open(src, encoding='utf-8') as f:
        raw = json.load(f)
    by_chapter = {}
    for key, refs in raw.items():
        parts = key.split('_')
        if len(parts) != 3:
            continue
        b, c, v = parts
        by_chapter.setdefault((b, c), {})[v] = refs
    out = os.path.join(out_root, 'crossrefs')
    shutil.rmtree(out, ignore_errors=True)
    for (b, c), verses in by_chapter.items():
        write_json(os.path.join(out, b, f'{c}.json'), verses)
    return len(by_chapter)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default='.')
    ap.add_argument('--crossrefs', help='path to crossrefs_mobile.json')
    args = ap.parse_args()
    for src in sorted(glob.glob(os.path.join(args.root, 'bible_*.json'))):
        version, books = split_bible(src, args.root)
        print(f'{version}: {books} books')
    if args.crossrefs and os.path.exists(args.crossrefs):
        print(f'crossrefs: {split_crossrefs(args.crossrefs, args.root)} chapters')


if __name__ == '__main__':
    main()
