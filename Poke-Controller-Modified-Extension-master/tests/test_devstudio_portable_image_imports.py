"""Generated image imports run under nested Origin and flat portable layouts."""
import ast
import builtins
import re
import textwrap
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'DevStudio/PokeConDevStudio.py'
NAMES = {'_sample_program_source', 'refresh_sample_program_fragments', '_apply_image_code_to_editor'}
IMAGE_CODE = '# POKECON_IMAGE_CHECK_BEGIN\ndef image_check(self):\n    return True\n# POKECON_IMAGE_CHECK_END'


class Editor:
    def __init__(self, text):
        self.text = text

    def get(self, *args):
        return self.text

    def delete(self, *args):
        self.text = ''

    def insert(self, _index, text):
        self.text = text


class PortableImageImportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tree = ast.parse(SOURCE.read_text('utf-8-sig'), feature_version=(3, 7))
        cls.namespace = dict(re=re, textwrap=textwrap,
            python_identifier=lambda name: 'Example', resolve_members=lambda data, name: [],
            preserve_library_import_block=lambda code, source: code)
        functions = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name in NAMES]
        assert len(functions) == len(NAMES)
        module = ast.fix_missing_locations(ast.Module(body=functions, type_ignores=[]))
        exec(compile(module, str(SOURCE), 'exec'), cls.namespace)

    def app(self, imports=(), image_code=IMAGE_CODE):
        self.namespace['compose_preview'] = lambda root, data, name: dict(
            imports=list(imports), class_variables=[], initializers=[], included=[], image_targets=[])
        box = lambda value: types.SimpleNamespace(get=lambda: value, set=lambda value: None)
        app = types.SimpleNamespace(fragment_root=lambda: '.',
            _generated_region=lambda name, body, indent: body + '\n',
            _image_code_for_target_names=lambda *args, **kwargs: image_code,
            _indent_source=lambda value, indent: textwrap.indent(value, indent),
            _extract_image_check_user=lambda source: None,
            _fragment_blocks=lambda source: {}, _generated_blocks=lambda source: {},
            _extract_user_region=lambda source, name: None,
            _extract_image_check_block=lambda source: textwrap.indent(IMAGE_CODE, '    '),
            ui_text=lambda english, japanese: english, status=box(''),
            sample_program_list=box('Example'), sample_program_path=box(''),
            update_editor_view=lambda: None, _update_sample_program_line_numbers=lambda: None)
        for name in NAMES:
            setattr(app, name, types.MethodType(self.namespace[name], app))
        return app

    def assert_imports_run_in_both_layouts(self, source):
        tree = ast.parse(source, feature_version=(3, 7))
        imports = ast.Module(body=[n for n in tree.body if isinstance(n, ast.Try)
            or isinstance(n, ast.ImportFrom) and n.module and 'LocalFunction' in n.module], type_ignores=[])
        self.assertTrue(imports.body)
        code = compile(ast.fix_missing_locations(imports), '<generated imports>', 'exec')
        for layout in ('nested', 'flat'):
            with self.subTest(layout=layout):
                calls = []
                fake = types.SimpleNamespace(SimilarityHistory=object(), detect_image=object(),
                    confirm_consecutive_image_matches=object())
                def importer(name, globals=None, locals=None, fromlist=(), level=0):
                    calls.append(name)
                    if name == 'Commands.PythonCommands.LocalFunction.ImageDetection':
                        if layout == 'flat':
                            raise ModuleNotFoundError('missing nested package', name='Commands.PythonCommands.LocalFunction')
                        return fake
                    if name == 'LocalFunction.ImageDetection':
                        if layout == 'nested':
                            raise AssertionError('Nested imports must not require the flat alias')
                        return fake
                    return builtins.__import__(name, globals, locals, fromlist, level)
                namespace = {'__builtins__': dict(vars(builtins), __import__=importer)}
                exec(code, namespace)
                self.assertIs(namespace['detect_image'], fake.detect_image)
                self.assertIs(namespace['SimilarityHistory'], fake.SimilarityHistory)
                self.assertEqual('LocalFunction.ImageDetection' in calls, layout == 'flat')
        def broken_dependency(name, globals=None, locals=None, fromlist=(), level=0):
            if name == 'Commands.PythonCommands.LocalFunction.ImageDetection':
                raise ModuleNotFoundError('missing dependency', name='numpy')
            raise AssertionError('A missing dependency must not trigger the flat fallback')
        with self.assertRaises(ModuleNotFoundError) as caught:
            exec(code, {'__builtins__': dict(vars(builtins), __import__=broken_dependency)})
        self.assertEqual(caught.exception.name, 'numpy')

    def test_sample_generation_wraps_image_and_metadata_imports(self):
        app = self.app(imports=('from LocalFunction.ImageDetection import SimilarityHistory, detect_image',
            'from LocalFunction.ImageDetection import (confirm_consecutive_image_matches,\n SimilarityHistory)'))
        source = app._sample_program_source('Example', fragment_root='.', data={})
        self.assert_imports_run_in_both_layouts(source)
        self.assertFalse(any(isinstance(n, ast.ImportFrom) and n.module == 'LocalFunction.ImageDetection'
            for n in ast.parse(source).body))

    def test_applying_image_code_upgrades_existing_flat_import(self):
        app = self.app()
        app.sample_program_editor = object()
        app.editor = Editor('from LocalFunction.ImageDetection import SimilarityHistory, detect_image\nclass Example:\n    pass\n')
        self.assertTrue(app._apply_image_code_to_editor(app.editor, IMAGE_CODE))
        self.assert_imports_run_in_both_layouts(app.editor.text)

    def test_applying_image_code_reuses_existing_canonical_alias(self):
        app = self.app()
        app.sample_program_editor = object()
        app.editor = Editor('import Commands.PythonCommands.LocalFunction.ImageDetection as _image_detection\n'
            'SimilarityHistory = _image_detection.SimilarityHistory\ndetect_image = _image_detection.detect_image\n'
            'class Example:\n    pass\n')
        self.assertTrue(app._apply_image_code_to_editor(app.editor, IMAGE_CODE))
        self.assertNotIn('from LocalFunction.ImageDetection', app.editor.text)
        ast.parse(app.editor.text, feature_version=(3, 7))

    def test_refreshing_preserved_image_block_uses_portable_import(self):
        app = self.app(image_code='')
        app.sample_program_editor = Editor('class Example:\n    # POKECON_USER_DO_BEGIN\n    pass\n')
        app._sample_program_source = lambda name: ('class Example:\n    # POKECON_USER_METHODS_BEGIN\n    pass\n')
        app.refresh_sample_program_fragments()
        self.assert_imports_run_in_both_layouts(app.sample_program_editor.text)

    def test_refreshing_legacy_flat_header_upgrades_import(self):
        app = self.app(image_code='')
        app.sample_program_editor = Editor('class Example:\n    # POKECON_USER_DO_BEGIN\n    pass\n')
        app._sample_program_source = lambda name: (
            'from LocalFunction.ImageDetection import SimilarityHistory, detect_image\n'
            'class Example:\n    # POKECON_USER_METHODS_BEGIN\n    pass\n')
        app.refresh_sample_program_fragments()
        self.assert_imports_run_in_both_layouts(app.sample_program_editor.text)


if __name__ == '__main__':
    unittest.main()
