#!/usr/bin/env python3
"""Validate a finished short-video series without editing its files."""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


def validate(args):
    if not shutil.which('ffprobe') or (args.full_decode and not shutil.which('ffmpeg')):
        raise ValueError('ffprobe and, for --full-decode, ffmpeg must be available')
    rows = json.loads(Path(args.manifest).read_text(encoding='utf-8'))
    if not isinstance(rows, list) or len(rows) != args.expected:
        raise ValueError(f'Expected {args.expected} manifest rows')
    if not all(isinstance(row, dict) for row in rows):
        raise ValueError('Each manifest row must be an object')
    ids = [str(row.get('id', '')).zfill(2) for row in rows]
    if ids != [f'{n:02}' for n in range(1, args.expected + 1)]:
        raise ValueError('IDs must be ordered, unique and consecutive from 01')
    errors, verified = [], []
    for row, number in zip(rows, ids):
        try:
            for key in ('topic', 'hook', 'caption'):
                if not isinstance(row.get(key), str) or not row[key].strip():
                    raise ValueError(f'Missing text: {key}')
            path = Path(args.video_dir) / f'{number}.mp4'
            if not path.is_file() or path.stat().st_size == 0:
                raise ValueError(f'Missing or empty video: {path}')
            result = subprocess.run(['ffprobe', '-v', 'error', '-show_format', '-show_streams', '-of', 'json', str(path)], capture_output=True, text=True)
            if result.returncode:
                raise ValueError(result.stderr.strip() or 'ffprobe failed')
            data = json.loads(result.stdout)
            videos = [s for s in data.get('streams', []) if s.get('codec_type') == 'video']
            if len(videos) != 1:
                raise ValueError('Expected exactly one video stream')
            video = videos[0]
            if (video.get('width'), video.get('height')) != (args.width, args.height):
                raise ValueError('Wrong video dimensions')
            if video.get('codec_name') != 'h264' or video.get('pix_fmt') != 'yuv420p':
                raise ValueError('Expected H.264 with yuv420p')
            duration = float(data['format']['duration'])
            if not 4.95 <= duration <= 7.05:
                raise ValueError(f'Duration outside 5–7 seconds: {duration}')
            if args.require_audio and not any(s.get('codec_type') == 'audio' for s in data['streams']):
                raise ValueError('Required audio stream missing')
            if args.full_decode:
                decoded = subprocess.run(['ffmpeg', '-v', 'error', '-threads', '1', '-i', str(path), '-f', 'null', '-'], capture_output=True, text=True)
                if decoded.returncode or decoded.stderr.strip():
                    raise ValueError(decoded.stderr.strip() or 'Full decode failed')
            verified.append(number)
        except (ValueError, KeyError, OSError, json.JSONDecodeError) as error:
            errors.append({'id': number, 'error': str(error)})
    return {'expected': args.expected, 'verified': verified, 'errors': errors, 'full_decode': args.full_decode}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--video-dir', required=True)
    parser.add_argument('--expected', type=int, default=50)
    parser.add_argument('--width', type=int, default=1080)
    parser.add_argument('--height', type=int, default=1920)
    parser.add_argument('--require-audio', action='store_true')
    parser.add_argument('--full-decode', action='store_true')
    args = parser.parse_args()
    try:
        report = validate(args)
    except (ValueError, OSError, json.JSONDecodeError) as error:
        print(json.dumps({'error': str(error)}, ensure_ascii=False))
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report['errors'] else 0


if __name__ == '__main__':
    sys.exit(main())
