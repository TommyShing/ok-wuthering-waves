"""Exercise the real new-scheme config persistence in disposable directories.

Extract source definitions to avoid importing OK or starting its GUI/game runtime.
All writes go to TemporaryDirectory; personal configs are read only for target keys.
"""
import ast
import json
import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
TASKS = ('FarmEchoTask', 'DailyTask', 'TacetTask', 'ForgeryTask')


def load_config_implementation():
    namespace = {'os': os, 'json': json, 'logger': logging.getLogger('offline-config')}
    tree = ast.parse((ROOT / 'ok/util/file.py').read_text(encoding='utf-8-sig'))
    names = {'read_json_file', 'write_json_file', 'get_relative_path',
             'ensure_dir_for_file', 'ensure_dir'}
    definitions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                   and node.name in names]
    exec(compile(ast.Module(body=definitions, type_ignores=[]), '<actual file helpers>', 'exec'), namespace)
    tree = ast.parse((ROOT / 'ok/util/config.py').read_text(encoding='utf-8-sig'))
    definition = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                      and node.name == 'Config')
    exec(compile(ast.Module(body=[definition], type_ignores=[]), '<actual Config>', 'exec'), namespace)
    tree = ast.parse((ROOT / 'ok/ui/qt/tasks/ConfigLabelAndWidget.py').read_text(encoding='utf-8-sig'))
    update = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
                  and node.name == 'update_config')
    exec(compile(ast.Module(body=[update], type_ignores=[]), '<actual UI setter>', 'exec'), namespace)
    return namespace['Config'], namespace['update_config']


def task_defaults(name):
    tree = ast.parse((ROOT / f'src/task/{name}.py').read_text(encoding='utf-8-sig'))
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == name)
    init = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == '__init__')
    if name == 'FarmEchoTask':
        value = next(node.args[0] for node in ast.walk(init) if isinstance(node, ast.Call)
                     and isinstance(node.func, ast.Attribute) and node.func.attr == 'update'
                     and isinstance(node.func.value, ast.Attribute)
                     and node.func.value.attr == 'default_config')
    else:
        value = next(node.value for node in init.body if isinstance(node, ast.Assign)
                     and isinstance(node.value, ast.Dict)
                     and any((isinstance(target, ast.Name) and target.id == 'default_config')
                             or (isinstance(target, ast.Attribute) and target.attr == 'default_config')
                             for target in node.targets))
    environment = {'self': SimpleNamespace(support_tasks=['Tacet Suppression', 'Forgery Challenge',
                                                         'Simulation Challenge']),
                   'ADDITIONAL_TASKS': 'Additional Tasks to Run After Daily Task',
                   'CHECK_WEEKLY_GARDEN': 'Check Weekly Garden'}
    expression = ast.Expression(body=value)
    permitted = (ast.Expression, ast.Dict, ast.List, ast.Constant, ast.Name,
                 ast.Attribute, ast.Subscript, ast.Load)
    assert all(isinstance(node, permitted) for node in ast.walk(expression))
    return eval(compile(expression, '<actual task defaults>', 'eval'), {'__builtins__': {}}, environment)


def target_keys(defaults):
    return [key for key in defaults if key.startswith('Which ')
            and (' Bar to ' in key or ' in Bar to ' in key)]


def accept_task_config(key, value):
    # Task.validate_config is inherited as a no-op for these four tasks.
    return True, None


def reload_in_child(folder):
    Config, _ = load_config_implementation()
    expected = json.loads((folder / 'expected.json').read_text(encoding='utf-8'))
    for name in TASKS:
        config = Config(name, task_defaults(name), folder=str(folder), validator=accept_task_config)
        assert dict(config) == expected[name], name
    print('Fresh Python process reload: PASS (4 task configs, 14 target fields)')


def main():
    if len(sys.argv) == 3 and sys.argv[1] == '--reload':
        reload_in_child(Path(sys.argv[2]))
        return
    Config, update_config = load_config_implementation()
    expected = {}
    with tempfile.TemporaryDirectory(prefix='ok-ww-new-config-') as folder_name:
        folder = Path(folder_name)
        for name in TASKS:
            defaults = task_defaults(name)
            keys = target_keys(defaults)
            config = Config(name, defaults, folder=folder_name, validator=accept_task_config)
            assert dict(config) == defaults
            for index, key in enumerate(keys):
                value = (3, 2, 5, 4, 2, 6)[index]
                update_config(SimpleNamespace(config=config, key=key), value)
                assert json.loads(Path(config.config_file).read_text(encoding='utf-8'))[key] == value
            saved_targets = {key: config[key] for key in keys}
            selectors = {'FarmEchoTask': ('Teleport to Boss', ['Weekly Challenge', 'Boss Challenge',
                                                             'Special Nightmare', 'No']),
                         'DailyTask': ('Which to Farm', ['Forgery Challenge', 'Simulation Challenge',
                                                       'Tacet Suppression'])}
            if name in selectors:
                selector, options = selectors[name]
                for option in options:
                    update_config(SimpleNamespace(config=config, key=selector), option)
                    assert {key: config[key] for key in keys} == saved_targets
            expected[name] = dict(config)
            for _ in range(3):
                before = Path(config.config_file).read_bytes()
                config = Config(name, defaults, folder=folder_name, validator=accept_task_config)
                assert dict(config) == expected[name]
                assert Path(config.config_file).read_bytes() == before
            print(f'{name}: immediate disk save, option switches, 3 reloads PASS ({len(keys)} fields)')

            personal_path = ROOT / f'configs/{name}.json'
            if personal_path.is_file():
                personal = json.loads(personal_path.read_text(encoding='utf-8'))
                current_targets = {key: personal[key] for key in keys if key in personal}
                assert len(current_targets) == len(keys), name
                personal_copy = folder / 'personal-target-copy'
                personal_copy.mkdir(exist_ok=True)
                (personal_copy / f'{name}.json').write_text(json.dumps(current_targets), encoding='utf-8')
                restored = Config(name, defaults, folder=str(personal_copy), validator=accept_task_config)
                assert {key: restored[key] for key in keys} == current_targets
                print(f'{name}: existing personal target values retained on isolated reload PASS')
        (folder / 'expected.json').write_text(json.dumps(expected), encoding='utf-8')
        subprocess.run([sys.executable, '-B', str(Path(__file__).resolve()), '--reload', folder_name], check=True)
    print('New-scheme persistence PASS; personal configs were not modified.')


if __name__ == '__main__':
    main()
