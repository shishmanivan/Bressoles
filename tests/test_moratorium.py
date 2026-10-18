import ast
import csv
from pathlib import Path
import unittest
from unittest import mock

import game_state
import profile_manager
from shop_page import ShopPage


class MoratoriumTests(unittest.TestCase):
    def test_offer_status_uses_runs_in_every_language(self):
        from gameplay_collection_views import offer_status

        root = Path(__file__).resolve().parents[1]
        with (root / "Lang.csv").open(encoding="utf-8-sig", newline="") as source:
            rows = list(csv.reader(source, delimiter=";"))
        translations = next(row for row in rows if row[0] == "OfferRunsLeft")
        for text in translations[1:]:
            page = mock.Mock()
            page._get_text.return_value = text
            status = offer_status(page, {"remaining": 17, "remaining_kind": "runs"})
            page._get_text.assert_called_once_with("OfferRunsLeft", "Осталось забегов: {count}")
            self.assertEqual(status, text.format(count=17))
        self.assertEqual(translations[2], "{count} runs remaining")

    def test_run_start_counts_once_and_rounds_and_reload_do_not_reduce_duration(self):
        # Exercise the actual nested run-start hook without launching the UI loop.
        root = Path(__file__).resolve().parents[1]
        tree = ast.parse((root / "main.py").read_text(encoding="utf-8-sig"))
        hook = next(node for node in ast.walk(tree)
                    if isinstance(node, ast.FunctionDef) and node.name == "mark_level_run_started")
        scope = {"test_mode": False, "selected_slot": 1, "game_state": game_state,
                 "update_level_run_started": mock.Mock()}
        exec(compile(ast.Module(body=[hook], type_ignores=[]), "main.py", "exec"), scope)
        start = scope["mark_level_run_started"]
        self.assertTrue(game_state.buy_moratorium(401, 5))
        for _ in range(4):
            start({}, 5)
        self.assertEqual(game_state.get_active_moratoriums()[401], 17)
        current_run = {"run_stats_started": True}
        for _ in range(25):
            game_state.advance_bailout_round()
            game_state.advance_disclosure_round()
            game_state.advance_price_support_round()
            start(current_run, 5)
            profile_manager.apply_profile_to_game_state({"progress": profile_manager._capture_progress()})
        self.assertEqual(game_state.get_active_moratoriums()[401], 17)
        self.assertNotIn(401, game_state.build_open_gold_cards_pool(5))
        start({}, 5)
        self.assertEqual(game_state.get_active_moratoriums()[401], 16)

    def setUp(self):
        self.progress = profile_manager._capture_progress()
        game_state.seen_gold_card_ids = set(range(401, 416))
        game_state.moratorium_expirations = {}
        game_state.moratorium_run_number = 7
        game_state.gold_cards = []
        game_state.shop_deck_cards = []

    def tearDown(self):
        profile_manager.apply_profile_to_game_state({"progress": self.progress})

    def test_blocks_twenty_subsequent_runs_and_survives_resets_and_reload(self):
        self.assertTrue(game_state.buy_moratorium(401, 5))
        game_state.reset_level_attempt(5)
        profile_manager.apply_profile_to_game_state({"progress": profile_manager._capture_progress()})
        for run in range(1, 21):
            game_state.advance_moratorium_run()
            self.assertIn(401, game_state.get_active_moratoriums())
            self.assertNotIn(401, game_state.build_open_gold_cards_pool(5))
            self.assertNotIn(401, game_state.build_multibagger_gold_fallback_pool(5))
            self.assertNotIn(401, game_state.build_all_available_shop_cards(5))
            self.assertIsNone(game_state.add_gold_card(401))
        game_state.advance_moratorium_run()
        self.assertIn(401, game_state.build_open_gold_cards_pool(5))
        self.assertTrue(game_state.is_moratorium_offer_available(5))

    def test_candidates_limits_and_pool_probability(self):
        self.assertFalse(game_state.buy_moratorium(401, 4))
        self.assertFalse(game_state.buy_moratorium(420, 5))
        for roll, expected in ((10, True), (11, False)):
            with mock.patch.object(game_state.random, "randint", return_value=roll):
                pool = game_state.build_shop_special_offer_pool(5, max_offers=50)
            self.assertEqual("moratorium" in pool, expected)
        for card_id in range(401, 406):
            self.assertTrue(game_state.buy_moratorium(card_id, 5))
        self.assertFalse(game_state.buy_moratorium(406, 5))
        self.assertNotIn("moratorium", game_state._available_screening_offer_ids(5))
        entries = [e for e in game_state.get_active_shop_offer_effects(5) if e["special_id"] == "moratorium"]
        self.assertEqual(len(entries), 5)
        self.assertEqual(entries[0]["remaining"], 20)
        self.assertEqual(entries[0]["remaining_kind"], "runs")

    def test_selection_and_cancellation_charge_only_after_confirmation(self):
        page = ShopPage.__new__(ShopPage)
        page.offers = [{"kind": "special", "special_id": "moratorium", "cost": 6}]
        page.sold_offer_indexes = set()
        page.level_number = 5
        page.screen = page.font_path = None
        page.message = ""
        game_state.napoleondors = 10
        with mock.patch("shop_page.MoratoriumDeckPage") as selector:
            selector.return_value.run.return_value = None
            page._buy_offer(0)
            self.assertEqual(game_state.napoleondors, 10)
            self.assertFalse(page.sold_offer_indexes)
            candidates = selector.call_args.kwargs["deck"]
            self.assertEqual(len(set(candidates)), 10)
            self.assertTrue(set(candidates) <= game_state.seen_gold_card_ids)
            selector.return_value.run.side_effect = lambda: selector.call_args.kwargs["deck"][0]
            page._buy_offer(0)
            self.assertEqual(selector.call_args.kwargs["deck"], candidates)
        self.assertEqual(game_state.napoleondors, 4)
        self.assertEqual(len(game_state.get_active_moratoriums()), 1)

    def test_awards_record_seen_cards_but_pool_rolls_do_not(self):
        game_state.seen_gold_card_ids = set()
        game_state.build_gold_cards_pool(5)
        self.assertFalse(game_state.seen_gold_card_ids)
        game_state.add_gold_card(401)
        self.assertEqual(game_state.seen_gold_card_ids, {401})

    def test_shop_display_records_encounter_and_reload_preserves_it(self):
        game_state.seen_gold_card_ids = set()
        with mock.patch.object(game_state, "build_shop_card_offer_pool", return_value=[401]):
            game_state.generate_shop_offers(5, card_slots=1, special_slots=0, license_slots=0)
        self.assertEqual(game_state.seen_gold_card_ids, {401})
        saved = profile_manager._capture_progress()
        game_state.seen_gold_card_ids.clear()
        profile_manager.apply_profile_to_game_state({"progress": saved})
        self.assertEqual(game_state.get_moratorium_candidates(), [401])

    def test_moratorium_tooltip_names_card_and_run_count(self):
        from gameplay_page import GameplayPage
        from localization import get_language, set_language
        old_language = get_language()
        self.addCleanup(set_language, old_language)
        page = GameplayPage.__new__(GameplayPage)
        for language in ("RU", "ENG", "DE", "HU", "FR"):
            set_language(language)
            with mock.patch.object(page, "_draw_boss_reward_tooltip") as draw:
                page._draw_active_shop_offer_tooltip({
                    "special_id": "moratorium", "card_id": 401,
                    "remaining": 17, "remaining_kind": "runs",
                }, None)
            text = draw.call_args.args[0]["reward_text"]
            self.assertIn("17", text)
            if language != "RU":
                self.assertNotRegex(text, "[А-Яа-яЁё]")
