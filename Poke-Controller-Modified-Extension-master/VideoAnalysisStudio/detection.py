"""Frozen image predicates, safe source imports and cancellable file scanning."""
import ast
import copy
import configparser
import hashlib
import math
import time
import uuid
from pathlib import Path

import cv2
import numpy as np

from .model import canonical, digest, make_clip, number, require_source, signature

SERIAL_ROOT = Path(__file__).resolve().parents[1] / 'SerialController'


def image_node(variant, name='画像', base=SERIAL_ROOT):
    spec = copy.deepcopy(variant)
    path = Path(spec['template_path'])
    spec['template_path'] = str(path if path.is_absolute() else (Path(base) / path).resolve())
    return {'op': 'image', 'name': name, 'variant': spec}


def target_node(name, variants, operator='OR', base=SERIAL_ROOT):
    children = [image_node(v, '{} [{}]'.format(name, i + 1), base) for i, v in enumerate(variants)]
    if not children:
        raise ValueError('条件画像がありません: ' + name)
    node = {'op': 'all' if operator == 'AND' else 'any', 'name': name, 'children': children}
    if str(operator).startswith('AT_LEAST_'):
        node.update(op='atleast', count=int(operator.rsplit('_', 1)[1]))
    return node


def source_targets(path):
    """Read literal registrations without importing/running a Commands module."""
    tree = ast.parse(Path(path).read_text(encoding='utf-8-sig'))
    values = {'IMAGE_DETECTION_TARGETS': {}, 'IMAGE_DETECTION_OPERATORS': {}}
    for cls in [n for n in tree.body if isinstance(n, ast.ClassDef)]:
        for node in cls.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id in values:
                        values[target.id].update(ast.literal_eval(node.value))
            elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                call = node.value
                if (isinstance(call.func, ast.Attribute) and call.func.attr == 'update'
                        and isinstance(call.func.value, ast.Name)
                        and call.func.value.id in values and len(call.args) == 1):
                    values[call.func.value.id].update(ast.literal_eval(call.args[0]))
    return {name: target_node(name, variants, values['IMAGE_DETECTION_OPERATORS'].get(name, 'OR'))
            for name, variants in values['IMAGE_DETECTION_TARGETS'].items() if variants}


def default_rule():
    """Static frame equivalent of ZA's HardGuard; runtime confirmation is separate."""
    path = SERIAL_ROOT / 'Commands/PythonCommands/ZA/ZA_story/ZA_story.py'
    targets = source_targets(path)
    names = [
        ['POKEMON_ZA_FIELD_W', 'POKEMON_ZA_FIELD_BACK_W'],
        ['POKEMON_ZA_MERIP_ICON_GET5', 'POKEMON_ZA_BATTLE', 'POKEMON_ZA_WANINOKO_ICON',
         'POKEMON_ZA_ODAIRU_ICON', 'POKEMON_ZA_ABSOL_ICON', 'POKEMON_ZA_DEAD'],
        ['POKEMON_ZA_BATTLE_BALL_CHECK', 'POKEMON_ZA_ESCAPE']]
    groups = [{'op': 'any', 'name': label, 'children': [copy.deepcopy(targets[n]) for n in group]}
              for label, group in zip(['フィールド表示', '手持ちアイコン', '戦闘表示'], names)]
    groups[2] = {'op': 'not', 'name': '戦闘表示を除外', 'children': [groups[2]]}
    return {'id': 'za-hard-field', 'name': 'ZA 非戦闘フィールド HARD CHECK',
            'condition': {'op': 'all', 'name': 'HARD CHECK（保存動画の画像条件）', 'children': groups},
            'event': 'both', 'interval': 0.5, 'stable_samples': 2,
            'origin': {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                       'note': '同一保存フレームの画像条件。実機の複数fresh frame確認とは別。'}}


def new_rule():
    return {'id': uuid.uuid4().hex, 'name': '新しい切り抜き条件', 'event': 'both',
            'interval': 0.5, 'stable_samples': 2,
            'condition': {'op': 'all', 'name': 'すべて一致', 'children': []}}


def import_pokecon_rule(settings_path):
    """Copy the recording feature's AND/OR, stability and THEN settings."""
    config = configparser.ConfigParser(interpolation=None)
    with open(settings_path, encoding='utf-8-sig') as stream:
        config.read_file(stream)
    import json
    saved = json.loads(config.get('Recording', 'event_clip_rule', fallback='{}'))
    if not saved.get('stages'):
        raise ValueError('このPokeCon設定には保存済みの切り抜き条件がありません。')
    rule = new_rule()
    groups = []
    for index, stage in enumerate(saved['stages']):
        groups.append({'op': 'all' if stage.get('operator', 'AND') == 'AND' else 'any',
                       'name': '段階{}'.format(index + 1), 'stable_seconds': stage.get('stable_seconds', 0),
                       'children': [target_node(target.get('name', '画像'), target['variants'],
                                                target.get('operator', 'OR')) for target in stage['targets']]})
    rule.update(name='PokeCon 条件クリップ（コピー）', event='enter', interval=saved.get('interval_seconds', .1),
                condition={'op': 'sequence', 'name': 'PokeConと同じ順序・継続条件', 'children': groups,
                           'within_seconds': saved.get('within_seconds', 30),
                           'cooldown_seconds': saved.get('cooldown_seconds', 5)},
                origin={'settings_path': str(settings_path), 'saved_rule': saved},
                suggested_before=saved.get('pre_seconds', 5), suggested_after=saved.get('post_seconds', 5))
    build_matcher(rule['condition'])
    return rule


def region(image, rect):
    if not rect or not any(rect):
        return image, (0, 0)
    if len(rect) != 4:
        raise ValueError('画像範囲は x1,y1,x2,y2 の4値です。')
    x1, y1, x2, y2 = [int(v) for v in rect]
    h, w = image.shape[:2]
    x2, y2 = (x2 if x2 > 0 else w), (y2 if y2 > 0 else h)
    if x1 < 0 or y1 < 0 or x2 <= x1 or y2 <= y1 or x2 > w or y2 > h:
        raise ValueError('条件画像の範囲が動画／画像の外です。解像度と範囲を確認してください。')
    return image[y1:y2, x1:x2], (x1, y1)


class Matcher:
    def __init__(self, condition):
        self.condition = copy.deepcopy(condition)
        self.templates = {}
        self.assets = {}
        self._prepare(self.condition, 0)
        self.key = digest([self.condition, self.assets])

    def _prepare(self, node, depth):
        if depth > 24 or len(self.templates) > 512:
            raise ValueError('条件が大きすぎます。深さ24／画像512個以内にしてください。')
        op = node['op']
        if op == 'image':
            variant = node['variant']
            number(variant.get('threshold', .8), 0, 1, '一致度')
            path = Path(variant['template_path'])
            raw = path.read_bytes()
            if variant.get('sha256') and hashlib.sha256(raw).hexdigest() != variant['sha256']:
                raise ValueError('PokeConで保存した条件画像が変更されています。条件を保存し直してください: ' + str(path))
            if len(raw) > 16 * 1024 * 1024:
                raise ValueError('条件画像は16MB以内にしてください。')
            template = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
            if template is None:
                raise ValueError('条件画像を読めません: ' + str(path))
            template, _ = region(template, variant.get('template_crop'))
            if variant.get('use_gray', True):
                template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
            if float(np.std(template)) < .01:
                raise ValueError('単色の条件画像では画像一致を判定できません: ' + str(path))
            self.templates[id(node)] = template
            self.assets[str(path)] = hashlib.sha256(raw).hexdigest()
        else:
            if op not in ('all', 'any', 'not', 'atleast') or not node.get('children'):
                raise ValueError('条件グループに画像またはグループを追加してください。')
            if op == 'not' and len(node['children']) != 1:
                raise ValueError('除外グループは1個の条件グループを指定してください。')
            if op == 'atleast':
                number(node.get('count', 0), 1, len(node['children']), '必要一致数')
            for child in node['children']:
                self._prepare(child, depth + 1)

    def verify_assets(self):
        for path, expected in self.assets.items():
            if hashlib.sha256(Path(path).read_bytes()).hexdigest() != expected:
                raise ValueError('解析中に条件画像が変更されました: ' + path)

    def match(self, frame):
        return self._match(self.condition, frame)

    def _match(self, node, frame):
        op = node['op']
        if op != 'image':
            if op == 'all':
                return all(self._match(c, frame) for c in node['children'])
            if op == 'any':
                return any(self._match(c, frame) for c in node['children'])
            if op == 'not':
                return not self._match(node['children'][0], frame)
            return sum(self._match(c, frame) for c in node['children']) >= node['count']
        variant = node['variant']
        source, offset = region(frame, variant.get('crop'))
        if variant.get('use_gray', True):
            source = cv2.cvtColor(source, cv2.COLOR_BGR2GRAY)
        template = self.templates[id(node)]
        if source.shape[0] < template.shape[0] or source.shape[1] < template.shape[1]:
            raise ValueError('検索範囲が条件画像より小さいです: ' + node.get('name', ''))
        response = cv2.matchTemplate(source, template, cv2.TM_CCOEFF_NORMED)
        th, tw = template.shape[:2]
        for exclusion in variant.get('exclude_regions') or []:
            x1, y1, x2, y2 = [int(v) for v in exclusion]
            left, right = max(0, x1 - offset[0] - tw + 1), min(response.shape[1], x2 - offset[0])
            top, bottom = max(0, y1 - offset[1] - th + 1), min(response.shape[0], y2 - offset[1])
            if left < right and top < bottom:
                response[top:bottom, left:right] = -2
        score = cv2.minMaxLoc(response)[1]
        return math.isfinite(score) and score >= float(variant.get('threshold', .8))


class SequenceMatcher:
    def __init__(self, condition):
        if not 1 <= len(condition.get('children', [])) <= 2:
            raise ValueError('順序条件は1〜2段階です。')
        self.matchers = [Matcher(stage) for stage in condition['children']]
        self.sequence_rule = {'within_seconds': number(condition.get('within_seconds', 30), .01, 3600),
                              'cooldown_seconds': number(condition.get('cooldown_seconds', 5), 0, 3600),
                              'stages': [{'stable_seconds': number(c.get('stable_seconds', 0), 0, 60)}
                                         for c in condition['children']]}
        self.assets = {path: sha for matcher in self.matchers for path, sha in matcher.assets.items()}
        self.key = digest([condition, self.assets])

    def match(self, frame):
        return [matcher.match(frame) for matcher in self.matchers]

    def verify_assets(self):
        for matcher in self.matchers: matcher.verify_assets()


def build_matcher(condition):
    return SequenceMatcher(condition) if condition.get('op') == 'sequence' else Matcher(condition)


def probe(path):
    before = signature(path)
    cap = cv2.VideoCapture(str(path))
    try:
        fps = float(cap.get(cv2.CAP_PROP_FPS))
        frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width, height = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if not cap.isOpened() or not math.isfinite(fps) or fps <= 0 or frames <= 0:
            raise ValueError('動画を読めません: ' + str(path))
        result = {'path': str(Path(path).resolve()), 'signature': before,
                  'fps': fps, 'frames': frames, 'duration': frames / fps,
                  'width': width, 'height': height}
        require_source(result)
        return result
    finally:
        cap.release()


def read_at(cap, source, seconds):
    index = max(0, min(source['frames'] - 1, int(seconds * source['fps'] + 1e-6)))
    next_index = int(round(cap.get(cv2.CAP_PROP_POS_FRAMES)))
    if next_index != index:
        cap.set(cv2.CAP_PROP_POS_FRAMES, index)
    ok, frame = cap.read()
    actual = int(round(cap.get(cv2.CAP_PROP_POS_FRAMES))) - 1
    if not ok or frame is None or actual != index:
        raise ValueError('動画のframe {}を正確に復号できません。'.format(index))
    return frame, index / source['fps']


class EventCollector:
    """Debounce both edges; retain the first supporting sample's time."""
    def __init__(self, rule, source):
        self.rule, self.source = rule, source
        self.clips, self.state, self.candidate = [], None, None
        self.count, self.since, self.active_start = 0, 0.0, None

    def emit(self, start, end, edge):
        self.clips.append(make_clip(canonical(self.source['path']), self.rule,
                                    start, end, edge, self.source['signature']))

    def feed(self, when, matched):
        if matched != self.candidate:
            self.candidate, self.count, self.since = matched, 1, when
        else:
            self.count += 1
        if self.count < self.rule['stable_samples'] or matched == self.state:
            return
        previous, self.state = self.state, matched
        event = self.rule['event']
        if event in ('match', 'nonmatch'):
            desired = event == 'match'
            if matched == desired:
                self.active_start = self.since
            elif self.active_start is not None:
                self.emit(self.active_start, self.since, event)
                self.active_start = None
        elif ((matched and event in ('enter', 'both')) or
              (not matched and previous is not None and event in ('exit', 'both'))):
            self.emit(self.since, self.since, 'enter' if matched else 'exit')

    def finish(self):
        if self.active_start is not None:
            self.emit(self.active_start, self.source['duration'], self.rule['event'])
            self.active_start = None


def scan_video(path, rule, cancel, progress=None):
    rule = copy.deepcopy(rule)
    interval = number(rule['interval'], 0, 3600, '解析間隔')
    rule['stable_samples'] = int(number(rule['stable_samples'], 1, 120, '連続確認数'))
    if rule['event'] not in ('enter', 'exit', 'both', 'match', 'nonmatch'):
        raise ValueError('切り抜き方法が不正です。')
    matcher = build_matcher(rule['condition'])
    source = probe(path)
    step = max(1, int(round(interval * source['fps'])))
    collector = EventCollector(rule, source)
    sequence = None
    if isinstance(matcher, SequenceMatcher):
        if rule['event'] != 'enter':
            raise ValueError('順序条件の抽出方法は「成立の前後」を選択してください。')
        import sys
        if str(SERIAL_ROOT) not in sys.path: sys.path.insert(0, str(SERIAL_ROOT))
        from EventClips import EventSequence
        sequence = EventSequence(matcher.sequence_rule)
    report = {'path': str(path), 'rule_id': rule['id'], 'rule': rule,
              'predicate_key': matcher.key, 'assets': matcher.assets,
              'source_signature': source['signature'], 'sample_stride_frames': step,
              'all_frames': step == 1, 'samples': 0, 'status': 'running',
              'started': time.time()}
    cap = cv2.VideoCapture(str(path))
    try:
        for index in range(0, source['frames'], step):
            if cancel.is_set():
                report['status'] = 'cancelled'
                break
            frame, when = read_at(cap, source, index / source['fps'])
            matched = matcher.match(frame)
            if sequence is None:
                collector.feed(when, matched)
            else:
                event = sequence.update(when, matched)
                if event is not None:
                    collector.emit(event['confirmed_seconds'], event['confirmed_seconds'], 'sequence')
            report['samples'] += 1
            if progress and (report['samples'] % 10 == 0 or index == 0):
                progress(when / source['duration'], '{} / {:.1f}秒'.format(Path(path).name, when))
            if len(collector.clips) > 100000:
                raise ValueError('1動画の候補が10万件を超えました。条件を絞ってください。')
        else:
            collector.finish()
            matcher.verify_assets()
            require_source(source)
            report['status'] = 'complete'
    except Exception as error:
        report.update(status='failed', error=str(error))
    finally:
        cap.release()
    report['ended'] = time.time()
    report['partial_candidates'] = len(collector.clips) if report['status'] != 'complete' else 0
    return source, collector.clips, report
