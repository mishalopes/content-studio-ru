#!/usr/bin/env python3
"""Russian-aware editorial checks and approximate speech timing, not a predictor."""
import argparse
import json
import math
import re
import sys

WORD = re.compile(r"[^\W_]+(?:[-'’][^\W_]+)*", re.UNICODE)
HASHTAG = re.compile(r"(?<!\w)#([^\W]+)", re.UNICODE)
LINK = re.compile(r"https?://\S+|www\.\S+", re.I)
CLICHES = [r"в современном мире", r"погруз\w* в мир", r"раскро\w* потенциал",
           r"не просто.{0,70}(?:а |это )", r"уникальная возможность"]

def analyse(text, wpm=165, mode='script', target=None, caption_limit=2200):
    if not math.isfinite(wpm) or wpm <= 0:
        raise ValueError('wpm must be finite and positive')
    if mode not in {'script', 'hook', 'caption'}:
        raise ValueError('mode must be script, hook or caption')
    if target is not None and (not math.isfinite(target) or target <= 0):
        raise ValueError('target must be finite and positive')
    if caption_limit <= 0:
        raise ValueError('caption_limit must be positive')
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    counts = [len(WORD.findall(line)) for line in lines]
    n = sum(counts)
    point = n * 60 / wpm
    notes = []
    if text.strip() and not n:
        notes.append('Нет слов: это может быть изображение, символы или эмодзи.')
    if '—' in text:
        notes.append('Есть длинное тире: сверить с голосом автора.')
    for pattern in CLICHES:
        if re.search(pattern, text, re.I):
            notes.append('Проверить штамп: ' + pattern)
    if mode != 'caption' and counts and counts[0] * 60 / wpm > 3:
        notes.append('Первая реплика длиннее примерно 3 секунд; проверить начало на слух.')
    long = [i+1 for i, count in enumerate(counts) if count * 60 / wpm > 5]
    if mode != 'caption' and long:
        notes.append('Длинные реплики, проверить кадр/паузу: ' + ', '.join(map(str, long)))
    if not text.strip():
        notes.append('Пустой текст.')
    if mode == 'caption':
        if len(text.strip()) > caption_limit:
            notes.append(f'Подпись длиннее заданного лимита {caption_limit} символов.')
        first_line = lines[0] if lines else ''
        if len(first_line) > 125:
            notes.append('Первая строка может обрезаться. Проверить предпросмотр в приложении.')
        if first_line.startswith(('#', '@')):
            notes.append('Первая строка начинается с тега или упоминания. Проверить замысел.')
        if LINK.search(text):
            notes.append('В подписи есть ссылка. Проверить доступность перехода в выбранном формате.')
    return {'words': n, 'characters': len(text), 'wpm': wpm, 'mode': mode,
            'estimated_speech_seconds': round(point, 1),
            'planning_range_seconds': [round(point*.8, 1), round(point*1.25, 1)],
            'timing_note': 'Условный диапазон ±темп, не статистический интервал. Паузы, демонстрации и произнесение чисел не учтены.',
            'caption_preview_approx_125': text.strip()[:125],
            'hashtags': ['#' + tag for tag in HASHTAG.findall(text)],
            'target_seconds': target,
            'difference_from_target_seconds': round(point-target, 1) if target is not None else None,
            'caption_limit': caption_limit if mode == 'caption' else None,
            'text_changed': False,
            'lines': [{'line': i+1, 'words': count,
                       'start_seconds': round(sum(counts[:i])*60/wpm, 1),
                       'estimated_seconds': round(count*60/wpm, 1)}
                      for i, count in enumerate(counts)],
            'editorial_flags': notes}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', nargs='?', default='-')
    parser.add_argument('--wpm', type=float, default=165)
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--mode', choices=['script', 'hook', 'caption'], default='script')
    parser.add_argument('--target', type=float, help='Желаемая длительность речи в секундах')
    parser.add_argument('--caption-limit', type=int, default=2200)
    args = parser.parse_args()
    if not math.isfinite(args.wpm) or args.wpm <= 0:
        parser.error('--wpm must be finite and positive')
    if args.target is not None and (not math.isfinite(args.target) or args.target <= 0):
        parser.error('--target must be finite and positive')
    if args.caption_limit <= 0:
        parser.error('--caption-limit must be positive')
    if args.input == '-':
        text = sys.stdin.read()
    else:
        with open(args.input, encoding='utf-8') as source:
            text = source.read()
    result = analyse(text, args.wpm, args.mode, args.target, args.caption_limit)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Слов: {result['words']}; примерная речь: {result['estimated_speech_seconds']} с")
        print('Это оценка по тексту; проверить по записи.')
        for note in result['editorial_flags']:
            print('- ' + note)

if __name__ == '__main__':
    main()
