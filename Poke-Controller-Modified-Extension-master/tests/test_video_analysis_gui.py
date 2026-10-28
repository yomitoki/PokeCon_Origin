"""Real Tk widgets and real file decoders, isolated from PokeCon and its settings."""
import ast
import copy
import os
import tempfile
import threading
import time
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from VideoAnalysisStudio import detection, model, media
from VideoAnalysisStudio.app import Studio
from tests.test_video_analysis_studio import make_video, fixture_project


class StudioGuiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        path, template = make_video(self.directory / 'videos')
        self.project_path = self.directory / 'test.project.json'
        project = fixture_project(path)
        rule = detection.new_rule()
        rule.update(name='fixture', interval=.1, stable_samples=2)
        rule['condition']['children'] = [detection.image_node({'template_path': str(template),
                'threshold': .85, 'crop': [45, 25, 80, 55], 'use_gray': True}, 'marker')]
        project['rules'] = [rule]; project['roots'] = [str(path.parent)]
        project['library_dir'] = str(self.directory / 'library')
        model.atomic_json(self.project_path, project)
        self.errors = []
        self.error_patch = mock.patch('VideoAnalysisStudio.app.messagebox.showerror',
                                      side_effect=lambda *a, **k: self.errors.append(a))
        self.error_patch.start(); self.addCleanup(self.error_patch.stop)
        self.root = tk.Tk(); self.root.withdraw()
        self.app = Studio(self.root, self.project_path, self.directory / 'settings.ini')
        self.root.update()
        self.addCleanup(self.close)

    def close(self):
        self.app.shutdown()
        self.app.decoder.thread.join(3)

    def pump(self, condition, timeout=10):
        until = time.monotonic() + timeout
        while not condition() and time.monotonic() < until:
            self.root.update(); time.sleep(.01)
        self.assertTrue(condition(), self.app.status.get())

    def test_gui_scan_and_similarity_produce_playable_members(self):
        self.app.project['clips'] = []
        self.app.scan(); self.pump(lambda: not self.app.busy)
        self.assertFalse(self.errors)
        self.assertEqual(len(self.app.project['clips']), 4)
        self.app.analyse_similarity(); self.pump(lambda: not self.app.busy)
        self.assertEqual(sum(len(g['members']) for g in self.app.project['groups']), 4)
        group = next(g for g in self.app.project['groups'] if len(g['members']) > 1)
        self.app.unique.set(True); self.app.refresh()
        self.app.clip_tree.selection_set(group['representative'])
        self.app.play('group')
        self.assertEqual(len(self.app.play_items), len(group['members']))
        self.pump(lambda: self.app.last_frame is not None)
        self.app.clock.set_speed(10)
        self.pump(lambda: not self.app.playing)

    def test_margin_undo_and_redo_are_immediate_and_non_destructive(self):
        old = copy.deepcopy(self.app.project['clips'])
        self.app.set_margins(10); self.app.set_margins(4)
        self.app.undo_margins(); self.assertEqual(self.app.project['before'], 10)
        self.app.undo_margins(True); self.assertEqual(self.app.project['before'], 4)
        self.assertEqual(self.app.project['clips'], old)

    def test_scan_reuses_unchanged_evidence_and_can_force_a_rescan(self):
        self.app.scan(); self.pump(lambda: not self.app.busy)
        count = len(self.app.project['scans'])
        with mock.patch.object(detection, 'scan_video', side_effect=AssertionError('unneeded rescan')):
            self.app.scan(); self.pump(lambda: not self.app.busy)
        self.assertFalse(self.errors)
        self.assertEqual(len(self.app.project['scans']), count)
        self.app.force_scan.set(True)
        self.app.scan(); self.pump(lambda: not self.app.busy)
        self.assertEqual(len(self.app.project['scans']), count + 1)

    def test_margin_change_replaces_the_active_playlist_bounds(self):
        clip = self.app.project['clips'][0]
        self.app.start_playlist(media.playlist(self.app.project, [clip]), False)
        self.app.set_margins(4)
        self.assertEqual(self.app.play_items[0]['start'], 0)
        self.assertEqual(self.app.play_items[0]['end'], 6)
        self.app.set_margins(10)
        self.assertEqual(self.app.play_items[0]['end'], 8)

    def test_unapplied_image_edit_survives_selection_switch_and_save(self):
        self.app.rule_tree.selection_set('node_1'); self.app.select_condition()
        self.app.node_threshold.set('0.96')
        self.app.rule_tree.selection_set('node_0'); self.app.select_condition()
        self.assertTrue(self.app.save())
        persisted = model.load_project(self.project_path)
        draft = persisted['rule_drafts'][self.app.selected_rule()['id']]
        self.assertEqual(draft['rule']['condition']['children'][0]['_raw_form']['threshold'], '0.96')
        self.app._replace_project(persisted, self.project_path, model.signature(self.project_path))
        self.app.rule_tree.selection_set('node_1'); self.app.select_condition()
        self.assertEqual(self.app.node_threshold.get(), '0.96')
        self.assertTrue(self.app.apply_rule())
        self.assertEqual(self.app.selected_rule()['condition']['children'][0]['variant']['threshold'], .96)

    def test_invalid_draft_can_be_saved_but_not_used_for_scan(self):
        self.app.rule_tree.selection_set('node_1'); self.app.select_condition()
        self.app.node_crop.set('invalid')
        self.assertTrue(self.app.save())
        self.assertFalse(self.app.apply_rule())
        self.assertTrue(self.errors)
        self.assertEqual(self.app.selected_rule()['condition']['children'][0]['variant']['crop'], [45, 25, 80, 55])

    def test_external_project_change_is_not_overwritten(self):
        external = model.load_project(self.project_path); external['before'] = 99
        model.atomic_json(self.project_path, external)
        self.assertFalse(self.app.save())
        self.assertEqual(model.load_project(self.project_path)['before'], 99)

    def test_speed_and_upload_preferences_persist(self):
        self.app.speed.set('10'); self.app.split_minutes.set('45'); self.app.merge.set(False)
        self.assertTrue(self.app.save())
        preferences = model.load_project(self.project_path)['preferences']
        self.assertEqual(preferences['speed'], '10')
        self.assertEqual(preferences['split_minutes'], '45')
        self.assertFalse(preferences['merge'])

    def test_stale_decoder_result_is_not_displayed(self):
        self.app.token = 10
        self.app.decoder.results.put((9, 1, None, 'stale decode error'))
        self.app.tick()
        self.assertNotEqual(self.app.status.get(), 'stale decode error')

    def test_separate_preserves_all_candidates(self):
        self.app.analyse_similarity(); self.pump(lambda: not self.app.busy)
        self.assertEqual(len(self.app.project['groups']), 1)
        selected = self.app.project['clips'][1]['id']
        self.app.clip_tree.selection_set(selected)
        self.app.separate()
        self.assertEqual(len(self.app.project['groups']), 2)
        self.assertEqual(len(model.current_clips(self.app.project)), 2)

    def test_changing_representative_recomputes_scores(self):
        self.app.analyse_similarity(); self.pump(lambda: not self.app.busy)
        selected = self.app.project['clips'][1]['id']
        self.app.clip_tree.selection_set(selected)
        self.app.make_representative(); self.pump(lambda: not self.app.busy)
        group = self.app.project['groups'][0]
        self.assertEqual(group['representative'], selected)
        self.assertEqual(next(m['score'] for m in group['members'] if m['id'] == selected), 1)


class LauncherTests(unittest.TestCase):
    def test_pokecon_launch_is_detached_and_does_not_import_the_gui(self):
        path = Path(__file__).resolve().parents[1] / 'SerialController/Window.py'
        tree = ast.parse(path.read_text(encoding='utf-8-sig'))
        method = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == 'open_video_analysis_studio')
        module = ast.Module(body=[method], type_ignores=[])
        process = SimpleNamespace(Popen=mock.Mock())
        namespace = {'os': os, '__file__': str(path), 'sys': SimpleNamespace(executable='python.exe'),
                     'subprocess': process, 'platform': SimpleNamespace(system=lambda: 'Windows'),
                     'Settings': SimpleNamespace(GuiSettings=SimpleNamespace(SETTING_PATH='profile/settings.ini')),
                     'tkmsg': SimpleNamespace(showerror=mock.Mock())}
        exec(compile(ast.fix_missing_locations(module), str(path), 'exec'), namespace)
        namespace['open_video_analysis_studio'](SimpleNamespace(show_output=mock.Mock()))
        args, options = process.Popen.call_args
        self.assertIn('VideoAnalysisStudio.pyw', args[0][1])
        self.assertIn('--settings', args[0]); self.assertTrue(options['creationflags'] & 0x4000)


if __name__ == '__main__':
    unittest.main()
