"""Standalone Japanese Tk interface. No Window/Camera/Commands imports."""
import argparse
import copy
import json
import os
import queue
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from PIL import Image, ImageTk

from . import detection, media, model
from .player import Decoder, PlaybackClock

EVENTS = {'成立・解除の前後': 'both', '成立の前後': 'enter', '解除の前後': 'exit',
          '一致区間全体': 'match', '不一致区間全体': 'nonmatch'}
OPS = {'all': 'すべて一致 (AND)', 'any': 'どれか一致 (OR)', 'not': '除外 (NOT)',
       'atleast': '指定数以上', 'image': '画像', 'sequence': '順番に成立 (THEN)'}
PAGE_SIZE = 400


def button(parent, text, callback):
    widget = ttk.Button(parent, text=text, command=callback)
    widget.pack(side='left', padx=3, pady=3)
    return widget


def entry(parent, label, variable, width=8):
    ttk.Label(parent, text=label).pack(side='left', padx=(6, 2))
    widget = ttk.Entry(parent, textvariable=variable, width=width)
    widget.pack(side='left', padx=2)
    return widget


def tree_with_scroll(parent, columns, headings, height=10):
    frame = ttk.Frame(parent)
    frame.pack(fill='both', expand=True)
    tree = ttk.Treeview(frame, columns=columns, show='headings', selectmode='extended', height=height)
    for name, label in zip(columns, headings):
        tree.heading(name, text=label)
        tree.column(name, width=100, minwidth=55)
    scroll = ttk.Scrollbar(frame, orient='vertical', command=tree.yview)
    tree.configure(yscrollcommand=scroll.set)
    tree.pack(side='left', fill='both', expand=True)
    scroll.pack(side='right', fill='y')
    return tree


class Studio:
    def __init__(self, root, project_path=None, settings_path=None, folders=()):
        self.root = root
        self.data_root = Path(__file__).resolve().parents[1] / '.video_analysis'
        self.data_root.mkdir(exist_ok=True)
        self.project_path = Path(project_path) if project_path else self.data_root / 'project.json'
        self.loaded_signature = None
        self.settings_path = tk.StringVar(value=str(settings_path or
            detection.SERIAL_ROOT / 'profiles/default/settings.ini'))
        self.project = model.new_project()
        self.startup_error = ''
        if self.project_path.is_file():
            try:
                self.project = model.load_project(self.project_path)
                self.loaded_signature = model.signature(self.project_path)
            except Exception as error:
                self.startup_error = 'プロジェクトを読めません: ' + str(error)
                # Keep malformed user documents intact.
                self.project_path = self.data_root / ('recovery_' + str(time.time_ns()) + '.json')
        if not self.project['rules']:
            try:
                self.project['rules'] = [detection.default_rule()]
            except Exception as error:
                self.project['rules'] = [detection.new_rule()]
                self.startup_error = 'HARD CHECK条件を読めません。条件を追加してください: ' + str(error)
        for folder in folders:
            if str(Path(folder).resolve()) not in self.project['roots']:
                self.project['roots'].append(str(Path(folder).resolve()))
        self.project['library_dir'] = self.project['library_dir'] or str(self.data_root / 'library')
        preferences = self.project.get('preferences', {})
        if not settings_path and preferences.get('settings_path'):
            self.settings_path.set(preferences['settings_path'])
        self.messages = queue.Queue()
        self.cancel = threading.Event()
        self.busy, self.closing = False, False
        self.dirty, self.page = False, 0
        self.undo, self.redo = [], []
        self.margin_timer = None
        self.margin_suppressed = False
        self.form_loading = True
        self.form_node = None
        self.all_visible, self.rows, self.groups_by_clip = [], {}, {}
        self.decoder = Decoder()
        self.clock = PlaybackClock()
        self.play_items, self.play_index, self.token = [], 0, 0
        self.playing, self.pending = False, False
        self.last_requested, self.last_frame = None, None
        self.status = tk.StringVar(value=self.startup_error or 'フォルダを追加して条件を選び、「解析開始」を押してください。')
        self.progress = tk.DoubleVar(value=0)
        self.before = tk.StringVar(value=str(self.project['before']))
        self.after = tk.StringVar(value=str(self.project['after']))
        self.speed = tk.StringVar(value=preferences.get('speed', '2'))
        self.unique = tk.BooleanVar(value=False)
        self.force_scan = tk.BooleanVar(value=False)
        self.order = tk.StringVar(value='時刻順')
        self.threshold = tk.StringVar(value=preferences.get('threshold', '0.92'))
        self.rule_name = tk.StringVar()
        self.clip_label = tk.StringVar(value='候補を選択するとここに表示します。')
        self.page_label = tk.StringVar()
        self.library_path = tk.StringVar(value=self.project['library_dir'])
        self.output_path = tk.StringVar(value=preferences.get('output_path', str(self.data_root / 'exports')))
        self.upload_scope = tk.StringVar(value='指定フォルダの全動画')
        self.channel = tk.StringVar(value=preferences.get('channel', ''))
        self.merge = tk.BooleanVar(value=preferences.get('merge', True))
        self.split_minutes = tk.StringVar(value=preferences.get('split_minutes', '120'))
        self._build()
        self._refresh_roots()
        self._refresh_rules()
        self.refresh()
        self.refresh_library()
        self.refresh_channels()
        self.form_loading = False
        for variable in (self.edit_rule_name, self.event, self.interval, self.stability,
                         self.node_name, self.node_path, self.node_threshold,
                         self.node_crop, self.node_template_crop, self.node_gray,
                         self.node_stable, self.node_within, self.node_cooldown):
            variable.trace_add('write', self.capture_rule_draft)
        for variable in (self.speed, self.threshold, self.output_path, self.settings_path,
                         self.channel, self.merge, self.split_minutes, self.library_path):
            variable.trace_add('write', lambda *_: self.changed())
        self.before.trace_add('write', self._margins_changed)
        self.after.trace_add('write', self._margins_changed)
        self.root.protocol('WM_DELETE_WINDOW', self.close)
        self.root.after(30, self.poll)
        self.root.after(40, self.tick)
        self.root.bind('<Control-s>', lambda e: self.save())
        self.root.bind('<Control-z>', lambda e: self.undo_margins())
        self.root.bind('<Control-y>', lambda e: self.undo_margins(True))
        self._title()

    def _build(self):
        self.root.title('PokeCon Video Analysis Studio')
        self.root.geometry('1320x900')
        self.root.minsize(1000, 720)
        toolbar = ttk.Frame(self.root); toolbar.pack(fill='x', padx=8, pady=4)
        button(toolbar, 'プロジェクトを開く', self.open_project)
        button(toolbar, '保存', self.save)
        button(toolbar, '名前を付けて保存', lambda: self.save(True))
        button(toolbar, '新規プロジェクト', self.new_project)
        ttk.Label(toolbar, text='動画解析・切り抜きレビュー', font=('', 13, 'bold')).pack(side='right', padx=10)
        tabs = ttk.Notebook(self.root); tabs.pack(fill='both', expand=True, padx=8, pady=4)
        self.review_tab, self.rule_tab, self.library_tab, self.upload_tab = [ttk.Frame(tabs) for _ in range(4)]
        for page, title in zip((self.review_tab, self.rule_tab, self.library_tab, self.upload_tab),
                               ('解析・連続再生', '切り抜き条件', 'ユニーク蓄積', '書き出し・YouTube')):
            tabs.add(page, text=title)
        self._build_review()
        self._build_rules()
        self._build_library()
        self._build_upload()
        bottom = ttk.Frame(self.root); bottom.pack(fill='x', padx=8, pady=5)
        self.stop_job_button = button(bottom, '処理を中止', self.cancel.set)
        ttk.Progressbar(bottom, variable=self.progress, maximum=1, length=130).pack(side='left', padx=5)
        ttk.Label(bottom, textvariable=self.status, wraplength=930).pack(side='left', fill='x', expand=True)

    def _build_review(self):
        top = ttk.Frame(self.review_tab); top.pack(fill='x', padx=6, pady=4)
        folders = ttk.LabelFrame(top, text='対象フォルダ（複数・配下を再帰検索）'); folders.pack(side='left', fill='both', expand=True)
        self.folder_list = tk.Listbox(folders, height=3, exportselection=False)
        self.folder_list.pack(side='left', fill='both', expand=True, padx=4, pady=4)
        folder_buttons = ttk.Frame(folders); folder_buttons.pack(side='right')
        ttk.Button(folder_buttons, text='追加', command=self.add_folder).pack(padx=4, pady=3)
        ttk.Button(folder_buttons, text='除外', command=self.remove_folder).pack(padx=4, pady=3)
        controls = ttk.Frame(top); controls.pack(side='right', padx=8)
        self.rule_combo = ttk.Combobox(controls, textvariable=self.rule_name, width=37, state='readonly')
        self.rule_combo.pack(fill='x', pady=3)
        ttk.Button(controls, text='選択条件で解析開始', command=self.scan).pack(fill='x')
        ttk.Label(controls, text='間引きは短い表示を見落とす場合があります。').pack(pady=3)
        ttk.Checkbutton(controls, text='変更なしの動画も再解析', variable=self.force_scan).pack(anchor='w')
        panes = ttk.Panedwindow(self.review_tab, orient='horizontal'); panes.pack(fill='both', expand=True, padx=6)
        left, right = ttk.Frame(panes), ttk.Frame(panes)
        panes.add(left, weight=3); panes.add(right, weight=4)
        self.clip_tree = tree_with_scroll(left, ('group', 'rule', 'file', 'range', 'score', 'review'),
                                         ('類似', '条件', '元動画', '表示範囲（秒）', '一致度', '確認'), 15)
        for column, width in [('group', 50), ('rule', 120), ('file', 140), ('range', 135), ('score', 65), ('review', 50)]:
            self.clip_tree.column(column, width=width)
        self.clip_tree.bind('<<TreeviewSelect>>', self.select_clip)
        self.clip_tree.bind('<Double-1>', lambda e: self.play('selected'))
        pagination = ttk.Frame(left); pagination.pack(fill='x')
        button(pagination, '前のページ', lambda: self.change_page(-1))
        button(pagination, '次のページ', lambda: self.change_page(1))
        ttk.Label(pagination, textvariable=self.page_label).pack(side='right', padx=5)
        similar = ttk.Frame(left); similar.pack(fill='x')
        entry(similar, '類似閾値', self.threshold, 5)
        button(similar, '類似を解析', self.analyse_similarity)
        order = ttk.Combobox(similar, textvariable=self.order, values=['時刻順', '類似順'], width=8, state='readonly')
        order.pack(side='left', padx=3); order.bind('<<ComboboxSelected>>', lambda e: self.refresh())
        ttk.Checkbutton(similar, text='代表のみ', variable=self.unique, command=self.refresh).pack(side='left')
        actions = ttk.Frame(left); actions.pack(fill='x')
        button(actions, '選択を代表に', self.make_representative)
        button(actions, '別のユニーク候補に分ける', self.separate)
        button(actions, '確認済みにする', self.mark_reviewed)
        ttk.Label(left, text='類似判定は映像5点の候補分類です。代表のみでも全メンバーを再生できます。',
                  wraplength=580).pack(fill='x', pady=5)
        self.canvas = tk.Canvas(right, bg='#151922', highlightthickness=0, height=360)
        self.canvas.pack(fill='both', expand=True)
        ttk.Label(right, textvariable=self.clip_label, wraplength=610).pack(fill='x', pady=3)
        self.seek = ttk.Scale(right, from_=0, to=1, command=self.seek_to)
        self.seek.pack(fill='x', pady=3)
        self.seeking = False
        play_buttons = ttk.Frame(right); play_buttons.pack(fill='x')
        button(play_buttons, '選択を再生', lambda: self.play('selected'))
        button(play_buttons, '一覧を連続再生', lambda: self.play('visible'))
        button(play_buttons, '類似内を全再生', lambda: self.play('group'))
        button(play_buttons, '停止', self.stop_playback)
        speed_row = ttk.Frame(right); speed_row.pack(fill='x')
        ttk.Label(speed_row, text='速度').pack(side='left', padx=5)
        speed = ttk.Combobox(speed_row, textvariable=self.speed, values=[str(i) for i in range(1, 11)],
                             state='readonly', width=5)
        speed.pack(side='left'); speed.bind('<<ComboboxSelected>>', lambda e: self.clock.set_speed(self.speed.get()))
        ttk.Label(speed_row, text='倍  /  プレビューは無音・書き出しは元音声を保持').pack(side='left', padx=5)
        margins = ttk.LabelFrame(right, text='表示する前後の秒数（元動画は保持・再解析不要）')
        margins.pack(fill='x', pady=5)
        entry(margins, '前', self.before, 6); entry(margins, '後', self.after, 6)
        button(margins, '4秒', lambda: self.set_margins(4))
        button(margins, '10秒へ戻す', lambda: self.set_margins(10))
        fine = ttk.Frame(right); fine.pack(fill='x')
        button(fine, '選択だけ微調整', self.tune_selected)
        button(fine, '個別調整を解除', self.clear_overrides)
        button(fine, '元に戻す', self.undo_margins)
        button(fine, 'やり直す', lambda: self.undo_margins(True))

    def _build_rules(self):
        bar = ttk.Frame(self.rule_tab); bar.pack(fill='x', padx=6, pady=4)
        button(bar, '新しい条件', self.add_rule)
        button(bar, '選択条件を複製', self.duplicate_rule)
        button(bar, '条件を読込', self.import_rule)
        button(bar, '条件を書出', self.export_rule)
        button(bar, 'PokeConの切り抜き条件をコピー', self.import_recording_rule)
        button(bar, '条件を適用', self.apply_rule)
        button(bar, '選択フレームで照合', self.test_condition)
        row = ttk.Frame(self.rule_tab); row.pack(fill='x', padx=6)
        self.edit_rule_name = tk.StringVar(); self.event = tk.StringVar()
        self.interval = tk.StringVar(); self.stability = tk.StringVar()
        entry(row, '名前', self.edit_rule_name, 38)
        ttk.Combobox(row, textvariable=self.event, values=list(EVENTS), state='readonly', width=17).pack(side='left', padx=4)
        entry(row, '解析間隔 秒（0=全frame）', self.interval, 6)
        entry(row, '連続確認数', self.stability, 4)
        panes = ttk.Panedwindow(self.rule_tab, orient='horizontal'); panes.pack(fill='both', expand=True, padx=6, pady=6)
        left, right = ttk.Frame(panes), ttk.Frame(panes); panes.add(left, weight=2); panes.add(right, weight=3)
        self.rule_tree = ttk.Treeview(left, show='tree', selectmode='browse')
        self.rule_tree.pack(fill='both', expand=True)
        self.rule_tree.bind('<<TreeviewSelect>>', self.select_condition)
        for op in ('all', 'any', 'not'):
            ttk.Button(left, text=OPS[op] + 'を追加', command=lambda o=op: self.add_group(o)).pack(fill='x', pady=2)
        ttk.Button(left, text='画像ファイルを追加', command=self.add_image).pack(fill='x', pady=2)
        ttk.Button(left, text='選択条件を除く', command=self.remove_condition).pack(fill='x', pady=2)
        self.node_name, self.node_path, self.node_threshold = tk.StringVar(), tk.StringVar(), tk.StringVar()
        self.node_crop, self.node_template_crop = tk.StringVar(), tk.StringVar()
        self.node_gray = tk.BooleanVar()
        self.node_stable, self.node_within, self.node_cooldown = tk.StringVar(), tk.StringVar(), tk.StringVar()
        for label, var in [('条件名', self.node_name), ('画像ファイル', self.node_path), ('一致閾値 0〜1', self.node_threshold),
                           ('検索範囲 x1,y1,x2,y2（0,0,0,0=全体）', self.node_crop),
                           ('画像内の範囲 x1,y1,x2,y2', self.node_template_crop)]:
            ttk.Label(right, text=label).pack(anchor='w', padx=6, pady=(6, 0))
            ttk.Entry(right, textvariable=var).pack(fill='x', padx=6)
        ttk.Checkbutton(right, text='グレースケールで判定', variable=self.node_gray).pack(anchor='w', padx=6, pady=5)
        ttk.Button(right, text='この画像の変更を反映', command=self.update_node).pack(anchor='w', padx=6, pady=5)
        temporal = ttk.Frame(right); temporal.pack(fill='x', padx=6)
        entry(temporal, '段階の継続秒', self.node_stable, 5)
        entry(temporal, '①→②制限秒', self.node_within, 5)
        entry(temporal, '再検出間隔秒', self.node_cooldown, 5)
        ttk.Label(right, text='時間設定はPokeConからコピーした順序条件に適用します。').pack(anchor='w', padx=6)
        self.template_preview = ttk.Label(right); self.template_preview.pack(fill='x', padx=6, pady=6)
        ttk.Separator(right).pack(fill='x', pady=8)
        ttk.Label(right, text='PokeConの登録画像条件をコピー').pack(anchor='w', padx=6)
        catalog_row = ttk.Frame(right); catalog_row.pack(fill='x')
        button(catalog_row, 'Commandsソースから読込', self.load_catalog_source)
        button(catalog_row, '登録ライブラリから読込', self.load_catalog_library)
        self.catalog_choice = tk.StringVar()
        self.catalog_combo = ttk.Combobox(right, textvariable=self.catalog_choice, state='readonly')
        self.catalog_combo.pack(fill='x', padx=6, pady=3)
        ttk.Button(right, text='選択中のグループへ追加', command=self.add_catalog).pack(anchor='w', padx=6, pady=5)
        self.catalog = {}
        ttk.Label(right, text='条件はこの解析プロジェクト用のコピーです。\n画像ファイル・ROI・閾値・AND/OR/除外を編集できます。\n条件の変更は再解析後の結果へ反映されます。',
                  wraplength=550).pack(anchor='w', padx=6, pady=10)
        self.rule_combo.bind('<<ComboboxSelected>>', self.load_rule_form)

    def _build_library(self):
        row = ttk.Frame(self.library_tab); row.pack(fill='x', padx=6, pady=5)
        entry(row, '蓄積フォルダ', self.library_path, 75)
        button(row, '選択', self.choose_library)
        button(row, '更新', self.refresh_library)
        buttons = ttk.Frame(self.library_tab); buttons.pack(fill='x', padx=6)
        button(buttons, '解析の選択候補を蓄積', self.collect_selected)
        button(buttons, '蓄積の選択を連続再生', self.play_library)
        button(buttons, '蓄積内も類似を確認', self.compare_library)
        button(buttons, '解析候補と蓄積を比較', lambda: self.compare_library(True))
        self.library_tree = tree_with_scroll(self.library_tab, ('name', 'source', 'range', 'review', 'date'),
                                            ('条件', '出典', '元動画の秒数', '確認', '登録日時'))
        ttk.Label(self.library_tab, text='選んだクリップの動画・音声と出典を蓄積します。元動画を移動した後も再生できます。\n'
                  '同じ元動画・同じ表示範囲の二重登録は防止します。別録画の「本当にユニークか」は類似候補を再生して確認してください。',
                  wraplength=1150).pack(fill='x', padx=6, pady=8)
        self.library_entries = {}

    def _build_upload(self):
        page = self.upload_tab
        for label, var, callback in [('出力フォルダ', self.output_path, self.choose_output),
                                      ('PokeCon設定ファイル', self.settings_path, self.choose_settings)]:
            row = ttk.Frame(page); row.pack(fill='x', padx=8, pady=6)
            entry(row, label, var, 85); button(row, '選択', callback)
        row = ttk.Frame(page); row.pack(fill='x', padx=8, pady=6)
        ttk.Label(row, text='対象').pack(side='left', padx=5)
        ttk.Combobox(row, textvariable=self.upload_scope, values=['指定フォルダの全動画', '解析の一覧', '解析の選択'],
                     state='readonly', width=26).pack(side='left')
        ttk.Checkbutton(row, text='一覧の順序でマージ', variable=self.merge).pack(side='left', padx=10)
        entry(row, '分割（分） 0=分割なし', self.split_minutes, 8)
        row = ttk.Frame(page); row.pack(fill='x', padx=8, pady=6)
        ttk.Label(row, text='YouTubeチャンネル設定').pack(side='left', padx=5)
        self.channel_combo = ttk.Combobox(row, textvariable=self.channel, width=35, state='readonly')
        self.channel_combo.pack(side='left')
        button(row, '再読込', self.refresh_channels)
        button(row, 'チャンネルを認証・追加', self.authorize_channel)
        row = ttk.Frame(page); row.pack(fill='x', padx=8, pady=8)
        button(row, '対象を確認', self.inspect_export)
        button(row, 'MP4を書き出す', lambda: self.export(False))
        button(row, 'YouTubeへアップロード', lambda: self.export(True))
        button(row, 'キューを更新', self.refresh_queue)
        button(row, '共通キューを再開', self.resume_queue)
        ttk.Label(page, text='YouTubeはPokeConと同じ認証・再開可能キューを使い、限定公開で登録します。元動画は削除しません。\n'
                  'マージ／分割は元動画を保持して別ファイルを作成します。フォルダ全動画はパス順、解析結果は一覧の順序です。\n'
                  'プレビューと書き出しは等速の元時刻を共有します。再生の倍速設定は書き出し速度を変えません。',
                  wraplength=1150).pack(fill='x', padx=12, pady=10)
        self.upload_text = tk.Text(page, height=18, wrap='word', state='disabled')
        self.upload_text.pack(fill='both', expand=True, padx=10, pady=6)

    def guard(self):
        if self.busy:
            self.status.set('処理中です。完了または中止後に変更してください。')
            return False
        return True

    def error(self, error):
        self.status.set(str(error))
        messagebox.showerror('動画解析', str(error), parent=self.root)

    def _title(self):
        self.root.title('PokeCon Video Analysis Studio — {}{}'.format(self.project_path.name, ' *' if self.dirty else ''))

    def changed(self):
        self.dirty = True
        self._title()

    def save(self, save_as=False):
        self.flush_margins()
        self.capture_rule_draft()
        path = self.project_path
        if save_as:
            chosen = filedialog.asksaveasfilename(parent=self.root, defaultextension='.json',
                         initialfile=path.name, filetypes=[('解析プロジェクト', '*.json')])
            if not chosen:
                return False
            path = Path(chosen)
        try:
            if path == self.project_path and path.exists() and self.loaded_signature != model.signature(path):
                raise ValueError('別の画面でプロジェクトが変更されています。「名前を付けて保存」で別保存してください。')
            self.project['library_dir'] = self.library_path.get()
            self.project['preferences'] = {name: getattr(self, name).get() for name in
                ('speed', 'threshold', 'output_path', 'settings_path', 'channel', 'merge', 'split_minutes')}
            model.atomic_json(path, self.project)
            self.project_path, self.loaded_signature = path, model.signature(path)
            self.dirty = False
            self._title()
            return True
        except Exception as error:
            self.error(error)
            return False

    def open_project(self):
        if not self.guard() or (self.dirty and not self.save()):
            return
        path = filedialog.askopenfilename(parent=self.root, filetypes=[('解析プロジェクト', '*.json')])
        if not path:
            return
        try:
            project = model.load_project(path)
            self._replace_project(project, Path(path), model.signature(path))
        except Exception as error:
            self.error(error)

    def new_project(self):
        if not self.guard() or (self.dirty and not self.save()):
            return
        project = model.new_project()
        try:
            project['rules'] = [detection.default_rule()]
        except Exception:
            project['rules'] = [detection.new_rule()]
        project['library_dir'] = self.library_path.get()
        self._replace_project(project, self.data_root / ('project_' + str(time.time_ns()) + '.json'), None)
        self.changed()

    def _replace_project(self, project, path, sig):
        self.stop_playback()
        self.project, self.project_path, self.loaded_signature = project, path, sig
        self.undo, self.redo, self.page = [], [], 0
        self.margin_suppressed = True
        self.before.set(str(project['before'])); self.after.set(str(project['after']))
        self.margin_suppressed = False
        self.library_path.set(project['library_dir'] or str(self.data_root / 'library'))
        self.unique.set(False); self.order.set('時刻順')
        self._refresh_roots(); self._refresh_rules(); self.refresh(); self.refresh_library()
        self.dirty = False; self._title()

    def _refresh_roots(self):
        self.folder_list.delete(0, 'end')
        for folder in self.project['roots']:
            self.folder_list.insert('end', folder)

    def add_folder(self):
        if not self.guard(): return
        path = filedialog.askdirectory(parent=self.root)
        if path and model.canonical(path) not in {model.canonical(p) for p in self.project['roots']}:
            self.project['roots'].append(path); self._refresh_roots(); self.changed()

    def remove_folder(self):
        if not self.guard(): return
        for index in reversed(self.folder_list.curselection()):
            self.project['roots'].pop(index)
        self._refresh_roots(); self.changed()
        self.status.set('走査対象から除外しました。保存済みの解析結果は保持されています。')

    def _refresh_rules(self, index=0):
        self.rule_combo['values'] = [r['name'] for r in self.project['rules']]
        if self.project['rules']:
            self.rule_combo.current(min(index, len(self.project['rules']) - 1))
            self.load_rule_form()

    def selected_rule(self):
        index = max(0, self.rule_combo.current())
        return self.project['rules'][index]

    def job(self, name, work, complete):
        if not self.guard(): return
        self.busy = True; self.cancel.clear(); self.progress.set(0); self.status.set(name)
        self.complete_callback = complete
        last_progress = [0.0]
        def progress(fraction, text):
            now = time.monotonic()
            if now - last_progress[0] >= .1 or fraction >= 1:
                self.messages.put(('progress', (fraction, text)))
                last_progress[0] = now
        def run():
            try:
                value = work(progress)
                self.messages.put(('done', value))
            except Exception as error:
                self.messages.put(('error', error))
        threading.Thread(target=run, daemon=True, name='VideoAnalysisJob').start()

    def poll(self):
        if self.closing: return
        for _ in range(100):
            try:
                kind, value = self.messages.get_nowait()
            except queue.Empty:
                break
            if kind == 'progress':
                self.progress.set(value[0]); self.status.set(value[1])
            elif kind == 'scan_result':
                source, rule, clips, report = value
                model.apply_scan(self.project, source, rule, clips, report)
                self.changed()
            elif kind == 'done':
                self.busy = False
                try:
                    self.complete_callback(value)
                    self.save()
                except Exception as error:
                    self.error(error)
            elif kind == 'error':
                self.busy = False
                if isinstance(value, media.Cancelled):
                    self.status.set(str(value))
                else:
                    self.error(value)
                self.refresh()
                if self.dirty: self.save()
        self.root.after(50, self.poll)

    def excluded_paths(self):
        return [str(self.data_root), self.library_path.get(), self.output_path.get()]

    def scan(self):
        if not self.guard(): return
        if not self.project['roots']:
            self.status.set('解析するフォルダを追加してください。'); return
        if not self.apply_rule(): return
        rule = copy.deepcopy(self.selected_rule())
        roots, excluded = list(self.project['roots']), self.excluded_paths()
        cache = {(model.canonical(r['path']), r['rule_id']): copy.deepcopy(r)
                 for r in self.project['scans'] if r.get('status') == 'complete'}
        force_scan = self.force_scan.get()
        def work(progress):
            paths, errors = model.discover(roots, excluded, self.cancel)
            complete, failed, reused = 0, 0, 0
            matcher_key = detection.build_matcher(rule['condition']).key
            for index, path in enumerate(paths):
                if self.cancel.is_set(): break
                try:
                    previous = cache.get((model.canonical(path), rule['id']), {})
                    if (not force_scan and previous.get('rule') == rule
                            and previous.get('source_signature') == model.signature(path)
                            and previous.get('predicate_key') == matcher_key):
                        reused += 1; complete += 1
                        progress((index + 1) / len(paths), '解析済みを再利用: ' + Path(path).name)
                        continue
                    source, clips, report = detection.scan_video(path, rule, self.cancel,
                        lambda f, text: progress((index + f) / len(paths), text))
                    self.messages.put(('scan_result', (source, rule, clips, report)))
                    if report['status'] == 'complete': complete += 1
                    elif report['status'] == 'failed':
                        failed += 1; errors.append(path + ': ' + report.get('error', ''))
                except Exception as error:
                    failed += 1; errors.append(path + ': ' + str(error))
            return {'complete': complete, 'failed': failed, 'total': len(paths),
                    'cancelled': self.cancel.is_set(), 'errors': errors, 'reused': reused}
        def complete(result):
            self.unique.set(False); self.order.set('時刻順'); self.refresh()
            self.status.set('{}: 完了{}/{}本（再利用{}）、失敗{}本、候補{}件'.format(
                '中止・部分結果' if result['cancelled'] else '走査終了', result['complete'], result['total'],
                result['reused'], result['failed'], len(model.current_clips(self.project))))
            if result['errors']:
                self.set_upload_text('\n'.join(result['errors']))
                messagebox.showwarning('解析で読めなかった動画／フォルダ', '\n'.join(result['errors'][:12]), parent=self.root)
        self.job('動画を探しています…', work, complete)

    def refresh(self):
        selected = self.clip_tree.selection()
        try:
            clips = model.ordered_clips(self.project, 'similarity' if self.order.get() == '類似順' else 'time', self.unique.get())
        except ValueError as error:
            self.unique.set(False); self.order.set('時刻順')
            clips = model.ordered_clips(self.project)
            self.status.set(str(error))
        self.all_visible = clips
        valid_groups = self.project['group_key'] == model.view_key(self.project)
        self.groups_by_clip = {}
        if valid_groups:
            for index, group in enumerate(self.project['groups']):
                for member in group['members']:
                    self.groups_by_clip[member['id']] = (index + 1, group, member['score'])
        self.page = max(0, min(self.page, (len(clips) - 1) // PAGE_SIZE))
        self.clip_tree.delete(*self.clip_tree.get_children())
        self.rows = {}
        for clip in clips[self.page * PAGE_SIZE:(self.page + 1) * PAGE_SIZE]:
            start, end = model.clip_bounds(self.project, clip)
            group = self.groups_by_clip.get(clip['id'])
            self.rows[clip['id']] = clip
            self.clip_tree.insert('', 'end', iid=clip['id'], values=(
                '{} ({})'.format(group[0], len(group[1]['members'])) if group else '',
                clip['rule_name'], Path(self.project['sources'][clip['source']]['path']).name,
                '{:.2f}–{:.2f}'.format(start, end), '{:.1%}'.format(group[2]) if group else '',
                '済' if model.is_reviewed(self.project, clip) else '未'))
        self.page_label.set('{}件 / {}ページ目'.format(len(clips), self.page + 1))
        keep = [i for i in selected if i in self.rows]
        if keep: self.clip_tree.selection_set(keep)

    def change_page(self, offset):
        self.page += offset; self.refresh()

    def selected_clips(self):
        return [self.rows[i] for i in self.clip_tree.selection() if i in self.rows]

    def analyse_similarity(self):
        self.flush_margins()
        try:
            threshold = model.number(self.threshold.get(), .5, 1, '類似閾値')
            snapshot = copy.deepcopy(self.project)
            clips = model.ordered_clips(snapshot)
            if not clips: raise ValueError('先に動画を解析してください。')
        except Exception as error:
            self.error(error); return
        def complete(result):
            groups, key = result
            if key != model.view_key(self.project):
                self.status.set('表示範囲が変わったため類似結果を破棄しました。再実行してください。'); return
            self.project.update(groups=groups, group_key=key)
            self.order.set('類似順'); self.changed(); self.refresh()
            self.status.set('{}件を{}類似グループに分類。全候補を確認できます。'.format(len(clips), len(groups)))
        self.job('類似特徴を解析しています…',
                 lambda p: media.group_clips(snapshot, clips, threshold, self.cancel, p), complete)

    def make_representative(self):
        clips = self.selected_clips()
        if len(clips) != 1 or clips[0]['id'] not in self.groups_by_clip: return
        group = self.groups_by_clip[clips[0]['id']][1]
        chosen = clips[0]['id']
        ids = {m['id'] for m in group['members']}
        snapshot = copy.deepcopy(self.project)
        key = model.view_key(snapshot)
        members = [c for c in model.current_clips(snapshot) if c['id'] in ids]
        def work(progress):
            vectors = media.descriptors(snapshot, members, self.cancel, progress)
            representative = next(v for v in vectors if v['id'] == chosen)
            return sorted([{'id': v['id'], 'score': media.similarity(v, representative)} for v in vectors],
                          key=lambda v: -v['score'])
        def complete(values):
            if key != model.view_key(self.project):
                self.status.set('表示範囲が変わったため代表変更を取り消しました。'); return
            group.update(representative=chosen, members=values)
            self.changed(); self.refresh(); self.status.set('代表を変更し、一致度を再計算しました。')
        self.job('新しい代表と全メンバーを比較しています…', work, complete)

    def separate(self):
        clips = self.selected_clips()
        for clip in clips:
            info = self.groups_by_clip.get(clip['id'])
            if not info or len(info[1]['members']) <= 1: continue
            group = info[1]
            group['members'] = [m for m in group['members'] if m['id'] != clip['id']]
            if group['representative'] == clip['id']:
                group['representative'] = group['members'][0]['id']
            self.project['groups'].append({'representative': clip['id'], 'members': [{'id': clip['id'], 'score': 1.0}],
                                            'threshold': group['threshold'], 'reviewed': True})
        self.changed(); self.refresh()

    def mark_reviewed(self):
        for clip in self.selected_clips():
            clip['reviewed'] = True
            clip['reviewed_view'] = list(model.clip_bounds(self.project, clip))
        self.changed(); self.refresh()

    def margin_state(self):
        return {'before': self.project['before'], 'after': self.project['after'],
                'overrides': {c['id']: {k: c[k] for k in ('before', 'after') if k in c}
                              for c in self.project['clips'] if 'before' in c or 'after' in c}}

    def remember_margins(self):
        self.undo.append(self.margin_state()); self.undo = self.undo[-100:]; self.redo = []

    def _margins_changed(self, *_):
        if self.margin_suppressed: return
        if self.margin_timer: self.root.after_cancel(self.margin_timer)
        self.margin_timer = self.root.after(250, self.flush_margins)

    def flush_margins(self):
        if self.margin_timer:
            self.root.after_cancel(self.margin_timer); self.margin_timer = None
        try:
            before, after = model.number(self.before.get()), model.number(self.after.get())
        except (ValueError, TypeError):
            self.status.set('前後秒数は0〜86400の数値で指定してください。'); return
        if (before, after) != (self.project['before'], self.project['after']):
            self.remember_margins()
            self.project.update(before=before, after=after)
            self.update_margin_preview()
            self.status.set('表示を前{}秒／後{}秒へ変更しました。10秒へ即時に戻せます。'.format(before, after))

    def update_margin_preview(self):
        active = self.play_items[self.play_index]['clip_id'] if self.play_items else None
        self.stop_playback(); self.play_items = []
        self.changed(); self.refresh()
        clip = next((c for c in model.current_clips(self.project) if c['id'] == active), None)
        if clip:
            try: self.start_playlist(media.playlist(self.project, [clip]), False)
            except Exception as error: self.status.set(str(error))

    def set_margins(self, seconds):
        self.before.set(str(seconds)); self.after.set(str(seconds)); self.flush_margins()

    def undo_margins(self, redo=False):
        self.flush_margins()
        source, destination = (self.redo, self.undo) if redo else (self.undo, self.redo)
        if not source: return
        destination.append(self.margin_state()); saved = source.pop()
        self.project.update(before=saved['before'], after=saved['after'])
        for clip in self.project['clips']:
            clip.pop('before', None); clip.pop('after', None)
            clip.update(saved['overrides'].get(clip['id'], {}))
        self.margin_suppressed = True
        self.before.set(str(saved['before'])); self.after.set(str(saved['after']))
        self.margin_suppressed = False
        self.update_margin_preview()

    def tune_selected(self):
        clips = self.selected_clips()
        if not clips: return
        before = simpledialog.askfloat('個別の微調整', '選択候補の前の秒数', initialvalue=clips[0].get('before', self.project['before']),
                                       minvalue=0, maxvalue=86400, parent=self.root)
        if before is None: return
        after = simpledialog.askfloat('個別の微調整', '選択候補の後の秒数', initialvalue=clips[0].get('after', self.project['after']),
                                      minvalue=0, maxvalue=86400, parent=self.root)
        if after is None: return
        self.remember_margins()
        for clip in clips: clip.update(before=before, after=after)
        self.update_margin_preview()

    def clear_overrides(self):
        self.remember_margins()
        for clip in self.selected_clips():
            clip.pop('before', None); clip.pop('after', None)
        self.update_margin_preview()

    def select_clip(self, _event=None):
        clips = self.selected_clips()
        if self.playing or not clips: return
        try:
            self.start_playlist(media.playlist(self.project, clips[:1]), False)
        except Exception as error:
            self.status.set(str(error))

    def play(self, scope):
        self.flush_margins()
        clips = self.all_visible if scope == 'visible' else self.selected_clips()
        if scope == 'group' and clips:
            info = self.groups_by_clip.get(clips[0]['id'])
            if not info:
                self.status.set('類似解析後にグループ内の候補を選択してください。'); return
            members = {m['id'] for m in info[1]['members']}
            clips = [c for c in model.current_clips(self.project) if c['id'] in members]
        try:
            self.start_playlist(media.playlist(self.project, clips), True)
        except Exception as error:
            self.error(error)

    def start_playlist(self, items, playing):
        self.stop_playback()
        if not items: return
        self.play_items, self.play_index, self.playing = items, 0, playing
        self.clock.set_speed(self.speed.get())
        self._begin_item()

    def _begin_item(self):
        item = self.play_items[self.play_index]
        self.clock.seek(item['start']); self.last_requested = None
        self.token += 1; self.pending = False
        self.seek.configure(from_=item['start'], to=item['end'])
        self._request_frame(item['start'])

    def _request_frame(self, seconds):
        item = self.play_items[self.play_index]
        self.decoder.request(self.token, item['source'], seconds,
                             (max(160, self.canvas.winfo_width()), max(90, self.canvas.winfo_height())))
        self.pending, self.last_requested = True, seconds

    def stop_playback(self):
        self.playing, self.pending = False, False
        self.token += 1

    def seek_to(self, value):
        if self.seeking or not self.play_items: return
        self.token += 1; self.pending = False
        item = self.play_items[self.play_index]
        seconds = max(item['start'], min(float(value), item['end'] - 1 / item['source']['fps']))
        self.clock.seek(seconds); self._request_frame(seconds)

    def tick(self):
        if self.closing: return
        while True:
            try:
                token, seconds, frame, error = self.decoder.results.get_nowait()
            except queue.Empty:
                break
            if token != self.token: continue
            self.pending = False
            if error:
                self.stop_playback(); self.status.set(error); continue
            self.last_frame = frame
            self.photo = ImageTk.PhotoImage(Image.fromarray(frame))
            self.canvas.delete('all')
            self.canvas.create_image(self.canvas.winfo_width() // 2, self.canvas.winfo_height() // 2, image=self.photo)
            self.clock.shown(seconds)
            self.seeking = True; self.seek.set(seconds); self.seeking = False
            item = self.play_items[self.play_index]
            self.clip_label.set('{}/{} | {} | {:.3f}秒 ({:.2f}–{:.2f})\n{}'.format(
                self.play_index + 1, len(self.play_items), item['label'], seconds,
                item['start'], item['end'], item['source']['path']))
        if self.playing and not self.pending and self.play_items:
            item = self.play_items[self.play_index]
            target = self.clock.target()
            if target >= item['end']:
                self.play_index += 1
                if self.play_index >= len(self.play_items):
                    self.play_index = len(self.play_items) - 1
                    self.stop_playback(); self.status.set('連続再生が終了しました。')
                else: self._begin_item()
            elif target > (self.last_requested if self.last_requested is not None else -1):
                self._request_frame(target)
        self.root.after(40, self.tick)

    def close(self):
        if self.busy:
            self.cancel.set(); self.status.set('中止処理中です。処理が止まった後に閉じてください。'); return
        if self.dirty and not self.save(): return
        self.shutdown()

    def shutdown(self):
        self.closing = True
        self.cancel.set(); self.decoder.close()
        for timer in self.root.tk.call('after', 'info'):
            self.root.after_cancel(timer)
        self.root.destroy()

    def load_rule_form(self, _event=None):
        if not self.project['rules']: return
        self.form_loading = True
        rule = copy.deepcopy(self.selected_rule())
        draft = self.project.get('rule_drafts', {}).get(rule['id'], {})
        if draft: rule = copy.deepcopy(draft['rule'])
        self.editing_rule = rule
        self.edit_rule_name.set(draft.get('name', rule['name']))
        self.event.set(draft.get('event', next((label for label, value in EVENTS.items() if value == rule['event']), list(EVENTS)[0])))
        self.interval.set(draft.get('interval', str(rule['interval'])))
        self.stability.set(draft.get('stability', str(rule['stable_samples'])))
        self.rebuild_condition_tree()
        self.form_loading = False

    def capture_rule_draft(self, *_):
        if self.form_loading or not hasattr(self, 'editing_rule'): return
        if self.form_node is not None:
            self.form_node['_raw_form'] = {'name': self.node_name.get(), 'path': self.node_path.get(),
                'threshold': self.node_threshold.get(), 'crop': self.node_crop.get(),
                'template_crop': self.node_template_crop.get(), 'gray': self.node_gray.get(),
                'stable_seconds': self.node_stable.get(), 'within_seconds': self.node_within.get(),
                'cooldown_seconds': self.node_cooldown.get()}
        draft = {'rule': copy.deepcopy(self.editing_rule), 'name': self.edit_rule_name.get(),
                 'event': self.event.get(), 'interval': self.interval.get(), 'stability': self.stability.get()}
        drafts = self.project.setdefault('rule_drafts', {})
        if drafts.get(self.editing_rule['id']) != draft:
            drafts[self.editing_rule['id']] = draft
            self.changed()

    def rebuild_condition_tree(self):
        self.rule_tree.delete(*self.rule_tree.get_children())
        self.condition_nodes = {}
        def add(node, parent=''):
            iid = 'node_' + str(len(self.condition_nodes))
            label = '{}  {}'.format(OPS.get(node['op'], node['op']), node.get('name', ''))
            if node['op'] == 'image':
                label += '  ≥{:.2f}'.format(float(node['variant'].get('threshold', .8)))
            self.rule_tree.insert(parent, 'end', iid=iid, text=label, open=True)
            self.condition_nodes[iid] = node
            for child in node.get('children', []): add(child, iid)
        add(self.editing_rule['condition'])
        self.rule_tree.selection_set('node_0')
        self.select_condition()

    def condition_node(self):
        selected = self.rule_tree.selection()
        return self.condition_nodes.get(selected[0]) if selected else self.editing_rule['condition']

    def select_condition(self, _event=None):
        node = self.condition_node()
        if node is None: return
        was_loading = self.form_loading
        self.form_loading = True
        self.form_node = node
        raw = node.get('_raw_form', {})
        self.node_name.set(raw.get('name', node.get('name', '')))
        variant = node.get('variant', {})
        self.node_path.set(raw.get('path', variant.get('template_path', '')))
        self.node_threshold.set(raw.get('threshold', str(variant.get('threshold', .8))))
        self.node_crop.set(raw.get('crop', ','.join(str(v) for v in (variant.get('crop') or [0, 0, 0, 0]))))
        self.node_template_crop.set(raw.get('template_crop', ','.join(str(v) for v in (variant.get('template_crop') or [0, 0, 0, 0]))))
        self.node_gray.set(raw.get('gray', variant.get('use_gray', True)))
        self.node_stable.set(raw.get('stable_seconds', str(node.get('stable_seconds', 0))))
        self.node_within.set(raw.get('within_seconds', str(node.get('within_seconds', 30))))
        self.node_cooldown.set(raw.get('cooldown_seconds', str(node.get('cooldown_seconds', 5))))
        self.form_loading = was_loading
        try:
            if self.node_path.get():
                with Image.open(self.node_path.get()) as image:
                    image.thumbnail((480, 170))
                    self.template_photo = ImageTk.PhotoImage(image.copy())
                self.template_preview.configure(image=self.template_photo, text='')
            else: self.template_preview.configure(image='', text='グループを選択中')
        except Exception as error:
            self.template_preview.configure(image='', text=str(error))

    def update_node(self, rebuild=True):
        node = self.form_node
        if node is None: return True
        try:
            self.capture_rule_draft()
            self.normalize_node_form(node)
            if rebuild: self.rebuild_condition_tree()
            self.capture_rule_draft()
            return True
        except Exception as error:
            self.error(error); return False

    def apply_rule(self, quiet=False):
        if not hasattr(self, 'editing_rule'): return True
        if not self.update_node(False): return False
        try:
            rule = copy.deepcopy(self.editing_rule)
            self.normalize_node_form(rule['condition'], recursive=True)
            rule.update(name=self.edit_rule_name.get().strip(), event=EVENTS[self.event.get()],
                        interval=model.number(self.interval.get(), 0, 3600),
                        stable_samples=int(model.number(self.stability.get(), 1, 120)))
            if not rule['name']: raise ValueError('条件名を入力してください。')
            detection.build_matcher(rule['condition'])
            if rule['condition'].get('op') == 'sequence' and rule['event'] != 'enter':
                raise ValueError('順序条件の抽出方法は「成立の前後」を選択してください。')
            index = next(i for i, r in enumerate(self.project['rules']) if r['id'] == rule['id'])
            if self.project['rules'][index] != rule:
                self.project['rules'][index] = rule
                self.editing_rule = copy.deepcopy(rule)
                self.rule_combo['values'] = [r['name'] for r in self.project['rules']]
                self.rule_combo.current(index)
                self.changed()
            self.project.setdefault('rule_drafts', {}).pop(rule['id'], None)
            self.editing_rule = copy.deepcopy(rule)
            self.rebuild_condition_tree()
            if not quiet: self.status.set('条件を適用しました。変更後の条件で解析すると結果が更新されます。')
            return True
        except Exception as error:
            self.error(error); return False

    @staticmethod
    def normalize_node_form(node, recursive=False):
        raw = node.get('_raw_form')
        if raw:
            variant = copy.deepcopy(node.get('variant', {}))
            if node['op'] == 'image':
                if not raw['path'].strip(): raise ValueError('条件画像を指定してください。')
                if model.canonical(raw['path']) != model.canonical(variant.get('template_path', '')):
                    variant.pop('sha256', None)
                variant.update(template_path=str(Path(raw['path']).resolve()),
                               threshold=model.number(raw['threshold'], 0, 1), use_gray=raw['gray'])
                for key in ('crop', 'template_crop'):
                    rect = [int(v.strip()) for v in raw[key].split(',')]
                    if len(rect) != 4 or any(v < 0 for v in rect):
                        raise ValueError('範囲は0以上の x1,y1,x2,y2 です。')
                    variant[key] = rect
                node['variant'] = variant
            node['name'] = raw['name']
            if node['op'] != 'image':
                node['stable_seconds'] = model.number(raw.get('stable_seconds', 0), 0, 60)
            if node['op'] == 'sequence':
                node['within_seconds'] = model.number(raw.get('within_seconds', 30), .01, 3600)
                node['cooldown_seconds'] = model.number(raw.get('cooldown_seconds', 5), 0, 3600)
            node.pop('_raw_form', None)
        if recursive:
            for child in node.get('children', []): Studio.normalize_node_form(child, True)

    def add_rule(self):
        if not self.guard(): return
        self.project['rules'].append(detection.new_rule())
        self._refresh_rules(len(self.project['rules']) - 1); self.changed()

    def duplicate_rule(self):
        if not self.guard() or not self.apply_rule(): return
        rule = copy.deepcopy(self.selected_rule())
        rule['id'] = detection.uuid.uuid4().hex
        rule['name'] += '（コピー）'
        self.project['rules'].append(rule)
        self._refresh_rules(len(self.project['rules']) - 1); self.changed()

    def import_rule(self):
        if not self.guard(): return
        path = filedialog.askopenfilename(parent=self.root, filetypes=[('切り抜き条件', '*.json')])
        if not path: return
        try:
            rule = json.loads(Path(path).read_text(encoding='utf-8-sig'))
            detection.build_matcher(rule['condition'])
            for field in ('name', 'interval', 'stable_samples', 'event'):
                if field not in rule: raise ValueError('条件の項目がありません: ' + field)
            rule['id'] = detection.uuid.uuid4().hex
            self.project['rules'].append(rule)
            self._refresh_rules(len(self.project['rules']) - 1); self.changed()
        except Exception as error: self.error(error)

    def export_rule(self):
        if not self.apply_rule(): return
        path = filedialog.asksaveasfilename(parent=self.root, defaultextension='.json',
                                            initialfile='clip_rule.json', filetypes=[('切り抜き条件', '*.json')])
        if path:
            try: model.atomic_json(path, self.selected_rule())
            except Exception as error: self.error(error)

    def import_recording_rule(self):
        if not self.guard(): return
        try:
            rule = detection.import_pokecon_rule(self.settings_path.get())
            self.project['rules'].append(rule)
            self._refresh_rules(len(self.project['rules']) - 1)
            self.before.set(str(rule['suggested_before'])); self.after.set(str(rule['suggested_after']))
            self.flush_margins(); self.changed()
            self.status.set('PokeConの条件・順序・継続秒・前後秒をコピーしました。解析側で調整できます。')
        except Exception as error: self.error(error)

    def append_node(self, node):
        parent = self.condition_node()
        if parent['op'] == 'image':
            self.status.set('追加先のAND／ORグループを選択してください。'); return
        parent.setdefault('children', []).append(node)
        self.rebuild_condition_tree()
        self.capture_rule_draft()

    def add_group(self, op):
        self.append_node({'op': op, 'name': OPS[op], 'children': []})

    def add_image(self):
        paths = filedialog.askopenfilenames(parent=self.root, filetypes=[('条件画像', '*.png *.jpg *.jpeg *.bmp')])
        parent = self.condition_node()
        if parent['op'] == 'image':
            self.status.set('追加先のグループを選択してください。'); return
        for path in paths:
            parent.setdefault('children', []).append(detection.image_node({'template_path': path,
                'threshold': .8, 'use_gray': True, 'crop': [0, 0, 0, 0]}, Path(path).stem))
        self.rebuild_condition_tree()
        self.capture_rule_draft()

    def remove_condition(self):
        selected = self.rule_tree.selection()
        if not selected: return
        parent_id = self.rule_tree.parent(selected[0])
        if not parent_id: return
        parent, child = self.condition_nodes[parent_id], self.condition_nodes[selected[0]]
        parent['children'] = [c for c in parent['children'] if c is not child]
        self.rebuild_condition_tree()
        self.capture_rule_draft()

    def load_catalog_source(self):
        path = filedialog.askopenfilename(parent=self.root,
            initialdir=str(detection.SERIAL_ROOT / 'Commands/PythonCommands'), filetypes=[('Commandsソース', '*.py')])
        if not path: return
        self.job('画像の登録条件を読み込んでいます…', lambda p: detection.source_targets(path), self.set_catalog)

    def load_catalog_library(self):
        path = filedialog.askopenfilename(parent=self.root, initialdir=str(detection.SERIAL_ROOT / 'Template'),
                                          initialfile='image_detection_profiles.json', filetypes=[('登録ライブラリ', '*.json')])
        if not path: return
        def work(_progress):
            value = json.loads(Path(path).read_text(encoding='utf-8-sig'))
            return {name: detection.target_node(name, item['variants'], item.get('operator', 'OR'))
                    for name, item in value['targets'].items() if item.get('variants')}
        self.job('画像の登録条件を読み込んでいます…', work, self.set_catalog)

    def set_catalog(self, values):
        self.catalog = values
        names = sorted(values)
        self.catalog_combo['values'] = names
        if names: self.catalog_combo.current(0)
        self.status.set('{}件の画像条件を読み込みました。'.format(len(names)))

    def add_catalog(self):
        value = self.catalog.get(self.catalog_choice.get())
        if value: self.append_node(copy.deepcopy(value))

    def test_condition(self):
        if not self.apply_rule() or not self.play_items: return
        item = copy.deepcopy(self.play_items[self.play_index])
        when, rule = self.clock.position, copy.deepcopy(self.selected_rule())
        def work(_progress):
            source = item['source']; model.require_source(source)
            cap = detection.cv2.VideoCapture(source['path'])
            try:
                frame, actual = detection.read_at(cap, source, when)
                matcher = detection.build_matcher(rule['condition'])
                matched = matcher.match(frame)
                matcher.verify_assets(); model.require_source(source)
                return matched, actual
            finally: cap.release()
        def complete(result):
            matched, actual = result
            text = (' / '.join('段階{}:{}'.format(i + 1, '一致' if value else '不一致') for i, value in enumerate(matched))
                    + '（順序・継続の成立は全体解析で確認）') if isinstance(matched, list) else ('一致' if matched else '不一致')
            self.status.set('元動画 {:.3f}秒: {}'.format(actual, text))
        self.job('現在の元フレームを照合しています…', work, complete)

    def choose_library(self):
        if not self.guard(): return
        path = filedialog.askdirectory(parent=self.root)
        if path:
            self.library_path.set(path); self.project['library_dir'] = path
            self.changed(); self.refresh_library()

    def refresh_library(self):
        try:
            values = media.Library(self.library_path.get()).entries()
            self.library_tree.delete(*self.library_tree.get_children())
            self.library_entries = {value['id']: value for value in values}
            for value in values:
                self.library_tree.insert('', 'end', iid=value['id'], values=(
                    value['clip']['rule_name'], Path(value['source']['path']).name,
                    '{:.2f}–{:.2f}'.format(value['start'], value['end']), '済' if value['reviewed'] else '未',
                    time.strftime('%Y-%m-%d %H:%M', time.localtime(value['added_at']))))
        except Exception as error: self.status.set(str(error))

    def collect_selected(self):
        self.flush_margins()
        clips = copy.deepcopy(self.selected_clips())
        if not clips:
            self.status.set('解析一覧で蓄積する候補を選択してください。'); return
        project, directory = copy.deepcopy(self.project), self.library_path.get()
        def complete(values):
            self.refresh_library(); self.status.set('{}件をユニーク蓄積へ保存しました。'.format(len(values)))
        self.job('選択した候補を動画として蓄積しています…',
                 lambda p: media.Library(directory).add(project, clips, self.cancel, p), complete)

    def play_library(self):
        try:
            items = []
            for selected in self.library_tree.selection():
                value = self.library_entries[selected]
                source = detection.probe(value['path'])
                if value.get('media_signature') and source['signature'] != value['media_signature']:
                    raise ValueError('蓄積動画が登録後に変更されています: ' + value['path'])
                items.append({'source': source, 'start': 0.0, 'end': source['duration'],
                               'clip_id': value['id'], 'label': value['clip']['rule_name']})
            self.start_playlist(items, True)
            # Make the shared player visible.
            self.review_tab.master.select(self.review_tab)
        except Exception as error: self.error(error)

    def compare_library(self, include_candidates=False):
        values = [self.library_entries[i] for i in self.library_tree.selection()]
        if not values: values = list(self.library_entries.values())
        if not values: return
        snapshot = copy.deepcopy(self.project)
        try: threshold = model.number(self.threshold.get(), .5, 1)
        except ValueError as error: self.error(error); return
        def work(progress):
            project = model.new_project(); project.update(before=0, after=0)
            for value in values:
                source = detection.probe(value['path'])
                if value.get('media_signature') and source['signature'] != value['media_signature']:
                    raise ValueError('蓄積動画が登録後に変更されています: ' + value['path'])
                key = model.canonical(value['path']); project['sources'][key] = source
                clip = model.make_clip(key, {'id': 'library', 'name': value['clip']['rule_name']},
                                       0.0, source['duration'], 'match', source['signature'])
                clip['id'] = value['id']; project['clips'].append(clip)
            if include_candidates:
                for clip in model.current_clips(snapshot):
                    candidate = copy.deepcopy(clip)
                    # Preserve each candidate's current view inside the zero-margin comparison.
                    candidate['before'] = candidate.get('before', snapshot['before'])
                    candidate['after'] = candidate.get('after', snapshot['after'])
                    candidate['rule_name'] = '今回: ' + candidate['rule_name']
                    project['sources'][candidate['source']] = snapshot['sources'][candidate['source']]
                    project['clips'].append(candidate)
            groups, _key = media.group_clips(project, project['clips'], threshold, self.cancel, progress)
            return project, groups
        def complete(result):
            project, groups = result
            dialog = tk.Toplevel(self.root); dialog.title('蓄積内の類似候補'); dialog.geometry('950x560')
            tree = tree_with_scroll(dialog, ('group', 'name', 'score', 'source'), ('グループ', '条件', '一致度', '出典'))
            for index, group in enumerate(groups):
                for member in group['members']:
                    clip = next(c for c in project['clips'] if c['id'] == member['id'])
                    tree.insert('', 'end', iid=member['id'], values=(index + 1, clip['rule_name'],
                                     '{:.1%}'.format(member['score']), project['sources'][clip['source']]['path']))
            def play_group():
                selected = tree.selection()
                if not selected: return
                group = next(g for g in groups if any(m['id'] == selected[0] for m in g['members']))
                ids = {m['id'] for m in group['members']}
                self.start_playlist(media.playlist(project, [c for c in project['clips'] if c['id'] in ids]), True)
                self.review_tab.master.select(self.review_tab)
                dialog.destroy()
            ttk.Button(dialog, text='選択した類似グループを全再生', command=play_group).pack(pady=7)
            self.status.set('{}件を{}類似グループに分類しました。'.format(len(project['clips']), len(groups)))
        self.job('蓄積した動画を比較しています…', work, complete)

    def choose_output(self):
        path = filedialog.askdirectory(parent=self.root)
        if path: self.output_path.set(path)

    def choose_settings(self):
        if not self.guard(): return
        path = filedialog.askopenfilename(parent=self.root, initialdir=str(detection.SERIAL_ROOT / 'profiles'),
                                          filetypes=[('PokeCon設定', '*.ini')])
        if path: self.settings_path.set(path); self.refresh_channels()

    def refresh_channels(self):
        try:
            store = media.youtube.load_channel_store(media.youtube.channel_store_path(self.settings_path.get()))
            names = sorted(store.get('profiles', {})); self.channel_combo['values'] = names
            if self.channel.get() not in names:
                self.channel.set(store.get('default_profile', '') or (names[0] if names else ''))
        except Exception as error: self.status.set(str(error))

    def authorize_channel(self):
        if not self.guard(): return
        path = filedialog.askopenfilename(parent=self.root, title='Google OAuthクライアントJSON', filetypes=[('OAuth client', '*.json')])
        if not path: return
        name = simpledialog.askstring('YouTubeチャンネル設定', 'PokeConと共用する設定名', parent=self.root)
        if not name: return
        store = media.youtube.channel_store_path(self.settings_path.get())
        def complete(_result):
            self.refresh_channels(); self.channel.set(name)
            self.status.set('YouTubeチャンネルを認証しました。')
        self.job('ブラウザでYouTubeチャンネルを認証してください（最大5分）。',
                 lambda p: media.youtube.authorize_installed_app(path, name, store), complete)

    def set_upload_text(self, text):
        self.upload_text.configure(state='normal'); self.upload_text.delete('1.0', 'end')
        self.upload_text.insert('1.0', text); self.upload_text.configure(state='disabled')

    def export_snapshot(self):
        self.flush_margins()
        snapshot = copy.deepcopy(self.project)
        scope = self.upload_scope.get()
        clips = copy.deepcopy(self.selected_clips() if scope == '解析の選択' else self.all_visible)
        seconds = model.number(self.split_minutes.get(), 0, 660, '分割の分数') * 60
        return {'project': snapshot, 'scope': scope, 'clips': clips, 'seconds': seconds,
                'merge': self.merge.get(), 'roots': list(snapshot['roots']), 'excluded': self.excluded_paths(),
                'output': self.output_path.get(), 'settings': self.settings_path.get(), 'channel': self.channel.get()}

    def export_items(self, settings):
        if settings['scope'] != '指定フォルダの全動画':
            return media.playlist(settings['project'], settings['clips'])
        paths, errors = model.discover(settings['roots'], settings['excluded'], self.cancel)
        if errors: raise ValueError('\n'.join(errors))
        result = []
        for path in paths:
            media.check_cancel(self.cancel)
            source = detection.probe(path)
            result.append({'source': source, 'start': 0.0, 'end': source['duration'],
                           'clip_id': model.digest(source['signature']), 'label': Path(path).stem})
        return result

    def inspect_export(self):
        try: settings = self.export_snapshot()
        except Exception as error: self.error(error); return
        def complete(items):
            plan = media.split_plan(items, settings['merge'], settings['seconds'])
            lines = ['対象{}件 → 出力{}本 / 合計{:.1f}分'.format(len(items), len(plan), sum(i['end'] - i['start'] for i in items) / 60),
                     '出力先: ' + settings['output']]
            lines += ['{} | {:.3f}–{:.3f}秒'.format(i['source']['path'], i['start'], i['end']) for i in items]
            self.set_upload_text('\n'.join(lines)); self.status.set('対象一覧を確認できます。')
        self.job('書き出し対象を確認しています…', lambda p: self.export_items(settings), complete)

    def export(self, upload):
        if not self.guard(): return
        try: settings = self.export_snapshot()
        except Exception as error: self.error(error); return
        # Prepare the exact immutable list before asking to transmit it.
        def prepared(items):
            if not items: raise ValueError('対象動画がありません。')
            plan = media.split_plan(items, settings['merge'], settings['seconds'])
            self.set_upload_text('\n'.join('{} | {:.3f}–{:.3f}'.format(i['source']['path'], i['start'], i['end']) for i in items))
            if upload and not messagebox.askyesno('YouTubeへアップロード',
                    'チャンネル設定: {}\n対象{}件 → {}本\n合計 {:.1f}分・限定公開\n\n表示した対象をアップロードします。元動画は保持します。'.format(
                        settings['channel'] or '既定', len(items), len(plan), sum(i['end'] - i['start'] for i in items) / 60), parent=self.root):
                self.status.set('アップロードを取り消しました。'); return
            def work(progress):
                # Full independent files need no transcoding. The shared queue splits long files.
                direct = upload and not settings['merge'] and settings['scope'] == '指定フォルダの全動画' and (settings['seconds'] == 0 or settings['seconds'] >= 600)
                if direct:
                    result = {'outputs': [i['source']['path'] for i in items], 'status': 'complete'}
                    for item in items: model.require_source(item['source'])
                else:
                    result = media.export_plan(items, settings['output'], settings['merge'], settings['seconds'], self.cancel, progress)
                if upload:
                    result['jobs'] = media.queue_uploads(result['outputs'], settings['settings'], settings['channel'],
                        settings['seconds'] or 11 * 3600, self.data_root / 'upload_sessions', self.cancel)
                return result
            def complete(result):
                self.project['upload_runs'].append({'time': time.time(), 'outputs': result['outputs'], 'jobs': result.get('jobs', [])})
                self.changed()
                self.set_upload_text('\n'.join(result['outputs']) + ('\n\nキュー登録:\n' + '\n'.join(result['jobs']) if upload else ''))
                self.status.set('{}本を{}。'.format(len(result['outputs']), 'アップロードキューへ登録しました' if upload else '書き出しました'))
            # The previous job's callback is finishing; start the next one on the next event turn.
            self.root.after_idle(lambda: self.job('動画を準備しています…', work, complete))
        self.job('対象動画と出力数を確認しています…', lambda p: self.export_items(settings), prepared)

    def refresh_queue(self):
        directory = Path(media.youtube.upload_queue_dir(self.settings_path.get()))
        lines = []
        for path in sorted(directory.glob('*.json')):
            try:
                value = json.loads(path.read_text(encoding='utf-8'))
                if value.get('recording_kind') != 'video_analysis': continue
                lines.append('{} | {} | {}'.format(value.get('status'), value.get('command'), value.get('error', '')))
                for segment in value.get('segments', []):
                    if segment.get('video_id'): lines.append(media.youtube.youtube_watch_url(segment['video_id']))
            except (OSError, ValueError): continue
        self.set_upload_text('\n'.join(lines) or 'この設定に解析ツールのアップロードはありません。')

    def resume_queue(self):
        if not self.guard(): return
        settings, requested = self.settings_path.get(), self.channel.get()
        def work(_progress):
            store_path = media.youtube.channel_store_path(settings)
            store = media.youtube.load_channel_store(store_path)
            name = requested or store.get('default_profile', '')
            if name not in store.get('profiles', {}):
                raise ValueError('YouTubeチャンネルを認証してください。')
            queue_dir = media.youtube.upload_queue_dir(settings)
            media.youtube.resume_upload_jobs_for_profile(queue_dir, store_path, name)
            media.youtube.launch_upload_worker(queue_dir, store_path)
        def complete(_value):
            self.refresh_queue(); self.status.set('PokeCon共通のアップロードキューを再開しました。')
        self.job('共通キューを確認しています…', work, complete)


def main(argv=None):
    parser = argparse.ArgumentParser(description='PokeCon offline video analysis studio')
    parser.add_argument('--project')
    parser.add_argument('--settings')
    parser.add_argument('--folder', action='append', default=[])
    args = parser.parse_args(argv)
    detection.cv2.setNumThreads(1)
    root = tk.Tk()
    Studio(root, args.project, args.settings, args.folder)
    root.mainloop()


if __name__ == '__main__':
    main()
