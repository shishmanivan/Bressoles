import json
import os
from pathlib import Path
from string import Formatter
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')
import pygame
import game_state
from gameplay_page import GameplayPage
from localization import SUPPORTED_LANGUAGES, get_language, set_language
from newspaper_report import articles, catalog, text, wrap_lines, summarize_round_rolls


def make_page():
    page = GameplayPage.__new__(GameplayPage)
    page.screen = pygame.Surface((1680, 1050))
    page.level_number, page.round_num, page.Day = 3, 2, 1
    page.Money, page.Aprice, page.BPrice, page.CPrice = 125, 12, 20, 27
    page.newspaper_opening = {'coins': 10, 'prices': [10, 20, 30]}
    page.newspaper_events = []
    page.win_lose_state, page.result_report_stage = 'win', 'newspaper'
    page.finance_report_entries = [{'source': 'victory_reward', 'label': 'Награда за победу', 'amount': 7}]
    page.last_earned_cards = [11, 15]
    page.frugality_bonus_turns = 0
    page.is_final_boss = False
    page.blocked_reward_cards = []
    page._save_active_game = Mock()
    page._play_result_report_rustle = Mock()
    return page


class NewspaperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.font.init()

    def setUp(self):
        language = get_language()
        self.addCleanup(set_language, language)
        set_language('RU')

    def test_turn_journal_is_factual_idempotent_and_json_serializable(self):
        page = make_page()
        with patch.object(game_state, 'napoleondors', 13):
            page._capture_newspaper_turn()
            page._capture_newspaper_turn()
            self.assertEqual(len(page.newspaper_events), 1)
            event = page.newspaper_events[0]
            self.assertEqual(event['change'], 3)
            self.assertEqual(event['before_prices'], [10, 20, 30])
            page.Money = 140
            page._capture_newspaper_turn(final=True)
            self.assertEqual(event['cash'], 140)
            self.assertEqual(len(page.newspaper_events), 1)
            finance, cards, market = articles(page)
        self.assertIn('140', ' '.join(finance))
        self.assertIn('повысилась с 10 до 12', ' '.join(market))
        self.assertIn('не изменилась', ' '.join(market))
        self.assertIn('снизилась с 30 до 27', ' '.join(market))
        self.assertIn('раунда 2', ' '.join(cards))
        self.assertEqual(json.loads(json.dumps(page.newspaper_events)), page.newspaper_events)

    def test_roll_journal_preserves_sample_without_random_calls(self):
        page = make_page()
        roll = dict(market=0, outcome='rise', random_value=24.5,
                    probabilities=dict(rise=30, fall=30, flat=40))
        with patch('random.random', side_effect=AssertionError('Reports cannot reroll')):
            page._newspaper_event('roll', **roll)
            roll['probabilities']['rise'] = 99
            value = ' '.join(articles(page, detailed=True)[2])
        self.assertIn('24.5', value)
        self.assertIn('30%', value)
        self.assertNotIn('99%', value)

    def test_income_article_uses_actual_source_deltas_not_carried_income(self):
        page = make_page()
        page.newspaper_opening['income_sources'] = {'sideway': 5}
        income = [{'source': 'sideway', 'amount': 8}]
        with patch.object(game_state, 'pending_finance_report_entries', income):
            page._capture_newspaper_turn()
            self.assertEqual(page.newspaper_events[-1]['income'], [{'source': 'sideway', 'amount': 3}])
            page.Day = 2
            income[0]['amount'] = 12
            page._capture_newspaper_turn()
            self.assertEqual(page.newspaper_events[-1]['income'], [{'source': 'sideway', 'amount': 4}])
            prose = ' '.join(articles(page)[0])
        self.assertIn('На ходу 1 игрок получил 3 наполеондоров благодаря Sideway.', prose)
        self.assertIn('На ходу 2 игрок получил 4 наполеондоров благодаря Sideway.', prose)

    def test_each_detail_button_opens_and_back_returns_for_both_results(self):
        page = make_page()
        page.finance_report_image = pygame.Surface((600, 800))
        page.card_report_image = page.finance_report_image
        for outcome in ('win', 'lose'):
            page.win_lose_state = outcome
            targets = ('finance', 'card_report', 'market_report') if outcome == 'win' else ('market_report',)
            self.assertEqual(set(page._newspaper_button_layout()), {*targets, 'continue'})
            for target in targets:
                page.result_report_stage = 'newspaper'
                page.newspaper_y = 12
                page.newspaper_closing = False
                page.finance_stamp_state = 'idle'
                event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1,
                                           pos=page._newspaper_button_layout()[target].center)
                self.assertIsNone(page._handle_newspaper_input(event))
                self.assertEqual(page.result_report_stage, target)
                self.assertGreater(page.finance_report_y, page.screen.get_height())
                page.finance_report_y = (page.screen.get_height()-page.finance_report_image.get_height())//2
                page.finance_stamp_rect = pygame.Rect(900, 800, 100, 50)
                close = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=page.finance_stamp_rect.center)
                page._handle_newspaper_input(close)
                self.assertEqual(page.finance_stamp_state, 'pressing')
                page.finance_stamp_state = 'closing'
                page.finance_report_y = -page.finance_report_image.get_height()-30
                page.update_win_lose_animation()
                self.assertEqual(page.result_report_stage, 'newspaper')
                self.assertEqual(page.newspaper_y, 12)
            finish = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1,
                                       pos=page._newspaper_button_layout()['continue'].center)
            self.assertIsNone(page._handle_newspaper_input(finish))
            self.assertEqual(page.finance_stamp_state, 'pressing')
            self.assertFalse(page.newspaper_closing)
            for phase, elapsed in [('pressing', 180), ('flying', 310), ('stamped', 370)]:
                page.finance_stamp_state = phase
                page.finance_stamp_started_at = 1000-elapsed
                with patch('newspaper_report.pygame.time.get_ticks', return_value=1000):
                    page._update_newspaper_animation(0)
            self.assertTrue(page.newspaper_closing)
            page._update_newspaper_animation(1)
            self.assertEqual(page.result_transition_ready, 'round_select' if outcome == 'win' else 'level_select')

    def test_details_are_drawn_over_stationary_newspaper_and_stamp_sits_above_button(self):
        page = make_page()
        page.newspaper_y = 12
        calls = Mock()
        page._draw_newspaper = calls.newspaper
        page._draw_newspaper_detail = calls.detail
        for stage in ('finance', 'card_report', 'market_report'):
            page.result_report_stage = stage
            calls.reset_mock()
            page._draw_gameplay_overlays()
            self.assertEqual(calls.mock_calls, [unittest.mock.call.newspaper(active=False),
                                               unittest.mock.call.detail()])
            self.assertEqual(page.newspaper_y, 12)
        buttons = page._newspaper_button_layout()
        self.assertLess(buttons['continue'].bottom, buttons['market_report'].top)
        self.assertEqual(buttons['continue'].centerx, buttons['market_report'].centerx)

    def test_newspaper_enters_from_above_and_ignores_clicks_during_slide(self):
        page = make_page()
        page._start_newspaper_entrance()
        first = page.newspaper_y
        event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1,
                                   pos=page._newspaper_button_layout()['continue'].center)
        page._handle_newspaper_input(event)
        self.assertFalse(page.newspaper_closing)
        page._update_newspaper_animation(.1)
        self.assertGreater(page.newspaper_y, first)
        self.assertLess(page.newspaper_y, 12)
        page._update_newspaper_animation(1)
        self.assertEqual(page.newspaper_y, 12)

    def test_expected_percent_averages_the_probabilities_at_each_roll(self):
        page = make_page()
        page._newspaper_event('roll', market=0, outcome='rise', random_value=10,
                              probabilities=dict(rise=20, fall=30, flat=50))
        page._newspaper_event('roll', market=0, outcome='fall', random_value=90,
                              probabilities=dict(rise=80, fall=10, flat=10))
        summary = summarize_round_rolls(page.newspaper_events)
        self.assertEqual(summary['A']['rolls'], 2)
        self.assertEqual(summary['A']['outcomes']['rise'],
                         {'count': 1, 'expected_count': 1, 'actual_percent': 50, 'expected_percent': 50})
        self.assertAlmostEqual(summary['A']['outcomes']['fall']['expected_count'], .4)
        self.assertAlmostEqual(summary['A']['outcomes']['flat']['expected_count'], .6)
        self.assertAlmostEqual(sum(item['expected_count'] for item in summary['A']['outcomes'].values()), 2)
        self.assertEqual(summary['A']['outcomes']['fall']['expected_percent'], 20)
        self.assertEqual(summary['A']['outcomes']['flat']['expected_percent'], 30)
        self.assertEqual(summary['B']['rolls'], 0)
        self.assertIsNone(summary['B']['outcomes']['rise']['actual_percent'])
        self.assertIsNone(summary['B']['outcomes']['rise']['expected_percent'])

    def test_run_counts_span_rounds_survive_serialization_and_reset(self):
        import profile_manager
        page = make_page()
        roll = dict(market=0, outcome='rise', probabilities=dict(rise=25, fall=25, flat=50))
        with patch.object(game_state, 'boss_progress', {}):
            page._record_run_market_rolls([roll])
            restored = profile_manager._restore_boss_progress(
                json.loads(json.dumps(profile_manager._serialize_boss_progress(game_state.boss_progress))))
            game_state.boss_progress = restored
            next_round = make_page()
            next_round._record_run_market_rolls([roll])
            next_round.market_report_scope = 'run'
            summary = next_round._market_report_summary()
            self.assertEqual(summary['A']['rolls'], 2)
            self.assertEqual(summary['A']['outcomes']['rise']['expected_count'], .5)
            self.assertEqual(next_round._market_report_summary(), summary)
            game_state.boss_progress[3] = game_state.new_boss_progress_state()
            fresh_run = make_page()
            fresh_run._record_run_market_rolls([roll])
            fresh_run.market_report_scope = 'run'
            self.assertEqual(fresh_run._market_report_summary()['A']['rolls'], 1)
            self.assertEqual(next_round._market_report_summary()['A']['rolls'], 2)

    def test_scope_tabs_switch_without_starting_stamp(self):
        from player_market_stats import empty_stats, accumulate
        page = make_page()
        page.result_report_stage = 'market_report'
        page.market_report_image = pygame.Surface((1323, 882))
        page.finance_report_y = 84
        page.finance_stamp_state = 'idle'
        page.run_market_roll_stats = empty_stats()
        accumulate(page.run_market_roll_stats,
                   [dict(market=1, outcome='flat', probabilities=dict(rise=20, fall=30, flat=50))], (0, 0, 0))
        page._lifetime_market_report_stats = None
        rect = page.market_report_image.get_rect(center=(840, 525))
        for scope in ('run', 'lifetime', 'round'):
            page._handle_newspaper_input(pygame.event.Event(
                pygame.MOUSEBUTTONDOWN, button=1, pos=page._market_report_tabs(rect)[scope].center))
            self.assertEqual(page.market_report_scope, scope)
            self.assertEqual(page.finance_stamp_state, 'idle')
            page._draw_market_report_rows(rect)
            summary = page._market_report_summary()
            if scope == 'lifetime':
                self.assertIsNone(summary)
            else:
                self.assertEqual(summary['B']['rolls'], 1 if scope == 'run' else 0)

    def test_other_tab_renders_two_statistic_periods_and_legacy_notice(self):
        from player_other_stats import empty_stats, record
        page = make_page()
        page.result_report_stage = 'market_report'
        page.market_report_image = pygame.Surface((1323, 882))
        page.finance_report_y = 84
        page.finance_stamp_state = 'idle'
        rect = page.market_report_image.get_rect(center=(840, 525))
        page._handle_newspaper_input(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=1, pos=page._market_report_tabs(rect)['other'].center))
        self.assertEqual(page.market_report_scope, 'other')
        for language in SUPPORTED_LANGUAGES:
            set_language(language)
            page.other_stats_run = page.other_stats_lifetime = None
            page._draw_market_report_rows(rect)
            stats = empty_stats()
            record(stats, 'round', 25, earned=1234,
                   label=dict(level=3, round=2, boss=False, boss_number=None))
            page.other_stats_run = page.other_stats_lifetime = stats
            page._draw_market_report_rows(rect)

    def test_languages_have_matching_placeholders_and_render_both_results(self):
        reference = catalog()['RU']
        fields = lambda value: {key for _, key, _, _ in Formatter().parse(value) if key}
        page = make_page()
        page.newspaper_report_image = pygame.image.load(str(Path(__file__).resolve().parents[1] / 'Arts' / 'BressolesNewspaperTemplate-v3.png'))
        with patch.object(game_state, 'napoleondors', 13):
            for day in range(1, 9):
                page.Day = day
                page._capture_newspaper_turn()
            for language in SUPPORTED_LANGUAGES:
                set_language(language)
                self.assertEqual(set(catalog()[language]), set(reference))
                for key in reference:
                    self.assertEqual(fields(reference[key]), fields(catalog()[language][key]))
                for outcome in ('win', 'lose'):
                    page.win_lose_state = outcome
                    page._draw_newspaper()
                    page._draw_market_report_rows(page._newspaper_target_rect())
                    rect = page._newspaper_rect()
                    for button in page._newspaper_button_layout().values():
                        self.assertTrue(page.screen.get_rect().contains(button))
                    self.assertLess(rect.bottom, page.screen.get_height())

    def test_legacy_missing_history_is_not_invented(self):
        page = make_page()
        page.newspaper_events = []
        page.last_earned_cards = []
        page.win_lose_state = 'lose'
        finance, cards, market = articles(page)
        self.assertIn(text('legacy'), finance)
        self.assertIn(text('legacy'), market)
        self.assertIn(text('no_rewards'), cards)

    def test_long_card_name_cannot_overflow_column(self):
        page = make_page()
        font = page._newspaper_font(12)
        lines = wrap_lines('A' * 400, font, 170)
        self.assertTrue(all(font.size(line)[0] <= 170 for line in lines))


if __name__ == '__main__':
    unittest.main()
