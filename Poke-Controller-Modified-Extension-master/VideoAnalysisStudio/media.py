"""Offline similarity, durable clip collection, and source-preserving exports."""
import copy
import contextlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

import cv2
import numpy as np

from .detection import SERIAL_ROOT, probe, read_at
from .model import atomic_json, clip_bounds, digest, is_reviewed, number, require_source, signature, view_key

if str(SERIAL_ROOT) not in sys.path:
    sys.path.insert(0, str(SERIAL_ROOT))
import YouTubeArchive as youtube


class Cancelled(Exception):
    pass


def check_cancel(cancel):
    if cancel.is_set():
        raise Cancelled('中止しました。元動画は保持されています。')


def descriptors(project, clips, cancel, progress=None):
    result = []
    cache = {}
    cap, cap_path = None, None
    try:
        for index, clip in enumerate(clips):
            check_cancel(cancel)
            source = project['sources'][clip['source']]
            require_source(source)
            start, end = clip_bounds(project, clip)
            key = digest([source['signature'], start, end, 'five-frame-v1'])
            if key not in cache:
                if cap_path != source['path']:
                    if cap is not None:
                        cap.release()
                    cap, cap_path = cv2.VideoCapture(source['path']), source['path']
                values = []
                for fraction in (.05, .25, .5, .75, .95):
                    check_cancel(cancel)
                    frame, _ = read_at(cap, source, start + (end - start) * fraction)
                    gray = cv2.cvtColor(cv2.resize(frame, (9, 8)), cv2.COLOR_BGR2GRAY)
                    dhash = (gray[:, 1:] > gray[:, :-1]).astype(np.float32).ravel()
                    thumb = cv2.resize(frame, (16, 9)).astype(np.float32).ravel() / 255
                    values.append(np.concatenate([dhash, thumb]))
                require_source(source)
                cache[key] = np.stack(values)
            result.append({'id': clip['id'], 'vector': cache[key], 'duration': end - start})
            if progress:
                progress((index + 1) / max(1, len(clips)), '類似特徴 {}/{}'.format(index + 1, len(clips)))
    finally:
        if cap is not None:
            cap.release()
    return result


def similarity(a, b):
    av, bv = a['vector'], b['vector']
    hash_score = 1 - float(np.mean(np.abs(av[:, :64] - bv[:, :64])))
    color_score = 1 - float(np.mean(np.abs(av[:, 64:] - bv[:, 64:])))
    duration = min(a['duration'], b['duration']) / max(a['duration'], b['duration'])
    return max(0.0, min(1.0, .55 * hash_score + .35 * color_score + .10 * duration))


def group_descriptors(items, threshold, cancel, progress=None):
    """Every member must match its representative; no transitive deduplication."""
    threshold = number(threshold, .5, 1, '類似度')
    groups, representatives = [], []
    for index, item in enumerate(items):
        check_cancel(cancel)
        best, score = -1, -1.0
        for group_index, representative in enumerate(representatives):
            if group_index % 128 == 0:
                check_cancel(cancel)
            value = similarity(item, representative)
            if value > score:
                best, score = group_index, value
        if best < 0 or score < threshold:
            representatives.append(item)
            groups.append({'representative': item['id'], 'members': [{'id': item['id'], 'score': 1.0}],
                           'threshold': threshold, 'reviewed': False})
        else:
            groups[best]['members'].append({'id': item['id'], 'score': score})
        if progress and index % 50 == 0:
            progress((index + 1) / max(1, len(items)), '類似グループ {}/{}'.format(index + 1, len(items)))
    for group in groups:
        group['members'].sort(key=lambda m: (-m['score'], m['id']))
    return sorted(groups, key=lambda g: (-len(g['members']), g['representative']))


def group_clips(project, clips, threshold, cancel, progress=None):
    groups = group_descriptors(descriptors(project, clips, cancel, progress), threshold, cancel, progress)
    return groups, view_key(project)


def playlist(project, clips):
    result = []
    for clip in clips:
        source = copy.deepcopy(project['sources'][clip['source']])
        require_source(source)
        start, end = clip_bounds(project, clip)
        result.append({'source': source, 'start': start, 'end': end,
                       'clip_id': clip['id'], 'label': clip['rule_name']})
    return result


def split_plan(items, merge=True, seconds=0):
    """Split across clip boundaries without losing or repeating source time."""
    limit = number(seconds, 0, 11 * 3600, '分割秒数')
    groups, current, elapsed = [], [], 0.0
    for item in items:
        cursor, end = float(item['start']), float(item['end'])
        if end <= cursor:
            raise ValueError('出力区間が空です。')
        while cursor < end - 1e-8:
            duration = min(end - cursor, limit - elapsed) if limit else end - cursor
            part = copy.deepcopy(item)
            part.update(start=cursor, end=cursor + duration)
            current.append(part)
            cursor += duration
            elapsed += duration
            if limit and elapsed >= limit - 1e-8:
                groups.append(current)
                current, elapsed = [], 0.0
        if not merge and current:
            groups.append(current)
            current, elapsed = [], 0.0
    if current:
        groups.append(current)
    return groups


def ffmpeg_path():
    executable, _ = youtube._ffmpeg_tools()
    if not executable:
        raise RuntimeError('FFmpegが見つかりません。PokeConの動画作成環境を確認してください。')
    return executable


def run_process(command, cancel):
    check_cancel(cancel)
    options = {'stdin': subprocess.DEVNULL, 'stdout': subprocess.DEVNULL}
    if os.name == 'nt':
        options['creationflags'] = (getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000)
                                    | getattr(subprocess, 'BELOW_NORMAL_PRIORITY_CLASS', 0x4000))
    with tempfile.TemporaryFile() as errors:
        with subprocess.Popen(command, stderr=errors, **options) as process:
            while process.poll() is None:
                if cancel.wait(.1):
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                    raise Cancelled('動画作成を中止しました。')
            if process.returncode:
                errors.seek(0)
                raise RuntimeError(errors.read().decode('utf-8', errors='replace')[-2500:])


def has_audio(path):
    ffmpeg, ffprobe = youtube._ffmpeg_tools()
    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000) if os.name == 'nt' else 0
    if ffprobe:
        command = [ffprobe, '-v', 'error', '-select_streams', 'a:0', '-show_entries',
                   'stream=index', '-of', 'csv=p=0', str(path)]
        result = subprocess.run(command, capture_output=True, timeout=30, creationflags=flags)
        if result.returncode:
            raise RuntimeError('音声情報を読めません: ' + str(path))
        return bool(result.stdout.strip())
    result = subprocess.run([ffmpeg, '-hide_banner', '-i', str(path)], capture_output=True,
                            timeout=30, creationflags=flags)
    return b'Audio:' in result.stderr


def export_plan(items, destination, merge, seconds, cancel, progress=None):
    """Always create a new run directory; never replace or delete input media."""
    plan = split_plan(items, merge, seconds)
    if not plan:
        raise ValueError('出力する動画がありません。')
    executable = ffmpeg_path()
    root = Path(destination) / ('export_' + time.strftime('%Y%m%d_%H%M%S') + '_' + uuid.uuid4().hex[:8])
    root.mkdir(parents=True, exist_ok=False)
    manifest = {'version': 1, 'status': 'running', 'plan': plan, 'outputs': []}
    atomic_json(root / 'manifest.json', manifest)
    first = items[0]['source']
    width, height = max(2, first['width'] // 2 * 2), max(2, first['height'] // 2 * 2)
    fps = first['fps']
    audio_cache = {}
    total = sum(len(group) for group in plan)
    done = 0
    try:
        for group_index, group in enumerate(plan):
            check_cancel(cancel)
            output = root / ('part_{:04d}.mp4'.format(group_index + 1))
            with tempfile.TemporaryDirectory(prefix='render_', dir=str(root)) as working:
                parts = []
                for index, item in enumerate(group):
                    source = item['source']
                    require_source(source)
                    path = source['path']
                    if path not in audio_cache:
                        audio_cache[path] = has_audio(path)
                    # PCM intermediates avoid adding AAC encoder padding at every join.
                    part = Path(working) / ('clip_{:06d}.mkv'.format(index))
                    duration = item['end'] - item['start']
                    command = [executable, '-hide_banner', '-loglevel', 'error', '-nostdin', '-y',
                               '-threads', '2', '-ss', '{:.9f}'.format(item['start']), '-i', path]
                    if not audio_cache[path]:
                        command += ['-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo']
                    command += ['-t', '{:.9f}'.format(duration), '-map', '0:v:0', '-map',
                                '0:a:0' if audio_cache[path] else '1:a:0',
                                '-vf', 'scale={}:{}:force_original_aspect_ratio=decrease,pad={}:{}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={:.9f}'.format(width, height, width, height, fps),
                                '-c:v', 'libx264', '-threads', '2', '-filter_threads', '1',
                                '-preset', 'veryfast', '-crf', '18', '-pix_fmt', 'yuv420p',
                                '-c:a', 'pcm_s16le', '-ar', '48000', '-ac', '2',
                                '-af', 'aresample=async=1:first_pts=0,apad', str(part)]
                    run_process(command, cancel)
                    require_source(source)
                    parts.append(part)
                    done += 1
                    if progress:
                        progress(done / total, '動画作成 {}/{}'.format(done, total))
                pending = root / ('part_{:04d}.pending.mp4'.format(group_index + 1))
                listing = Path(working) / 'concat.txt'
                listing.write_text(''.join("file '{}'\n".format(p.as_posix().replace("'", "'\\''"))
                                           for p in parts), encoding='utf-8')
                run_process([executable, '-hide_banner', '-loglevel', 'error', '-nostdin', '-y',
                             '-f', 'concat', '-safe', '0', '-i', str(listing), '-c:v', 'copy',
                             '-c:a', 'aac', '-ar', '48000', '-ac', '2',
                             '-movflags', '+faststart', str(pending)], cancel)
                expected = sum(p['end'] - p['start'] for p in group)
                measured = probe(pending)
                if abs(measured['duration'] - expected) > max(.25, len(group) * 2 / fps):
                    raise ValueError('作成動画の長さが予定と一致しません。出力は未完了として保持します。')
                os.replace(pending, output)
            manifest['outputs'].append(str(output))
            atomic_json(root / 'manifest.json', manifest)
        for item in items:
            require_source(item['source'])
        manifest['status'] = 'complete'
    except Exception as error:
        manifest.update(status='cancelled' if isinstance(error, Cancelled) else 'failed', error=str(error))
        atomic_json(root / 'manifest.json', manifest)
        raise
    atomic_json(root / 'manifest.json', manifest)
    return manifest


class Library:
    """SQLite serializes additions from multiple studios; clips own their media."""
    def __init__(self, directory):
        self.root = Path(directory).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = self.root / 'library.sqlite3'
        with self.connect() as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS clips (id TEXT PRIMARY KEY, metadata TEXT NOT NULL)')

    @contextlib.contextmanager
    def connect(self):
        connection = sqlite3.connect(str(self.db), timeout=30)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def entries(self):
        with self.connect() as conn:
            return [json.loads(row[0]) for row in conn.execute('SELECT metadata FROM clips ORDER BY rowid')]

    def add(self, project, clips, cancel, progress=None):
        entries = []
        for index, clip in enumerate(clips):
            check_cancel(cancel)
            items = playlist(project, [clip])
            key = digest([items[0]['source']['signature'], items[0]['start'], items[0]['end']])
            with self.connect() as conn:
                exists = conn.execute('SELECT metadata FROM clips WHERE id=?', (key,)).fetchone()
            if exists:
                saved = json.loads(exists[0])
                actual = signature(saved['path'])
                if saved.get('media_signature') and actual != saved['media_signature']:
                    raise ValueError('既存の蓄積動画が変更されています: ' + saved['path'])
                if is_reviewed(project, clip) and not saved.get('reviewed'):
                    saved.update(reviewed=True, clip=copy.deepcopy(clip))
                    with self.connect() as conn:
                        conn.execute('UPDATE clips SET metadata=? WHERE id=?',
                                     (json.dumps(saved, ensure_ascii=False), key))
                    atomic_json(Path(saved['path']).parent / 'provenance.json', saved)
                entries.append(saved)
                continue
            result = export_plan(items, self.root / 'media', False, 0, cancel)
            groups = [copy.deepcopy(g) for g in project['groups']
                      if project['group_key'] == view_key(project)
                      and any(m['id'] == clip['id'] for m in g['members'])]
            metadata = {'id': key, 'clip': copy.deepcopy(clip), 'source': items[0]['source'],
                        'start': items[0]['start'], 'end': items[0]['end'],
                        'path': result['outputs'][0], 'groups_at_review': groups,
                        'media_signature': signature(result['outputs'][0]),
                        'reviewed': is_reviewed(project, clip), 'added_at': time.time()}
            atomic_json(Path(metadata['path']).parent / 'provenance.json', metadata)
            with self.connect() as conn:
                conn.execute('INSERT OR IGNORE INTO clips VALUES (?,?)',
                             (key, json.dumps(metadata, ensure_ascii=False)))
                saved = conn.execute('SELECT metadata FROM clips WHERE id=?', (key,)).fetchone()
            entries.append(json.loads(saved[0]))
            if progress:
                progress((index + 1) / len(clips), '蓄積 {}/{}'.format(index + 1, len(clips)))
        return entries


def queue_uploads(paths, settings_path, profile_name, segment_seconds, session_root, cancel):
    """Use the existing channel credentials/queue; never schedule source deletion."""
    store_path = youtube.channel_store_path(settings_path)
    store = youtube.load_channel_store(store_path)
    selected = profile_name or store.get('default_profile', '')
    profile = store.get('profiles', {}).get(selected)
    if not profile or not profile.get('channel_id'):
        raise ValueError('PokeConと共通のYouTube設定でチャンネル認証を行ってください。')
    queue_dir = youtube.upload_queue_dir(settings_path)
    results = []
    for path in paths:
        check_cancel(cancel)
        source = probe(path)
        session = Path(session_root) / digest(source['signature'])[:24]
        session.mkdir(parents=True, exist_ok=True)
        require_source(source)
        job = youtube.enqueue_upload_job(
            queue_dir, str(path), str(session), input_set='VideoAnalysisStudio',
            channel_profile=selected, channel_profile_resolved=selected,
            channel_id_resolved=profile['channel_id'], recording_kind='video_analysis',
            command=Path(path).stem, delete_local=False, segment_seconds=int(segment_seconds))
        if not job:
            raise RuntimeError('既存キューとの競合があるため登録できません: ' + str(path))
        results.append(job)
    if results:
        youtube.launch_upload_worker(queue_dir, store_path)
    return results
