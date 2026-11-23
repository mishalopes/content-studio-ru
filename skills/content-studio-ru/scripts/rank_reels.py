#!/usr/bin/env python3
"""Rank supplied comparable Reels, preserving missing values and baseline provenance."""

import argparse
import csv
import io
import json
import re
import statistics
import sys
from collections import defaultdict
from decimal import Decimal, InvalidOperation


COUNT_FIELDS = ('views', 'reach', 'shares', 'saves', 'baseline_n')
MISSING = {'', 'null', 'none', 'na', 'n/a'}


def parse_number(value, field, line, integer=True):
    raw = (value or '').strip()
    if raw.lower() in MISSING:
        return None
    compact = re.sub(r'[\s\u00a0\u202f]', '', raw)
    # Commas are accepted only as thousands separators. Decimal fractions use a dot.
    if ',' in compact:
        if not re.fullmatch(r'\d{1,3}(?:,\d{3})+(?:\.\d+)?', compact):
            raise ValueError(f'Строка {line}, {field}: нужны полные числа, получено {raw!r}')
        compact = compact.replace(',', '')
    try:
        number = Decimal(compact)
    except InvalidOperation as exc:
        raise ValueError(f'Строка {line}, {field}: неверное число {raw!r}') from exc
    if not number.is_finite() or number < 0 or (integer and number != number.to_integral_value()):
        raise ValueError(f'Строка {line}, {field}: нужно конечное неотрицательное число')
    return int(number) if integer else number


def read_rows(text, delimiter=None):
    if not text.strip():
        raise ValueError('Пустая таблица')
    if delimiter is None:
        try:
            delimiter = csv.Sniffer().sniff(text[:8192], delimiters=',\t;').delimiter
        except csv.Error as exc:
            raise ValueError('Не определён разделитель. Указать --delimiter') from exc
    reader = csv.DictReader(io.StringIO(text.lstrip('\ufeff')), delimiter=delimiter)
    required = {'account', 'views'}
    if not required.issubset(reader.fieldnames or []):
        raise ValueError('Обязательные столбцы: account, views')
    rows = []
    seen_urls = set()
    for line, raw in enumerate(reader, 2):
        if None in raw or any(value is None for value in raw.values()):
            raise ValueError(f'Строка {line}: число столбцов не совпадает с заголовком')
        row = {key: value.strip() for key, value in raw.items()}
        if not row['account']:
            raise ValueError(f'Строка {line}: пустой account')
        if row.get('url'):
            if row['url'] in seen_urls:
                raise ValueError(f'Строка {line}: повтор URL {row["url"]}')
            seen_urls.add(row['url'])
        for field in COUNT_FIELDS:
            row[field] = parse_number(row.get(field), field, line)
        row['baseline_median'] = parse_number(row.get('baseline_median'), 'baseline_median', line, integer=False)
        if row['baseline_n'] is not None and row['baseline_median'] is None:
            raise ValueError(f'Строка {line}: baseline_n указан без baseline_median')
        if row['baseline_median'] is not None and row['baseline_n'] == 0:
            raise ValueError(f'Строка {line}: для заданной медианы baseline_n должен быть больше нуля')
        row.setdefault('cohort', '')
        rows.append(row)
    if not rows:
        raise ValueError('В таблице нет строк данных')
    return rows


def analyse(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[(row['account'], row.get('cohort', ''))].append(row)
    results = []
    for group in groups.values():
        for row in group:
            warnings = []
            base = row['baseline_median']
            baseline_n = row['baseline_n']
            if base is not None:
                source = 'provided_baseline_median'
                if baseline_n is None:
                    warnings.append('Размер внешней базы не указан')
            else:
                sample = [item['views'] for item in group if item is not row and item['views'] is not None]
                base = statistics.median(sample) if sample else None
                baseline_n = len(sample)
                source = 'same_account_cohort_excluding_current'
                warnings.append('База рассчитана по переданным сопоставимым роликам без текущего')
            if base is None or base == 0:
                warnings.append('Относительный результат не рассчитан: база отсутствует или равна нулю')
            if row['views'] is None:
                warnings.append('Просмотры отсутствуют')
            if baseline_n is not None and baseline_n < 5:
                warnings.append('Малая база сравнения, использовать как описательный ориентир')
            reach = row['reach']
            if reach is None or reach == 0:
                warnings.append('Показатели на охват не рассчитаны: охват отсутствует или равен нулю')
            multiple = float(Decimal(row['views']) / Decimal(str(base))) if row['views'] is not None and base else None
            rates = {}
            for metric in ('shares', 'saves'):
                value = row[metric]
                rates[metric + '_per_reach_pct'] = round(100 * value / reach, 4) if value is not None and reach else None
            result = dict(row)
            result['baseline_median'] = float(base) if base is not None else None
            result.update(baseline_n=baseline_n, baseline_source=source,
                          outlier_multiple=round(multiple, 4) if multiple is not None else None,
                          warnings=warnings, **rates)
            results.append(result)
    results.sort(key=lambda row: (row['outlier_multiple'] is None, -(row['outlier_multiple'] or 0)))
    return {'rows': results, 'count': len(results),
            'notes': ['Сопоставимость формата, периода и возраста роликов задаётся входной выборкой.',
                      'Множитель и проценты описывают данные, причинность из них не следует.',
                      'Подписчики не используются вместо медианы просмотров.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', nargs='?', default='-')
    parser.add_argument('--delimiter', choices=['comma', 'tab', 'semicolon'])
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    if args.input == '-':
        text = sys.stdin.read()
    else:
        with open(args.input, encoding='utf-8-sig') as source:
            text = source.read()
    delimiter = {'comma': ',', 'tab': '\t', 'semicolon': ';'}.get(args.delimiter)
    try:
        result = analyse(read_rows(text, delimiter))
    except ValueError as exc:
        parser.error(str(exc))
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    else:
        for row in result['rows']:
            multiple = f"{row['outlier_multiple']:.2f}×" if row['outlier_multiple'] is not None else 'нет базы'
            print(f"{row['account']} | {row.get('url', '')} | {multiple} | база n={row['baseline_n']}")
            for warning in row['warnings']:
                print('  - ' + warning)


if __name__ == '__main__':
    main()
