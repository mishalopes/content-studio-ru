#!/usr/bin/env python3
"""Validate a single Caption JSON track and optionally export records to SRT.

No speech recognition, network access, automatic text changes or phrase grouping.
"""
import argparse
import json
import math
from pathlib import Path


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def validate(rows, duration_ms=None):
    if not isinstance(rows, list) or not rows:
        raise ValueError('Expected a non-empty array of Caption records')
    previous_end = 0
    for i, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            raise ValueError(f'Record {i}: expected object')
        if not isinstance(row.get('text'), str) or not row['text'].strip():
            raise ValueError(f'Record {i}: expected non-empty text')
        start, end = row.get('startMs'), row.get('endMs')
        if not number(start) or not number(end) or start < 0 or end <= start:
            raise ValueError(f'Record {i}: invalid startMs/endMs')
        if start < previous_end:
            raise ValueError(f'Record {i}: overlapping or unordered single-track intervals')
        if duration_ms is not None and end > duration_ms:
            raise ValueError(f'Record {i}: exceeds media duration')
        stamp, confidence = row.get('timestampMs'), row.get('confidence')
        if stamp is not None and (not number(stamp) or not start <= stamp <= end):
            raise ValueError(f'Record {i}: timestampMs outside interval')
        if confidence is not None and (not number(confidence) or not 0 <= confidence <= 1):
            raise ValueError(f'Record {i}: confidence outside 0..1')
        if 'pageBreakAfter' in row and not isinstance(row['pageBreakAfter'], bool):
            raise ValueError(f'Record {i}: pageBreakAfter must be boolean')
        previous_end = end
    return rows


def timestamp(ms):
    ms = round(ms)
    seconds, millis = divmod(ms, 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f'{hours:02}:{minutes:02}:{seconds:02},{millis:03}'


def export_srt(rows):
    blocks = []
    for i, row in enumerate(rows, 1):
        if round(row['endMs']) <= round(row['startMs']):
            raise ValueError(f'Record {i}: interval too short for millisecond SRT')
        text = row['text'].strip().replace('\r\n', '\n').replace('\r', '\n')
        if any(not line.strip() for line in text.split('\n')):
            raise ValueError(f'Record {i}: blank line would split an SRT block')
        blocks.append(f"{i}\n{timestamp(row['startMs'])} --> {timestamp(row['endMs'])}\n{text}\n")
    return '\n'.join(blocks)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--duration-ms', type=float)
    parser.add_argument('--srt', type=Path, help='New SRT output; existing files are not overwritten')
    args = parser.parse_args()
    try:
        if args.duration_ms is not None and (not number(args.duration_ms) or args.duration_ms <= 0):
            raise ValueError('--duration-ms must be finite and positive')
        if args.srt and args.srt.resolve() == args.input.resolve():
            raise ValueError('Input and output paths must differ')
        rows = validate(json.loads(args.input.read_text(encoding='utf-8-sig')), args.duration_ms)
        if args.srt:
            result = export_srt(rows)
            with args.srt.open('x', encoding='utf-8') as out:
                out.write(result)
        print(json.dumps({'valid': True, 'records': len(rows), 'endMs': rows[-1]['endMs'],
                          'srt': str(args.srt) if args.srt else None,
                          'input_modified': False, 'srt_text_trimmed': bool(args.srt)}, ensure_ascii=False))
    except (OSError, ValueError) as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    main()
