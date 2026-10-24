import unittest
from unittest.mock import Mock, PropertyMock, patch

from ok.feature.Box import Box

from src.task.BaseWWTask import (BOOK_BAR_H, BOOK_CARD_H, BOOK_GAP_BAR_CARD, BOOK_GAP_CARD_CARD,
                                 BOOK_GAP_LIST_TOP_BAR, BOOK_SCROLL_BAR_BOTTOM, BaseWWTask)

WIDTH, HEIGHT = 1920, 1080
BUTTON = Box(1760, 600, 40, 40)
LIST_TOP = 202 / HEIGHT
CONFIRM = Box(1400, 660, 60, 80)


class Screen:
    """A fake screen name, so the production `feature.name` check reads a real string."""

    def __init__(self, name):
        self.name = name


def arrow(y_center):
    """An expanded-arrow box whose centre sits at `y_center` pixels."""
    return Box(1791, y_center - 18, 36, 36)


def make_task(arrows, button=True):
    """A 1080p task showing `arrows` top to bottom.

    Clicking a bar collapses it, so the mock drops that bar's up arrow; that is what lets the
    production loop tell a real collapse from a click that did nothing.
    """
    task = BaseWWTask.__new__(BaseWWTask)
    task.info = {}
    task.clicks = []
    task.bar_clicks = []
    task.logs = []
    task.collapsed = 0

    task._book_find_arrows = lambda _frame: list(arrows[task.collapsed:])
    task._book_sliding_block = lambda _frame: None
    task._book_bar_is_gold = lambda _frame, _arrow: False
    task.find_one = lambda name, **kwargs: BUTTON if button else None
    task.next_frame = Mock()
    task.sleep = Mock()
    task.log_info = lambda message, **kwargs: task.logs.append(message)

    def click(*args, **kwargs):
        target = args[0]
        if target in arrows:
            task.collapsed += 1
            task.bar_clicks.append(target)
        # Keep the whole call so a scroll click stays readable as (x, y).
        task.clicks.append(tuple(args))

    task.click = click
    task.box_of_screen = lambda x, y, w, h: Box(int(x * WIDTH), int(y * HEIGHT),
                                                int((w - x) * WIDTH), int((h - y) * HEIGHT))
    task.wait_feature = lambda *a, **k: Screen('gray_teleport')
    return task


class TestBookTarget(unittest.TestCase):

    def setUp(self):
        # height, width and frame are read-only properties on the executor, so stub them out for
        # the whole test instead of assigning them on the instance.
        self._patches = [patch.object(BaseWWTask, 'height', new_callable=PropertyMock, return_value=HEIGHT),
                         patch.object(BaseWWTask, 'width', new_callable=PropertyMock, return_value=WIDTH),
                         patch.object(BaseWWTask, 'frame', new_callable=PropertyMock, return_value=None)]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in self._patches:
            p.stop()

    def card_log(self, task):
        """The card-bottom value the production code logged for the target card."""
        line = [m for m in task.logs if m.startswith('card bottom=')][0]
        return float(line.split()[1].split('=')[1])

    def test_first_bar_first_card_needs_no_collapse_and_no_scroll(self):
        task = make_task([arrow(231), arrow(500), arrow(700)])

        task.click_on_book_target(1, 1)

        self.assertEqual([], task.bar_clicks)
        self.assertEqual([(BUTTON,)], task.clicks)
        self.assertTrue(any('no scroll' in m for m in task.logs))

    def test_third_bar_collapses_the_two_bars_above_it_bottom_up(self):
        task = make_task([arrow(300), arrow(400), arrow(500)])

        task.click_on_book_target(3, 1)

        # Lower one first, so neither click shifts the other before it is clicked.
        self.assertEqual([arrow(400), arrow(300)], task.bar_clicks)
        self.assertEqual((BUTTON,), task.clicks[-1])

    def test_card_one_sits_right_under_the_target_bar(self):
        bar_top = LIST_TOP + BOOK_GAP_LIST_TOP_BAR
        task = make_task([arrow(int((bar_top + BOOK_BAR_H / 2) * HEIGHT))])

        task.click_on_book_target(1, 1)

        card_bottom = bar_top + BOOK_BAR_H + BOOK_GAP_BAR_CARD + BOOK_CARD_H
        self.assertAlmostEqual(card_bottom, self.card_log(task), delta=0.002)

    def test_second_card_is_one_card_pitch_lower(self):
        bar_top = LIST_TOP + BOOK_GAP_LIST_TOP_BAR
        task = make_task([arrow(int((bar_top + BOOK_BAR_H / 2) * HEIGHT))])

        task.click_on_book_target(1, 2)

        card_bottom = (bar_top + BOOK_BAR_H + BOOK_GAP_BAR_CARD + BOOK_CARD_H
                       + BOOK_GAP_CARD_CARD + BOOK_CARD_H)
        self.assertAlmostEqual(card_bottom, self.card_log(task), delta=0.002)

    def test_card_past_the_view_bottom_scrolls_the_thumb_by_its_own_fraction(self):
        task = make_task([arrow(int((LIST_TOP + BOOK_GAP_LIST_TOP_BAR + BOOK_BAR_H / 2) * HEIGHT))])
        task._book_sliding_block = lambda _frame: (0.25, 0.46)

        task.click_on_book_target(1, 6)

        bar_top = LIST_TOP + BOOK_GAP_LIST_TOP_BAR
        card_bottom = (bar_top + BOOK_BAR_H + BOOK_GAP_BAR_CARD
                       + 5 * (BOOK_CARD_H + BOOK_GAP_CARD_CARD) + BOOK_CARD_H)
        advance = (card_bottom - BOOK_SCROLL_BAR_BOTTOM) * (0.46 - 0.25) / (BOOK_SCROLL_BAR_BOTTOM - LIST_TOP)
        scroll_x, scroll_y = task.clicks[0]
        self.assertEqual(0.973, scroll_x)
        self.assertAlmostEqual(0.46 + advance, scroll_y, places=3)
        self.assertEqual((BUTTON,), task.clicks[-1])

    def test_card_past_the_end_of_the_list_raises_instead_of_clicking(self):
        task = make_task([arrow(int((LIST_TOP + BOOK_GAP_LIST_TOP_BAR + BOOK_BAR_H / 2) * HEIGHT))])
        task._book_sliding_block = lambda _frame: (0.25, BOOK_SCROLL_BAR_BOTTOM)

        with self.assertRaises(IndexError):
            task.click_on_book_target(1, 9)

        self.assertNotIn((BUTTON,), task.clicks)

    def test_card_past_the_view_bottom_without_a_scroll_bar_raises(self):
        task = make_task([arrow(int((LIST_TOP + BOOK_GAP_LIST_TOP_BAR + BOOK_BAR_H / 2) * HEIGHT))])

        with self.assertRaises(IndexError):
            task.click_on_book_target(1, 9)

        self.assertNotIn((BUTTON,), task.clicks)

    def test_no_arrow_raises(self):
        task = make_task([])

        with self.assertRaises(IndexError):
            task.click_on_book_target(1, 1)

    def test_bar_index_past_the_arrow_count_raises(self):
        # Only one bar on screen, so asking for the third cannot be satisfied.
        task = make_task([arrow(300)])

        with self.assertRaises(IndexError):
            task.click_on_book_target(3, 1)

        self.assertNotIn((BUTTON,), task.clicks)

    def test_missing_challenge_button_raises_instead_of_clicking_blind(self):
        task = make_task([arrow(231)], button=False)

        with self.assertRaises(IndexError):
            task.click_on_book_target(1, 1)

        self.assertEqual([], task.clicks)

    def test_zero_index_is_rejected(self):
        task = make_task([arrow(231)])

        with self.assertRaises(IndexError):
            task.click_on_book_target(0, 1)

    def test_team_screen_result_is_reported(self):
        task = make_task([arrow(231)])
        task.wait_feature = lambda *a, **k: Screen('team_close')

        self.assertTrue(task.click_on_book_target(1, 1))

    def test_world_screen_result_is_reported(self):
        task = make_task([arrow(231)])
        task.wait_feature = lambda *a, **k: Screen('gray_teleport')

        self.assertFalse(task.click_on_book_target(1, 1))

    def test_gold_bar_answers_the_early_access_warning(self):
        task = make_task([arrow(231)])
        task._book_bar_is_gold = lambda _frame, _arrow: True
        task.wait_feature = Mock(return_value=CONFIRM)

        task.click_on_book_target(1, 1)

        self.assertEqual([(BUTTON,), (CONFIRM,)], task.clicks)
        self.assertTrue(any('GOLD' in m for m in task.logs))

    def test_normal_bar_does_not_look_for_a_warning(self):
        task = make_task([arrow(231)])
        task.wait_feature = Mock(return_value=Screen('gray_teleport'))

        task.click_on_book_target(1, 1)

        # Only the final "which screen opened" wait, not the confirm-dialog probe.
        self.assertEqual(1, task.wait_feature.call_count)


if __name__ == '__main__':
    unittest.main()
