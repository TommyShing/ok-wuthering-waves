"""Offline handover checks; never import OK, load user config, or send input."""
import ast
import gettext
import io
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]


def extract_definitions(path, names):
    tree = ast.parse(path.read_text(encoding='utf-8-sig'))
    definitions = [node for node in ast.walk(tree)
                   if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names]
    module = ast.Module(body=definitions, type_ignores=[])
    return compile(ast.fix_missing_locations(module), str(path), 'exec')


class Box:
    # Match the framework's pixel rounding without importing its app package.
    def __init__(self, x, y, width, height, confidence=1.0):
        self.x, self.y = int(round(x)), int(round(y))
        self.width, self.height = int(round(width)), int(round(height))
        self.confidence = confidence


sources = [ROOT / name for name in ('config.py', 'main.py', 'main_debug.py')]
sources += sorted((ROOT / 'src').rglob('*.py'))
for path in sources:
    compile(path.read_text(encoding='utf-8-sig'), str(path), 'exec')
print('Syntax OK:', len(sources), 'files')
print('Git HEAD:', subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD'], cwd=ROOT, text=True).strip())

namespace = {'cv2': cv2, 'np': np, 'Box': Box}
exec(extract_definitions(ROOT / 'ok/util/color.py',
                        {'color_range_to_bound', 'find_color_rectangles'}), namespace)
base_tree = ast.parse((ROOT / 'src/task/BaseWWTask.py').read_text(encoding='utf-8'))
for node in base_tree.body:
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name) and (target.id.startswith('BOOK_') or target.id == 'book_bar_color'):
                allowed = (ast.Expression, ast.Constant, ast.BinOp, ast.Div, ast.Dict, ast.Tuple, ast.Load)
                expression = ast.Expression(body=node.value)
                assert all(isinstance(part, allowed) for part in ast.walk(expression)), target.id
                namespace[target.id] = eval(compile(expression, '<numeric constant>', 'eval'), {'__builtins__': {}})
namespace['BaseWWTask'] = type('OfflineTask', (), {
    '_book_arrow_tpl': cv2.imread(str(ROOT / 'assets/images/arrow_expanded_36.png')),
})
assert namespace['BaseWWTask']._book_arrow_tpl is not None
exec(extract_definitions(ROOT / 'src/task/BaseWWTask.py',
                        {'_book_find_arrows', '_book_sliding_block', '_book_bar_is_gold'}), namespace)

samples = [ROOT / 'docs/images' / name for name in (
    'class_1080p_expanded.png', 'class_1440p_collapsed.png',
    'verify_short.png', 'verify_long.png', 'verify_mid.png',
    'verify_bottom.png', 'verify_collapsed.png',
)]
samples += sorted((ROOT / 'screenshots').glob('*_original.png'))
for path in samples:
    frame = cv2.imread(str(path))
    assert frame is not None, path
    h, w = frame.shape[:2]
    fake = SimpleNamespace(box_of_screen=lambda x, y, x1, y1: Box(
        x * w, y * h, (x1 - x) * w, (y1 - y) * h))
    points = namespace['_book_find_arrows'](fake, frame)
    block = namespace['_book_sliding_block'](fake, frame)
    gold = [bool(namespace['_book_bar_is_gold'](fake, frame, point)) for point in points]
    print(json.dumps({'sample': path.name, 'size': [w, h],
                      'arrows': [[int(x), int(y)] for x, y in points],
                      'gold': gold, 'block': block}, ensure_ascii=False))

tpl = namespace['BaseWWTask']._book_arrow_tpl
negative = cv2.imread(str(ROOT / 'docs/images/arrow_collapsed_36.png'))
negative_max = float(cv2.matchTemplate(negative, tpl, cv2.TM_CCOEFF_NORMED).max())
assert negative_max < namespace['BOOK_ARROW_THRESHOLD'], negative_max
print('Collapsed arrow negative score:', round(negative_max, 3))

exec(extract_definitions(ROOT / 'src/task/BaseWWTask.py', {'click_on_book_target'}), namespace)


class NavigationProbe:
    """Record navigation decisions without a window, executor, or input device."""
    def __init__(self, block=(272, 406), height=1080):
        self.frame = np.zeros((height, round(height * 16 / 9), 3), dtype=np.uint8)
        self.block = block
        self.arrow_reads = 0
        self.block_reads = 0
        self.feature_waits = 0
        self.clicks = []
        self.logs = []

    def sleep(self, *args):
        pass

    def next_frame(self):
        pass

    def _book_find_arrows(self, frame):
        self.arrow_reads += 1
        scale = self.frame.shape[0] / 1080
        points = [(1809, 304), (1808, 831)] if self.arrow_reads == 1 else [(1808, 439)]
        return [(x * scale, y * scale) for x, y in points]

    def _book_bar_is_gold(self, *args):
        return False

    def _book_sliding_block(self, frame):
        self.block_reads += 1
        return self.block

    def log_info(self, message):
        self.logs.append(message)

    def click_relative(self, x, y, **kwargs):
        self.clicks.append((float(x), float(y), kwargs.get('name')))

    def wait_feature(self, *args, **kwargs):
        self.feature_waits += 1
        return SimpleNamespace(name='team_close')


for invalid in ((0, 1), (1, 0)):
    probe = NavigationProbe()
    try:
        namespace['click_on_book_target'](probe, *invalid)
    except IndexError:
        assert not probe.clicks
    else:
        raise AssertionError(f'Missing lower bound check for {invalid}')
probe = NavigationProbe()
assert namespace['click_on_book_target'](probe, 3, 2) is True
assert [click[2] for click in probe.clicks] == ['collapse2', 'collapse1', 'challenge']
assert abs(probe.clicks[-1][1] * 1080 - 703) < 1
assert probe.block_reads == 0
print('Mock N=3/M=2: collapse order [2, 1], challenge y=', round(probe.clicks[-1][1] * 1080))
probe = NavigationProbe()
assert namespace['click_on_book_target'](probe, 3, 4) is True
assert len(probe.clicks) == 4 and probe.clicks[-2][2] is None
assert all(0 <= y <= 1 for _, y, _ in probe.clicks)
assert probe.block_reads == 1
print('Mock N=3/M=4: scroll branch used; all coordinates within frame')

# Visible buttons must not depend on detecting a scrollbar, even when the card's
# bottom lies below the viewport. Exercise both supported screenshot scales.
boundary_results = []
for height in (1080, 1440):
    for card_index in (2, 3):
        probe = NavigationProbe(block=None, height=height)
        assert namespace['click_on_book_target'](probe, 3, card_index) is True
        assert probe.block_reads == 0 and probe.feature_waits == 1
        assert [click[2] for click in probe.clicks] == ['collapse2', 'collapse1', 'challenge']
    # Shift the first arrow so a button remains visible while its card bottom
    # extends past the viewport; the decision must use the button coordinate.
    probe = NavigationProbe(block=None, height=height)
    original_arrows = probe._book_find_arrows
    probe._book_find_arrows = lambda frame: [(x, y + 50 * height / 1080)
                                            for x, y in original_arrows(frame)]
    assert namespace['click_on_book_target'](probe, 3, 3) is True
    assert probe.block_reads == 0
    assert probe.clicks[-1][1] < namespace['BOOK_SCROLL_BAR_BOTTOM']
    assert (probe.clicks[-1][1] + namespace['BOOK_CARD_H'] / 2
            > namespace['BOOK_SCROLL_BAR_BOTTOM'])
    print(f'Mock {height}p visible button: no slider lookup, including partially visible card')


def expect_navigation_error(probe, bar_index, card_index, exception_type, message_fragment):
    try:
        namespace['click_on_book_target'](probe, bar_index, card_index)
    except exception_type as error:
        assert message_fragment in str(error), error
        assert not any(name in (None, 'challenge') for _, _, name in probe.clicks)
        assert probe.feature_waits == 0
        return str(error)
    raise AssertionError(f'Missing {exception_type.__name__} for {bar_index}/{card_index}')


for height in (1080, 1440):
    for card_index in (4, 30):
        probe = NavigationProbe(block=None, height=height)
        message = expect_navigation_error(probe, 3, card_index, IndexError, 'no scroll bar found')
        assert probe.block_reads == 1
        boundary_results.append({'case': 'outside_no_slider', 'height': height, 'N': 3,
                                 'M': card_index, 'status': message, 'challenge_y': []})
    scale = height / 1080
    probe = NavigationProbe(block=(272 * scale, 272 * scale + 135 * scale - 1), height=height)
    message = expect_navigation_error(probe, 3, 30, IndexError, 'list end')
    assert probe.block_reads == 1
    boundary_results.append({'case': 'beyond_list_end', 'height': height, 'N': 3,
                             'M': 30, 'status': message, 'challenge_y': []})
    probe = NavigationProbe(block=(272 * scale, 272 * scale + 135 * scale - 1), height=height)
    assert namespace['click_on_book_target'](probe, 3, 4) is True
    assert probe.block_reads == 1
    assert all(0 <= y <= namespace['BOOK_SCROLL_BAR_BOTTOM'] for _, y, name in probe.clicks
               if name in (None, 'challenge'))
print('Mock outside viewport: missing slider / beyond list end raise before scroll or challenge')

# A full-height thumb cannot provide scroll travel.
probe = NavigationProbe(block=(272, namespace['BOOK_SCROLL_BAR_BOTTOM'] * 1080 - 1))
expect_navigation_error(probe, 3, 4, IndexError, 'list end')

# Exhausting the collapse limit must not proceed, but reaching the target on the
# last allowed round must still work.
probe = NavigationProbe()
probe._book_find_arrows = lambda frame: [(1809, 304)]
message = expect_navigation_error(probe, 99, 1, RuntimeError, 'could not reach bar')
assert len(probe.clicks) == namespace['BOOK_COLLAPSE_MAX_ROUNDS']
assert probe.block_reads == 0
boundary_results.append({'case': 'collapse_rounds_exhausted', 'N': 99, 'M': 1,
                         'status': message, 'challenge_y': []})
probe = NavigationProbe()
probe._book_find_arrows = lambda frame: [(1809, 304)]
assert namespace['click_on_book_target'](probe, namespace['BOOK_COLLAPSE_MAX_ROUNDS'] + 1, 1) is True
assert sum(name is not None and name.startswith('collapse') for _, _, name in probe.clicks) == 16
assert probe.clicks[-1][2] == 'challenge'
print('Mock collapse limit: unfinished target rejected; target reached in final round allowed')
(ROOT / '.planning/project-followup/navigation-boundaries-current.json').write_text(
    json.dumps(boundary_results, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

probe = NavigationProbe()
probe._book_find_arrows = lambda frame: []
try:
    namespace['click_on_book_target'](probe, 1, 1)
except IndexError:
    assert not probe.clicks
else:
    raise AssertionError('Missing no-arrow check')
print('Mock lower bounds and no-arrow failure: OK')

farm_tree = ast.parse((ROOT / 'src/task/FarmEchoTask.py').read_text(encoding='utf-8'))
default_call = next(node for node in ast.walk(farm_tree)
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == 'update' and isinstance(node.func.value, ast.Attribute)
                    and node.func.value.attr == 'default_config')
defaults = ast.literal_eval(default_call.args[0])
print('Legacy config migration intentionally omitted per user; '
      'new config persistence is checked by verify_config_persistence.py')

new_keys = [key for key in defaults if ' Bar ' in key]
new_keys += ['Which Tacet Suppression Bar to Farm', 'Which Tacet Suppression in Bar to Farm',
             'Which Forgery Challenge Bar to Farm', 'Which Forgery Challenge in Bar to Farm',
             'Which Bar (from top, starting with 1)',
             'Which Boss inside that Bar (from top, starting with 1)']
for lang in ('zh_CN', 'zh_TW'):
    with (ROOT / f'i18n/{lang}/LC_MESSAGES/ok.mo').open('rb') as stream:
        translation = gettext.GNUTranslations(stream)
    baseline_mo = subprocess.check_output(
        ['git', 'show', f'cdd336c:i18n/{lang}/LC_MESSAGES/ok.mo'], cwd=ROOT)
    backup = gettext.GNUTranslations(io.BytesIO(baseline_mo))
    missing = [key for key in new_keys if translation.gettext(key) == key]
    old_messages = {key: value for key, value in backup._catalog.items() if key}
    lost = [key for key in old_messages if key not in translation._catalog]
    changed = [key for key in old_messages if key in translation._catalog
               and translation._catalog[key] != old_messages[key]]
    assert not missing and not lost and not changed, (lang, missing, lost, changed)
    print(json.dumps({'lang': lang, 'old_messages': len(backup._catalog),
                      'new_messages': len(translation._catalog), 'new_keys_checked': len(new_keys),
                      'missing': missing, 'lost': lost, 'changed': changed}, ensure_ascii=False))

    # These catalogs contain simple singular messages; parse continuations with
    # Python's string literal decoder to independently compare the saved PO/MO.
    po_messages = {}
    current = {}
    field = None
    for line in (ROOT / f'i18n/{lang}/LC_MESSAGES/ok.po').read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if line.startswith('msgid '):
            if current:
                po_messages[current['id']] = current.get('str', '')
            current = {'id': ast.literal_eval(line[6:])}
            field = 'id'
        elif line.startswith('msgstr '):
            current['str'] = ast.literal_eval(line[7:])
            field = 'str'
        elif line.startswith('"'):
            current[field] += ast.literal_eval(line)
        elif line and not line.startswith('#'):
            raise ValueError(f'Unsupported PO syntax: {line}')
    if current:
        po_messages[current['id']] = current.get('str', '')
    mismatches = [key for key, value in po_messages.items() if key
                  and translation._catalog.get(key) != value]
    extra = [key for key in translation._catalog if key and key not in po_messages]
    assert not mismatches and not extra, (lang, mismatches, extra)
    print('PO/MO matching messages:', lang, len(po_messages) - 1)

print('Offline checks completed; single-bar card limits remain outside the supported checks.')
