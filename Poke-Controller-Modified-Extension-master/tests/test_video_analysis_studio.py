"""File-based integration tests: no camera, controller, OAuth or network I/O."""
import ast
import copy
import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

import cv2
import numpy as np

from VideoAnalysisStudio import detection, media, model
from VideoAnalysisStudio.player import Decoder, PlaybackClock


def make_video(root, name='sample.avi', colored=True):
    root = Path(root); root.mkdir(parents=True, exist_ok=True)
    path = root / name
    template = np.random.default_rng(19).integers(0, 256, (18, 24, 3), dtype=np.uint8)
    cv2.imwrite(str(root / 'marker.png'), template)
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*'MJPG'), 10, (160, 90))
    if not writer.isOpened(): raise RuntimeError('Fixture encoder unavailable')
    for index in range(80):
        frame = np.zeros((90, 160, 3), np.uint8)
        frame[:] = (20, 45, 75) if colored else (100, 20, 30)
        if 20 <= index < 40 or 60 <= index < 70:
            frame[30:48, 50:74] = template
        writer.write(frame)
    writer.release()
    return path, root / 'marker.png'


def fixture_project(path):
    source = detection.probe(path)
    project = model.new_project(); key = model.canonical(path)
    project['sources'][key] = source
    rule = {'id': 'fixture', 'name': 'marker'}
    project['clips'] = [model.make_clip(key, rule, 2, 2, 'enter', source['signature']),
                        model.make_clip(key, rule, 6, 6, 'enter', source['signature'])]
    project.update(before=.5, after=.5)
    return project


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path, self.template = make_video(self.root)
        self.project = fixture_project(self.path)

    def test_recursive_overlapping_roots_and_owned_output_exclusion(self):
        nested = self.root / 'sub'; nested.mkdir(); (nested / 'x.MP4').write_bytes(b'x')
        owned = self.root / '.video_analysis'; owned.mkdir(); (owned / 'copy.mp4').write_bytes(b'x')
        found, errors = model.discover([self.root, nested], [owned])
        self.assertEqual(len(found), 2); self.assertFalse(errors)

    def test_missing_folder_is_reported(self):
        found, errors = model.discover([self.root / 'missing'])
        self.assertEqual(found, []); self.assertEqual(len(errors), 1)

    def test_margins_restore_without_modifying_events_or_source(self):
        clip = self.project['clips'][0]
        clip['start'] = clip['end'] = 15
        self.project['sources'][clip['source']]['duration'] = 50
        before_clip = copy.deepcopy(clip); before_file = self.path.read_bytes()
        self.project.update(before=10, after=10)
        self.assertEqual(model.clip_bounds(self.project, clip), (5, 25))
        self.project.update(before=4, after=4)
        self.assertEqual(model.clip_bounds(self.project, clip), (11, 19))
        self.project.update(before=10, after=10)
        self.assertEqual(model.clip_bounds(self.project, clip), (5, 25))
        self.assertEqual(clip, before_clip); self.assertEqual(self.path.read_bytes(), before_file)

    def test_bounds_clamp_to_video_and_keep_a_real_frame(self):
        self.project.update(before=0, after=0)
        start, end = model.clip_bounds(self.project, self.project['clips'][0])
        self.assertAlmostEqual(end - start, .1)

    def test_individual_override(self):
        self.project['clips'][0].update(before=1, after=2)
        self.assertEqual(model.clip_bounds(self.project, self.project['clips'][0]), (1, 4))
        self.assertEqual(model.clip_bounds(self.project, self.project['clips'][1]), (5.5, 6.5))

    def test_review_is_bound_to_the_actual_visible_interval(self):
        clip = self.project['clips'][0]
        clip.update(reviewed=True, reviewed_view=list(model.clip_bounds(self.project, clip)))
        self.assertTrue(model.is_reviewed(self.project, clip))
        self.project['before'] = 2
        self.assertFalse(model.is_reviewed(self.project, clip))
        self.project['before'] = .5
        self.assertTrue(model.is_reviewed(self.project, clip))

    def test_project_roundtrip_and_changed_source_rejection(self):
        path = self.root / 'review.json'; model.atomic_json(path, self.project)
        self.assertEqual(model.load_project(path), self.project)
        self.path.touch()
        with self.assertRaises(ValueError): media.playlist(self.project, self.project['clips'])

    def test_nan_and_negative_margins_rejected(self):
        for value in (-1, float('inf'), float('nan')):
            with self.assertRaises(ValueError): model.number(value)

    def test_failed_scan_does_not_erase_previous_candidates(self):
        source = self.project['sources'][model.canonical(self.path)]
        old = copy.deepcopy(self.project['clips'])
        model.apply_scan(self.project, source, {'id': 'fixture'}, [], {'status': 'failed'})
        self.assertEqual(self.project['clips'], old)

    def test_rescan_preserves_individual_review_fields_by_identity(self):
        source = self.project['sources'][model.canonical(self.path)]
        old = copy.deepcopy(self.project['clips'])
        self.project['clips'][0].update(before=2, reviewed=True)
        model.apply_scan(self.project, source, {'id': 'fixture'}, old, {'status': 'complete'})
        self.assertEqual(self.project['clips'][0]['before'], 2)
        self.assertTrue(self.project['clips'][0]['reviewed'])

    def test_stale_unique_view_is_rejected_and_restored(self):
        ids = [c['id'] for c in self.project['clips']]
        self.project['groups'] = [{'representative': ids[0], 'members': [{'id': i, 'score': 1} for i in ids]}]
        self.project['group_key'] = model.view_key(self.project)
        self.assertEqual(len(model.ordered_clips(self.project, unique=True)), 1)
        self.project['before'] = 1
        with self.assertRaises(ValueError): model.ordered_clips(self.project, unique=True)
        self.project['before'] = .5
        self.assertEqual(len(model.ordered_clips(self.project, unique=True)), 1)


class DetectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path, template = make_video(self.root)
        self.rule = detection.new_rule()
        self.rule.update(interval=.1, stable_samples=2)
        self.rule['condition']['children'] = [detection.image_node({'template_path': str(template),
            'threshold': .85, 'use_gray': True, 'crop': [45, 25, 80, 55]}, 'marker')]

    def test_actual_video_scans_enter_exit_times(self):
        source, clips, report = detection.scan_video(self.path, self.rule, threading.Event())
        self.assertEqual(report['status'], 'complete'); self.assertTrue(report['all_frames'])
        self.assertEqual(report['samples'], 80)
        self.assertEqual([(c['edge'], c['start']) for c in clips], [('enter', 2), ('exit', 4), ('enter', 6), ('exit', 7)])

    def test_match_and_nonmatch_intervals(self):
        for kind, expected in [('match', [(2, 4), (6, 7)]), ('nonmatch', [(0, 2), (4, 6), (7, 8)])]:
            self.rule['event'] = kind
            _, clips, report = detection.scan_video(self.path, self.rule, threading.Event())
            self.assertEqual(report['status'], 'complete')
            self.assertEqual([(c['start'], c['end']) for c in clips], expected)

    def test_cancel_is_partial_not_complete(self):
        cancel = threading.Event()
        def progress(*_): cancel.set()
        _, _, report = detection.scan_video(self.path, self.rule, cancel, progress)
        self.assertEqual(report['status'], 'cancelled')

    def test_template_change_during_scan_invalidates_result(self):
        template = Path(self.rule['condition']['children'][0]['variant']['template_path'])
        changed = []
        def progress(*_):
            if not changed:
                template.write_bytes(template.read_bytes() + b'x'); changed.append(True)
        _, _, report = detection.scan_video(self.path, self.rule, threading.Event(), progress)
        self.assertEqual(report['status'], 'failed'); self.assertIn('変更', report['error'])

    def test_corrupt_decoder_is_not_silently_skipped(self):
        with mock.patch.object(detection, 'read_at', side_effect=ValueError('bad frame')):
            _, _, report = detection.scan_video(self.path, self.rule, threading.Event())
        self.assertEqual(report['status'], 'failed')

    def test_not_and_or_same_frame(self):
        matcher = detection.Matcher(self.rule['condition'])
        cap = cv2.VideoCapture(str(self.path)); source = detection.probe(self.path)
        try: positive, _ = detection.read_at(cap, source, 2.5)
        finally: cap.release()
        self.assertTrue(matcher.match(positive))
        inverted = {'op': 'not', 'children': [copy.deepcopy(self.rule['condition'])]}
        self.assertFalse(detection.Matcher(inverted).match(positive))

    def test_exclusion_and_template_crop(self):
        node = self.rule['condition']['children'][0]
        node['variant']['template_crop'] = [2, 2, 20, 16]
        cap = cv2.VideoCapture(str(self.path)); source = detection.probe(self.path)
        try: frame, _ = detection.read_at(cap, source, 2.5)
        finally: cap.release()
        self.assertTrue(detection.Matcher(node).match(frame))
        node['variant']['exclude_regions'] = [[45, 25, 80, 55]]
        self.assertFalse(detection.Matcher(node).match(frame))

    def test_blank_template_fails_instead_of_matching_everything(self):
        cv2.imwrite(str(self.root / 'blank.png'), np.zeros((10, 10, 3), np.uint8))
        self.rule['condition']['children'][0]['variant']['template_path'] = str(self.root / 'blank.png')
        with self.assertRaises(ValueError): detection.Matcher(self.rule['condition'])

    def test_safe_source_import_does_not_execute_code(self):
        source = self.root / 'unsafe.py'
        source.write_text("raise RuntimeError('do not execute')\nclass X:\n IMAGE_DETECTION_TARGETS = {'a': [{'template_path': 'x.png'}]}\n IMAGE_DETECTION_OPERATORS = {'a': 'AND'}\n", encoding='utf-8')
        result = detection.source_targets(source)
        self.assertEqual(result['a']['op'], 'all')

    def test_import_pokecon_rule_preserves_then_stability_and_margins(self):
        import configparser
        config = configparser.ConfigParser(interpolation=None)
        variant = self.rule['condition']['children'][0]['variant']
        target = {'name': 'marker', 'operator': 'OR', 'variants': [variant]}
        saved = {'stages': [{'operator': 'AND', 'stable_seconds': .2, 'targets': [target]},
                            {'operator': 'OR', 'stable_seconds': .1, 'targets': [target]}],
                 'within_seconds': 2, 'cooldown_seconds': 1,
                 'pre_seconds': 10, 'post_seconds': 4, 'interval_seconds': .1}
        config['Recording'] = {'event_clip_rule': json.dumps(saved)}
        path = self.root / 'settings.ini'
        with path.open('w', encoding='utf-8') as stream: config.write(stream)
        before = path.read_bytes()
        rule = detection.import_pokecon_rule(path)
        self.assertEqual(rule['condition']['op'], 'sequence')
        self.assertEqual((rule['suggested_before'], rule['suggested_after']), (10, 4))
        _, clips, report = detection.scan_video(self.path, rule, threading.Event())
        self.assertEqual(report['status'], 'complete')
        self.assertEqual([c['start'] for c in clips], [2.4, 6.4])
        self.assertEqual(path.read_bytes(), before)

    def test_sequence_does_not_ignore_an_incompatible_event_mode(self):
        self.rule['condition'] = {'op': 'sequence', 'children': [self.rule['condition']]}
        with self.assertRaises(ValueError): detection.scan_video(self.path, self.rule, threading.Event())

    def test_pokecon_template_hash_is_checked(self):
        node = self.rule['condition']['children'][0]
        node['variant']['sha256'] = '0' * 64
        with self.assertRaises(ValueError): detection.Matcher(node)


class SimilarityAndPlaybackTests(unittest.TestCase):
    def test_grouping_avoids_transitive_chain(self):
        items = [{'id': i} for i in 'abc']
        def score(a, b): return {('b', 'a'): .95, ('c', 'a'): .5, ('c', 'b'): .95}[(a['id'], b['id'])]
        with mock.patch.object(media, 'similarity', side_effect=score):
            groups = media.group_descriptors(items, .9, threading.Event())
        self.assertEqual(sorted(len(g['members']) for g in groups), [1, 2])

    def test_speed_changes_anchor_to_last_displayed_frame(self):
        wall = [100.0]; clock = PlaybackClock(lambda: wall[0])
        clock.seek(10); wall[0] += 8
        self.assertEqual(clock.target(), 10)
        clock.shown(10); clock.set_speed(2); wall[0] += 1
        self.assertEqual(clock.target(), 12)
        clock.shown(11.8); clock.set_speed(10); wall[0] += .2
        self.assertAlmostEqual(clock.target(), 13.8)

    def test_split_across_boundaries_preserves_total_and_order(self):
        items = [{'start': 3, 'end': 10, 'id': 'a'}, {'start': 20, 'end': 27, 'id': 'b'}]
        groups = media.split_plan(items, True, 5)
        self.assertEqual([sum(p['end'] - p['start'] for p in g) for g in groups], [5, 5, 4])
        self.assertEqual([(p['id'], p['start'], p['end']) for g in groups for p in g],
                         [('a', 3, 8), ('a', 8, 10), ('b', 20, 23), ('b', 23, 27)])

    def test_unmerged_split_resets_at_each_source(self):
        groups = media.split_plan([{'start': 0, 'end': 7}, {'start': 0, 'end': 7}], False, 5)
        self.assertEqual([sum(p['end'] - p['start'] for p in g) for g in groups], [5, 2, 5, 2])

    def test_decoder_reads_real_video_and_reports_missing_source(self):
        with tempfile.TemporaryDirectory() as root:
            path, _ = make_video(root); source = detection.probe(path)
            decoder = Decoder()
            try:
                decoder.request(7, source, 2.2, (320, 180))
                token, when, frame, error = decoder.results.get(timeout=10)
                self.assertEqual(token, 7); self.assertAlmostEqual(when, 2.2)
                self.assertIsNone(error); self.assertEqual(frame.shape, (180, 320, 3))
                path.touch(); decoder.request(8, source, 2.2, (320, 180))
                self.assertIsNotNone(decoder.results.get(timeout=10)[3])
            finally:
                decoder.close(); decoder.thread.join(timeout=5)


class MediaIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cv2.setNumThreads(1)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path, _ = make_video(self.root)
        self.project = fixture_project(self.path)
        self.cancel = threading.Event()

    def test_real_similarity_duplicate_keeps_all_members(self):
        groups, key = media.group_clips(self.project, self.project['clips'], .9, self.cancel)
        self.assertEqual(len(groups), 1)
        self.assertEqual(len(groups[0]['members']), 2)
        self.assertEqual(key, model.view_key(self.project))

    def test_export_merge_split_and_audio_keep_source(self):
        executable = media.ffmpeg_path()
        voiced = self.root / 'with_audio.mp4'
        media.run_process([executable, '-y', '-i', str(self.path), '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000',
                           '-t', '8', '-c:v', 'libx264', '-threads', '2', '-c:a', 'aac', str(voiced)], self.cancel)
        project = fixture_project(voiced)
        before = model.signature(voiced)
        result = media.export_plan(media.playlist(project, project['clips']), self.root / 'exports', True, 1.5, self.cancel)
        self.assertEqual(result['status'], 'complete'); self.assertEqual(len(result['outputs']), 2)
        self.assertEqual([round(detection.probe(p)['duration'], 1) for p in result['outputs']], [1.5, .5])
        self.assertTrue(all(media.has_audio(p) for p in result['outputs']))
        self.assertEqual(model.signature(voiced), before)
        # Full decode both streams, not just container headers.
        for path in result['outputs']:
            media.run_process([executable, '-v', 'error', '-i', path, '-f', 'null', '-'], self.cancel)

    def test_library_survives_source_move_and_deduplicates(self):
        library = media.Library(self.root / 'collection')
        first = library.add(self.project, self.project['clips'][:1], self.cancel)
        second = library.add(self.project, self.project['clips'][:1], self.cancel)
        self.assertEqual(first, second); self.assertEqual(len(library.entries()), 1)
        self.path.rename(self.root / 'relocated.avi')
        self.assertGreater(detection.probe(first[0]['path'])['frames'], 0)

    def test_cancelled_export_never_replaces_source(self):
        self.cancel.set(); before = model.signature(self.path)
        with self.assertRaises(media.Cancelled):
            media.export_plan(media.playlist(self.project, self.project['clips']), self.root / 'exports', True, 0, self.cancel)
        self.assertEqual(model.signature(self.path), before)
        reports = list((self.root / 'exports').glob('*/manifest.json'))
        self.assertEqual(json.loads(reports[0].read_text(encoding='utf-8'))['status'], 'cancelled')

    def test_queue_reuses_pokecon_channel_and_forbids_source_cleanup(self):
        with mock.patch.object(media.youtube, 'load_channel_store', return_value={
                'default_profile': 'test', 'profiles': {'test': {'channel_id': 'channel-test'}}}), \
                mock.patch.object(media.youtube, 'launch_upload_worker') as launch:
            jobs = media.queue_uploads([self.path], self.root / 'settings.ini', 'test', 600,
                                       self.root / 'sessions', self.cancel)
        self.assertEqual(len(jobs), 1); self.assertTrue(launch.called)
        job = json.loads(Path(jobs[0]).read_text(encoding='utf-8'))
        self.assertFalse(job['delete_local_after_processing'])
        self.assertEqual(job['privacy_status'], 'unlisted')
        self.assertEqual(job['channel_id_resolved'], 'channel-test')
        self.assertNotEqual(Path(job['session_dir']), self.path.parent)

    def test_missing_channel_does_not_enqueue(self):
        with mock.patch.object(media.youtube, 'load_channel_store', return_value={'profiles': {}}), \
                mock.patch.object(media.youtube, 'enqueue_upload_job') as enqueue:
            with self.assertRaises(ValueError):
                media.queue_uploads([self.path], self.root / 'settings.ini', '', 600, self.root / 'sessions', self.cancel)
        enqueue.assert_not_called()


if __name__ == '__main__':
    unittest.main()
