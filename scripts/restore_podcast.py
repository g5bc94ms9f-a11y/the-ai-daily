#!/usr/bin/env python3
"""Include the last *successfully generated* podcast during a news-first deploy.

No generated audio is synthesized or invented here. The archived MP3 and its
exact episode metadata must both exist; otherwise the website simply has no
podcast audio until the background job succeeds.
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent.parent
ARCHIVE_DIR = ROOT / 'data' / 'podcast'
EDITION_FILE = ROOT / 'data' / 'edition.js'
PUBLIC_AUDIO = ROOT / 'public' / 'audio' / 'today.mp3'


def restore_episode():
    archive_audio = ARCHIVE_DIR / 'today.mp3'
    archive_meta = ARCHIVE_DIR / 'episode.json'
    if not archive_audio.is_file() or not archive_meta.is_file():
        print('No previously successful podcast; the news edition will publish without audio.')
        return False
    try:
        if archive_audio.stat().st_size < 10000:
            raise ValueError('Previous MP3 is too small')
        meta = json.loads(archive_meta.read_text(encoding='utf-8'))
        when = datetime.fromisoformat(str(meta['publishedAt']).replace('Z', '+00:00'))
        if when.tzinfo is None:
            raise ValueError('Podcast timestamp lacks timezone')
        if when > datetime.now(timezone.utc) + timedelta(minutes=10):
            raise ValueError('Podcast timestamp is in the future')
        if datetime.now(timezone.utc) - when > timedelta(days=14):
            print('Last successful episode is older than 14 days; not replaying stale news.')
            return False
        if not (meta.get('audioUrl') and meta.get('lines') and meta.get('hosts') == ['Maya', 'Ben']):
            raise ValueError('Podcast archive metadata is incomplete')
        raw = EDITION_FILE.read_text(encoding='utf-8').strip()
        prefix = 'window.AI_EDIT = '
        if not raw.startswith(prefix):
            raise ValueError('Edition file format is unexpected')
        edition = json.loads(raw[len(prefix):].removesuffix(';'))
        # The archive clearly labels the older episode; it is never described
        # as a new recording for today's fresh news edition.
        meta['blurb'] = 'Last successful episode (' + when.strftime('%b %d, %Y') + '). A newer conversation is being prepared.'
        meta['note'] = str(meta.get('note', '')) + ' Last successful recording: ' + when.strftime('%Y-%m-%d %H:%M UTC') + '.'
        edition['podcast'] = meta
        PUBLIC_AUDIO.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(archive_audio, PUBLIC_AUDIO)
        EDITION_FILE.write_text(prefix + json.dumps(edition, ensure_ascii=False, separators=(',', ':')) + ';\n', encoding='utf-8')
        print('Restored last successful recorded episode from', when.isoformat())
        return True
    except (KeyError, TypeError, ValueError, OSError, json.JSONDecodeError) as exc:
        print('Cannot restore archived podcast:', type(exc).__name__, str(exc)[:200])
        return False


if __name__ == '__main__':
    restore_episode()
