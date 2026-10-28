"""Non-destructive review documents and auditable similarity groups."""
import copy
import hashlib
import json
import math
import os
import tempfile
from pathlib import Path

VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.mov', '.m4v', '.webm', '.mts', '.m2ts', '.wmv'}
GENERATED_DIRS = {'.video_analysis', '.youtube_segments', '__pycache__'}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    allow_nan=False).encode('utf-8')).hexdigest()


def number(value, minimum=0, maximum=86400, label='数値'):
    result = float(value)
    if not math.isfinite(result) or not minimum <= result <= maximum:
        raise ValueError('{}は{}〜{}の有限数で指定してください。'.format(label, minimum, maximum))
    return result


def canonical(path):
    return os.path.normcase(os.path.realpath(os.path.abspath(str(path))))


def signature(path):
    value = os.stat(path)
    return {'path': canonical(path), 'size': value.st_size, 'mtime_ns': value.st_mtime_ns}


def require_source(source):
    if signature(source['path']) != source['signature']:
        raise ValueError('元動画が変更されています。再走査してください: ' + source['path'])


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + '.', suffix='.tmp', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def discover(roots, excluded=(), cancel=None):
    """Deduplicate overlapping roots and avoid junction loops and own exports."""
    found, errors, seen_dirs = {}, [], set()
    excluded = [canonical(p) for p in excluded]

    def excluded_path(path):
        candidate = canonical(path)
        return any(candidate == p or candidate.startswith(p + os.sep) for p in excluded)

    for root in roots:
        if not os.path.isdir(root):
            errors.append('フォルダがありません: ' + str(root))
            continue
        for directory, dirs, files in os.walk(root, followlinks=False,
                                             onerror=lambda error: errors.append(str(error))):
            if cancel and cancel.is_set():
                return sorted(found.values()), errors
            key = canonical(directory)
            if key in seen_dirs or excluded_path(directory):
                dirs[:] = []
                continue
            seen_dirs.add(key)
            dirs[:] = sorted(d for d in dirs if d not in GENERATED_DIRS
                             and not os.path.islink(os.path.join(directory, d))
                             and not getattr(os.path, 'isjunction', lambda p: False)(os.path.join(directory, d))
                             and not excluded_path(os.path.join(directory, d)))
            for name in sorted(files):
                path = os.path.join(directory, name)
                if Path(name).suffix.lower() in VIDEO_EXTENSIONS and not os.path.islink(path):
                    found.setdefault(canonical(path), os.path.abspath(path))
    return sorted(found.values(), key=str.casefold), errors


def new_project():
    return {'version': 1, 'roots': [], 'sources': {}, 'rules': [], 'clips': [],
            'scans': [], 'before': 10.0, 'after': 10.0, 'groups': [], 'group_key': '',
            'library_dir': '', 'upload_runs': []}


def load_project(path):
    with open(path, encoding='utf-8-sig') as stream:
        value = json.load(stream)
    if not isinstance(value, dict) or value.get('version') != 1:
        raise ValueError('対応していない解析プロジェクトです。')
    result = new_project()
    result.update(value)
    for name, kind in [('roots', list), ('sources', dict), ('rules', list),
                       ('clips', list), ('groups', list), ('scans', list)]:
        if not isinstance(result[name], kind):
            raise ValueError('プロジェクトの形式が不正です: ' + name)
    number(result['before']); number(result['after'])
    return result


def clip_bounds(project, clip):
    source = project['sources'][clip['source']]
    before = number(clip.get('before', project['before']))
    after = number(clip.get('after', project['after']))
    start = max(0.0, float(clip['start']) - before)
    end = min(float(source['duration']), float(clip['end']) + after)
    # A point event still has one real frame if both margins are zero.
    end = min(float(source['duration']), max(end, start + 1.0 / source['fps']))
    if end <= start:
        raise ValueError('クリップが動画の範囲外です。')
    return start, end


def make_clip(source_id, rule, start, end, edge, source_signature):
    identity = [source_signature, rule, round(start, 6), round(end, 6), edge]
    return {'id': digest(identity)[:24], 'source': source_id,
            'rule_id': rule['id'], 'rule_name': rule['name'],
            'start': start, 'end': end, 'edge': edge,
            'source_signature': copy.deepcopy(source_signature), 'reviewed': False}


def current_clips(project):
    return [c for c in project['clips'] if c['source'] in project['sources']
            and c['source_signature'] == project['sources'][c['source']]['signature']]


def is_reviewed(project, clip):
    return bool(clip.get('reviewed') and list(clip_bounds(project, clip)) == clip.get('reviewed_view'))


def view_key(project):
    return digest([(c['id'], clip_bounds(project, c),
                    project['sources'][c['source']]['signature']) for c in current_clips(project)])


def ordered_clips(project, order='time', unique=False):
    clips = current_clips(project)
    by_id = {c['id']: c for c in clips}
    if order == 'similarity' or unique:
        if not project['groups'] or project['group_key'] != view_key(project):
            raise ValueError('現在の表示範囲で「類似を解析」を実行してください。')
        ids = []
        for group in project['groups']:
            ids.extend([group['representative']] if unique else
                       [group['representative']] + [m['id'] for m in group['members']
                                                   if m['id'] != group['representative']])
        return [by_id[i] for i in ids if i in by_id]
    return sorted(clips, key=lambda c: (project['sources'][c['source']]['path'].casefold(),
                                       c['start'], c['rule_name']))


def apply_scan(project, source, rule, clips, report):
    """Commit one complete source/rule result; failed scans never erase old evidence."""
    key = canonical(source['path'])
    project['sources'][key] = source
    if report['status'] == 'complete':
        old = {c['id']: c for c in project['clips']}
        for clip in clips:
            for field in ('before', 'after', 'reviewed', 'reviewed_view', 'note'):
                if field in old.get(clip['id'], {}):
                    clip[field] = old[clip['id']][field]
        project['clips'] = [c for c in project['clips'] if not
                            (c['source'] == key and c['rule_id'] == rule['id'])] + clips
    project['scans'].append(report)
    project['groups'], project['group_key'] = [], ''
