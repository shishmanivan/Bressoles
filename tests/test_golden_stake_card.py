import os
import unittest
from types import SimpleNamespace
from unittest import mock

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import game_state
import localization
import profile_manager
from gameplay_page import GameplayPage
from gameplay_winlose import apply_win_reward
from shop_page import CARD_DESCRIPTIONS, CARD_NAMES
from silver_black_page import CARD_TOOLTIPS


class GoldenStakeTests(unittest.TestCase):
    def setUp(self):
        self.progress = profile_manager._capture_progress()
        game_state.golden_stake_shareholder_parity = 0

    def tearDown(self):
        profile = profile_manager._default_profile(1)
        profile["progress"] = self.progress
        profile_manager.apply_profile_to_game_state(profile)

    def reward(self, cards, gold=(436,), silver=()):
        page = SimpleNamespace(is_boss_fight=False, level_number=5,
                               round_num=1, difficulty="e", last_earned_cards=[],
                               active_gold_cards=list(gold), active_silver_cards=list(silver))
        rewards = {(5, 1, "E"): {f"reward{i}": [card] for i, card in enumerate(cards, 1)}}
        earned = {}
        apply_win_reward(page, earned, rewards, -999, mock.Mock(), mock.Mock(),
                         mock.Mock(), mock.Mock(), mock.Mock())
        self.last_reward_page = page
        self.assertEqual(earned[5], page.last_earned_cards)
        return page.last_earned_cards

    def test_report_keeps_blocked_rewards_in_order_without_adding_them_to_deck(self):
        for silver, expected, blockers in [((205,), [100, 11, 100], [205, None, 205]),
                                           ((), [100, 11, 100], [None, None, 436])]:
            game_state.golden_stake_shareholder_parity = 0
            self.reward([100, 11, 100], silver=silver)
            page = GameplayPage.__new__(GameplayPage)
            page.level_number = 5
            page.last_earned_cards = self.last_reward_page.last_earned_cards
            page.blocked_reward_cards = self.last_reward_page.blocked_reward_cards
            page._get_text = lambda key, default: default
            rows = page._get_card_report_rows()
            self.assertEqual([row["card_id"] for row in rows], expected)
            self.assertEqual([row.get("blocked_by") for row in rows], blockers)
            for row in rows:
                if row.get("blocked_by"):
                    self.assertIn("не попал в колоду", row["label"])

    def test_report_handles_only_blocked_cards_and_old_saves(self):
        self.reward([100, 100], silver=(205,))
        page = GameplayPage.__new__(GameplayPage)
        page.level_number = 5
        page.last_earned_cards = []
        page.blocked_reward_cards = self.last_reward_page.blocked_reward_cards
        rows = page._get_card_report_rows()
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(row["blocked_by"] == 205 for row in rows))
        del page.blocked_reward_cards
        self.assertEqual(page._get_card_report_rows(), [])

    def test_report_crosses_out_blocked_card_and_hover_preview(self):
        import pygame
        pygame.font.init()
        page = GameplayPage.__new__(GameplayPage)
        page.screen = pygame.Surface((850, 1000))
        page.font_path = None
        page._get_text = lambda key, default: default
        page._get_card_report_rows = lambda: [
            {"card_id": 100, "blocked_by": 205, "label": "Blocked Shareholder"},
            {"card_id": 11, "label": "Accepted card"},
        ]
        page._load_winlose_card = lambda card, width: pygame.Surface((width, int(width * 171 / 99)))
        page._draw_negative_card_overlay = mock.Mock()
        report = pygame.Rect(110, 60, 630, 840)
        with mock.patch("pygame.mouse.get_pos", return_value=(200, 430)):
            page._draw_card_report_rows(report)
        self.assertEqual(page._draw_negative_card_overlay.call_count, 2)
        base, hover = page._draw_negative_card_overlay.call_args_list
        self.assertGreater(hover.args[2][0], base.args[2][0])
        self.assertEqual(page.card_report_tooltip[0], 100)

    def test_pairs_within_and_between_rounds(self):
        self.assertEqual(self.reward([100, 100]), [100])
        self.assertEqual(self.reward([100]), [100])
        self.assertEqual(self.reward([100]), [])
        self.assertEqual(self.reward([100, 11, 100]), [100, 11])

    def test_silver_blocks_all_shareholders_only_in_its_active_round(self):
        self.assertEqual(self.reward([100, 11, 0], gold=(), silver=(205,)), [11])
        self.assertEqual(self.reward([100, 100], gold=()), [100, 100])

    def test_silver_takes_priority_without_advancing_gold_counter(self):
        self.assertEqual(self.reward([100]), [100])
        self.assertEqual(self.reward([100, 100], silver=(205,)), [])
        self.assertEqual(self.reward([100]), [])

    def test_silver_descriptions_and_translations_match(self):
        from shop_page import LICENSE_EFFECT_DESCRIPTIONS
        description = CARD_DESCRIPTIONS[205]
        self.assertEqual(CARD_TOOLTIPS[205][1], description)
        self.assertEqual(LICENSE_EFFECT_DESCRIPTIONS[205], description)
        for language in localization.SUPPORTED_LANGUAGES:
            catalog, _, _ = localization._catalog(language)
            self.assertIn("Actionnaire" if language == "FR" else "Shareholder", catalog[description])
            if language != "RU":
                self.assertNotEqual(catalog[description], description)

    def test_inactive_rounds_and_other_cards_do_not_advance_counter(self):
        self.assertEqual(self.reward([100]), [100])
        self.assertEqual(self.reward([100, 100], gold=()), [100, 100])
        self.assertEqual(self.reward([11]), [11])
        self.assertEqual(self.reward([100]), [])

    def test_legacy_shareholder_and_duplicate_stakes(self):
        self.assertEqual(self.reward([0, 0], gold=(436, 436)), [100])

    def test_profile_roundtrip_preserves_pending_block_and_old_profiles_default(self):
        self.reward([100])
        profile = profile_manager._default_profile(1)
        profile["progress"] = profile_manager._capture_progress()
        game_state.golden_stake_shareholder_parity = 0
        profile_manager.apply_profile_to_game_state(profile)
        self.assertEqual(self.reward([100]), [])
        del profile["progress"]["golden_stake_shareholder_parity"]
        profile_manager.apply_profile_to_game_state(profile)
        self.assertEqual(self.reward([100]), [100])

    def test_run_reset_clears_counter_even_when_gold_is_preserved(self):
        self.reward([100])
        game_state.clear_gold_cards()
        self.assertEqual(self.reward([100]), [100])
        game_state.capital_preservation_bought = True
        game_state.consume_capital_preservation()
        self.assertEqual(self.reward([100]), [100])

    def test_gold_and_silver_stakes_prevent_shareholder_shutdown(self):
        for silver, gold, protected in [([], [436], True), ([205], [], True),
                                         ([205], [436], True), ([], [], False)]:
            with self.subTest(silver=silver, gold=gold):
                page = GameplayPage.__new__(GameplayPage)
                page.active_silver_cards = silver
                page.active_gold_cards = gold
                page.level_number = 5
                page.Day = 1
                page.win_lose_state = None
                page.shareholder_effect_count = 10
                page.shareholder_blocked_market = 1
                page._start_shareholder_jump_animations = mock.Mock()
                self.assertEqual(page._has_controlling_stake(), protected)
                with mock.patch("gameplay_page.random.random", return_value=0), \
                     mock.patch("gameplay_page.random.choice", return_value=1):
                    self.assertEqual(page._roll_shareholder_market_shutdown(), None if protected else 1)

    def test_price_level_chance_and_localization(self):
        self.assertEqual(game_state.SHOP_CARD_COSTS[436], 5)
        self.assertEqual(CARD_NAMES[436], "Golden Stake")
        cards = {436: game_state.load_cards_config()[436]}
        self.assertEqual(cards[436], {"Type": 5, "Open": 1, "Variable": "15"})
        with mock.patch.object(game_state, "load_cards_config", return_value=cards):
            with mock.patch.object(game_state.random, "randint", return_value=15) as roll:
                self.assertEqual(game_state.build_gold_cards_pool(4), [])
                roll.assert_not_called()
                self.assertEqual(game_state.build_gold_cards_pool(5), [436])
            with mock.patch.object(game_state.random, "randint", return_value=16):
                self.assertEqual(game_state.build_gold_cards_pool(5), [])
            self.assertNotIn(436, game_state.build_all_available_shop_cards(4))
            self.assertIn(436, game_state.build_all_available_shop_cards(5))
        description = CARD_DESCRIPTIONS[436]
        self.assertEqual(CARD_TOOLTIPS[436], ("Golden Stake", description))
        for language in localization.SUPPORTED_LANGUAGES:
            catalog, _, _ = localization._catalog(language)
            self.assertIn("Actionnaire" if language == "FR" else "Shareholder", catalog[description])
            if language != "RU":
                self.assertNotEqual(catalog[description], description)
