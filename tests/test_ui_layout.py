import os
import unittest
from unittest import mock
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

import boss_logic
import game_data
import game_state
from asset_loaders import find_font_path_or_exit
from boss_page import (
    BOSS_CHOICE_VERTICAL_SPACING,
    LEVEL5_BOSS_STAGE_RISE,
    POPUP_TEXT_BOTTOM_PADDING,
    build_boss_popup_text_layout,
    build_boss_stage_positions,
    build_next_boss_positions,
    get_boss_stage_rise,
    rebuild_boss_route_layout,
)
from game_data import load_language
from game_screen import GameScreen, PAPER_COLOR
from gameplay_page import GameplayPage
from level_screen_helpers import build_normal_mode_layout, load_primary_level_assets
from gameplay_winlose import build_win_result_layout
from round_page import RoundPage
from round_page_helpers import build_completed_round_lines
from shop_page import RetentionDeckPage, ScreeningOfferPage
from silver_black_page import PositioningPage, ReplicationGoldPage, ReplicationSilverPage, SilverBlackPage


class UiLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        cls.screen = pygame.display.set_mode((1680, 1050))
        cls.font_path = find_font_path_or_exit()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_level_year_is_drawn_without_a_level_description(self):
        page = GameScreen.__new__(GameScreen)
        page.levelcard_image = mock.Mock()
        page.levelcard_image.get_width.return_value = 500
        page.levelcard_image.get_height.return_value = 300
        page.screen = mock.Mock()
        page.lang = {"Level6Year": "1850"}
        page.font_card = mock.sentinel.font_card
        page.font_card_desc = mock.Mock()
        year_surface = mock.Mock()
        page._render_text_cached = mock.Mock(return_value=year_surface)
        page._wrap_text_cached = mock.Mock()
        page._draw_completed_stamp = mock.Mock()
        page.startarrow_image = None

        page._draw_level_card((100, 200), 6, None)

        page._render_text_cached.assert_called_once_with(page.font_card, "1850", PAPER_COLOR)
        page.screen.blit.assert_any_call(year_surface, (490, 208))
        page._wrap_text_cached.assert_not_called()

    def test_normal_campaign_layout_contains_the_sixth_level_card_and_picture(self):
        card = pygame.Surface((604, 360))
        arrow = pygame.Surface((50, 30))
        layout = build_normal_mode_layout(card, arrow, 1680, 75)

        self.assertEqual(layout["card6_position"][0], layout["card4_position"][0])
        self.assertEqual(layout["card6_position"][1], layout["card5_position"][1])
        self.assertIsNotNone(layout["arrow6_rect"])
        self.assertIsNotNone(load_primary_level_assets()["level6_picture"])

    def test_completed_level_has_no_start_arrow(self):
        page = GameScreen.__new__(GameScreen)
        page.levelcard_image = mock.Mock()
        page.levelcard_image.get_width.return_value = 500
        page.levelcard_image.get_height.return_value = 300
        page.screen = mock.Mock()
        page.lang = {}
        page.font_card = mock.Mock()
        page.font_card_desc = mock.Mock()
        page._draw_completed_stamp = mock.Mock()
        page.startarrow_image = mock.Mock()

        page._draw_level_card((100, 200), 1, None, show_start_arrow=False)

        self.assertNotIn(mock.call(page.startarrow_image, mock.ANY), page.screen.blit.call_args_list)

    def test_completed_level_click_is_ignored(self):
        page = GameScreen.__new__(GameScreen)
        page.test_mode = False
        page.progress_flags = {"level_1_boss_defeated": True}
        page.scroll_y = 0
        page.arrow_rect = pygame.Rect(10, 10, 50, 50)
        page.arrow2_rect = None
        page.arrow3_rect = None
        page.arrow4_rect = None
        page.arrow5_rect = None
        page.arrow6_rect = None

        event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(20, 20))
        with mock.patch("pygame.event.get", return_value=[event]), mock.patch("pygame.mouse.get_pos", return_value=(20, 20)):
            self.assertIsNone(page.handle_input())

    def test_campaign_selector_switches_to_second_page_and_opens_level_eight(self):
        page = GameScreen(
            self.screen,
            None,
            self.font_path,
            lang_dict=load_language("RU"),
            progress_flags={"level_8_unlocked": True},
        )
        next_event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=page.next_page_rect.center)
        with (
            mock.patch("pygame.event.get", return_value=[next_event]),
            mock.patch("pygame.mouse.get_pos", return_value=page.next_page_rect.center),
        ):
            self.assertIsNone(page.handle_input())
        self.assertEqual(page.level_page_index, 1)
        self.assertEqual(len(page.normal_card_positions), 6)

        level8_rect = page.normal_arrow_rects[1]
        level8_event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=level8_rect.center)
        with (
            mock.patch("pygame.event.get", return_value=[level8_event]),
            mock.patch("pygame.mouse.get_pos", return_value=level8_rect.center),
        ):
            self.assertEqual(page.handle_input(), "level_8")

    def test_round_popup_uses_the_actual_difficulty_and_boss_payouts(self):
        page = RoundPage.__new__(RoundPage)
        page.level_number = 2
        page.boss_number = 2

        with mock.patch.object(game_state, "profit_reward_bonus", 0):
            for difficulty, expected in (("e", 1), ("m", 2), ("h", 3)):
                with self.subTest(difficulty=difficulty):
                    page.popup_button = difficulty
                    self.assertEqual(page._get_popup_napoleondor_reward(), expected)

            page.popup_button = "boss"
            self.assertEqual(page._get_popup_napoleondor_reward(), 5)

        page.level_number = 1
        self.assertEqual(page._get_popup_napoleondor_reward(), 0)

    def test_level6_opens_the_boss_immediately_without_money_goals(self):
        page = RoundPage(
            self.screen,
            self.font_path,
            6,
            0,
            boss_filename="2_AdamSmith.png",
            lang_dict=load_language("RU"),
            load_rounds_config=game_data.load_rounds_config,
            load_levels_config=game_data.load_levels_config,
            load_boss_rewards=game_data.load_boss_rewards,
            load_rewards_config=game_data.load_rewards_config,
            get_level2_goal=game_data.get_level2_goal,
            get_level3_goal=game_data.get_level3_goal,
            get_level4_goal=game_data.get_level4_goal,
            get_boss_number_from_index=boss_logic.get_boss_number_from_index,
            get_boss_number_from_filename=boss_logic.get_boss_number_from_filename,
            apper_goal_boost=boss_logic.apper_goal_boost,
            reward_token_random_red=game_data.REWARD_TOKEN_RANDOM_RED,
        )

        self.assertEqual(page.rounds_required, 0)
        self.assertIsNone(page.get_current_active_round())
        self.assertIsNone(page.button_e_rect)
        self.assertIsNotNone(page.boss_icon_rect)

        click = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=page.boss_icon_rect.center)
        with (
            mock.patch("pygame.event.get", return_value=[click]),
            mock.patch("pygame.mouse.get_pos", return_value=page.boss_icon_rect.center),
        ):
            self.assertEqual(page.handle_input(), "boss_clicked")
        self.assertEqual(page.Goal, 0)

    def test_round_popup_includes_profit_and_peabody_modifiers(self):
        page = RoundPage.__new__(RoundPage)
        page.level_number = 5
        page.boss_number = 14
        page.popup_button = "h"

        with mock.patch.object(game_state, "profit_reward_bonus", 2):
            self.assertEqual(page._get_popup_napoleondor_reward(), 3.5)

    def test_finance_report_keeps_required_income_order_and_omits_zero_rows(self):
        page = GameplayPage.__new__(GameplayPage)
        page.lang_dict = load_language("RU")
        page.level_number = 5
        page.difficulty = "h"
        page.is_boss_fight = False
        page.boss_filename = None

        with mock.patch.object(game_state, "profit_reward_bonus", 2):
            entries = page._build_finance_report_entries(
                [
                    {"source": "starting_bonus", "amount": 7},
                    {"source": "sideway", "amount": 5},
                ],
                interest_amount=2.5,
                commission_amount=1,
                obligation_amount=0,
            )

        self.assertEqual(
            [entry["source"] for entry in entries],
            [
                "starting_bonus",
                "interest",
                "victory_reward",
                "profit_bonus",
                "sideway",
                "commission",
                "total",
            ],
        )
        self.assertEqual(entries[0]["label"], "Стартовый бонус")
        self.assertEqual(entries[1]["label"], "Проценты")
        self.assertNotIn("obligation", [entry["source"] for entry in entries])
        self.assertEqual(entries[-1]["label"], "Всего")
        self.assertEqual(entries[-1]["amount"], 20.5)

    def test_later_finance_reports_start_with_the_carried_account_balance(self):
        page = GameplayPage.__new__(GameplayPage)
        page.lang_dict = load_language("RU")
        page.level_number = 2
        page.difficulty = "m"
        page.is_boss_fight = False
        page.boss_filename = None

        with mock.patch.object(game_state, "profit_reward_bonus", 0):
            entries = page._build_finance_report_entries(
                [{"source": "sideway", "amount": 5}],
                opening_balance=4,
                interest_amount=1,
            )

        self.assertEqual(
            [entry["source"] for entry in entries],
            ["account_balance", "interest", "victory_reward", "sideway", "total"],
        )
        self.assertEqual(entries[0]["label"], "Остаток на счету")
        self.assertEqual(entries[-1]["amount"], 12)

    def test_zero_starting_bonus_and_shop_income_are_not_reported(self):
        page = GameplayPage.__new__(GameplayPage)
        page.lang_dict = load_language("RU")
        page.level_number = 2
        page.difficulty = "m"
        page.is_boss_fight = False
        page.boss_filename = None

        with mock.patch.object(game_state, "profit_reward_bonus", 0):
            entries = page._build_finance_report_entries(
                [
                    {"source": "starting_bonus", "amount": 0},
                    {"source": "interest", "amount": 2.5},
                    {"source": "loan_profit", "amount": 5},
                    {"source": "junk_bond", "amount": 6},
                    {"source": "card_sales", "amount": 4},
                ]
            )

        self.assertEqual(
            entries,
            [
                {"source": "victory_reward", "label": "Награда за победу", "amount": 2.0},
                {"source": "total", "label": "Всего", "amount": 2.0},
            ],
        )

    def test_finance_income_queue_aggregates_sources_and_is_consumed_once(self):
        original = [dict(entry) for entry in game_state.pending_finance_report_entries]
        try:
            game_state.pending_finance_report_entries = []
            game_state.record_finance_report_income("interest", 1.5)
            game_state.record_finance_report_income("interest", 1)
            game_state.record_finance_report_income("loan_profit", 5)
            game_state.record_finance_report_income("ignored", 0)

            self.assertEqual(
                game_state.consume_finance_report_income(),
                [
                    {"source": "interest", "amount": 2.5},
                    {"source": "loan_profit", "amount": 5.0},
                ],
            )
            self.assertEqual(game_state.consume_finance_report_income(), [])
        finally:
            game_state.pending_finance_report_entries = original

    def test_level_one_never_opens_the_finance_report(self):
        page = GameplayPage.__new__(GameplayPage)
        page.level_number = 1
        self.assertFalse(page._should_show_finance_report())

        page.level_number = 2
        self.assertTrue(page._should_show_finance_report())

        page.is_final_boss = True
        self.assertFalse(page._should_show_finance_report())

    def test_finance_amounts_use_the_same_left_edge(self):
        self.assertEqual(GameplayPage._format_finance_amount(2), "2")
        self.assertEqual(GameplayPage._format_finance_amount(0.5), "0.5")

    def test_stamp_impact_shakes_sheet_and_camera_flight_scales_then_fades(self):
        self.assertEqual(GameplayPage._get_finance_report_shake("idle", 0), (0, 0))
        self.assertNotEqual(GameplayPage._get_finance_report_shake("flying", 0), (0, 0))
        self.assertEqual(GameplayPage._get_finance_report_shake("flying", 180), (0, 0))

        start_scale, start_alpha = GameplayPage._get_stamp_camera_flight(0)
        end_scale, end_alpha = GameplayPage._get_stamp_camera_flight(1)
        self.assertEqual((start_scale, start_alpha), (1.0, 255))
        self.assertGreater(end_scale, start_scale)
        self.assertEqual(end_alpha, 0)

    def test_card_report_describes_each_reward_card_lifecycle(self):
        page = GameplayPage.__new__(GameplayPage)
        page.lang_dict = load_language("RU")
        page.level_number = 5
        page.is_boss_fight = False
        page.is_final_boss = False
        page.last_earned_cards = [11, 201, 401, 301]

        original_rewards = game_state.round_reward_cards
        try:
            game_state.round_reward_cards = {5: [11]}
            rows = page._get_card_report_rows()
        finally:
            game_state.round_reward_cards = original_rewards

        self.assertEqual(
            [row["label"] for row in rows],
            [
                "Временная карта. Пропадёт после победы над боссом.",
                "Серебряная карта. Пропадёт только тогда, когда вы её используете.",
                "Золотая карта. Пропадёт после поражения.",
                "Постоянная карта. Останется в вашей коллекции.",
            ],
        )

    def test_regular_boss_card_reward_is_not_described_as_permanent(self):
        page = GameplayPage.__new__(GameplayPage)
        page.lang_dict = load_language("RU")
        page.level_number = 2
        page.is_boss_fight = True
        page.is_final_boss = False
        page.last_earned_cards = [112]

        original_rewards = game_state.round_reward_cards
        try:
            game_state.round_reward_cards = {}
            rows = page._get_card_report_rows()
        finally:
            game_state.round_reward_cards = original_rewards

        self.assertEqual(
            rows[0]["label"],
            "Бонус за победу над боссом. Пропадёт после поражения.",
        )

    def test_boss_card_report_uses_the_actual_random_reward_description(self):
        page = GameplayPage.__new__(GameplayPage)
        page.lang_dict = load_language("RU")
        page.is_boss_fight = True
        page.is_final_boss = False
        page.random_boss_reward_text = "Случайная награда: 7 наполеондоров."

        self.assertEqual(
            page._get_card_report_boss_description(),
            "Случайная награда: 7 наполеондоров.",
        )

    def test_non_boss_card_report_has_no_boss_description(self):
        page = GameplayPage.__new__(GameplayPage)
        page.is_boss_fight = False
        self.assertIsNone(page._get_card_report_boss_description())

    def test_card_report_keeps_the_golden_stocks_trigger_notice(self):
        page = GameplayPage.__new__(GameplayPage)
        page.lang_dict = load_language("RU")
        page.golden_stocks_reward_card = None
        self.assertIsNone(page._get_card_report_notice())

        page.golden_stocks_reward_card = 401
        self.assertEqual(page._get_card_report_notice(), "Golden Stocks сработал!")

    def test_card_report_cards_are_larger_and_gain_another_twenty_percent_on_hover(self):
        previous_slot_height = 150
        expanded_slot_height = 172
        previous_width = max(
            44,
            min(92, int((previous_slot_height - 12) * (99 / 171.0))),
        )
        report_width = GameplayPage._get_card_report_card_width(expanded_slot_height)
        hover_width = GameplayPage._get_card_report_hover_width(report_width)

        self.assertGreaterEqual(report_width, round(previous_width * 1.15))
        self.assertLessEqual(report_width / (99 / 171.0), expanded_slot_height)
        self.assertEqual(hover_width, round(report_width * 1.20))

    def test_finance_report_closes_into_card_report_before_round_selection(self):
        page = GameplayPage.__new__(GameplayPage)
        report = pygame.Surface((500, 700))
        page.win_lose_state = "win"
        page.result_report_stage = "finance"
        page.finance_report_image = report
        page.card_report_image = report
        page.finance_report_y = float(-report.get_height() - 30)
        page.finance_stamp_state = "closing"
        page.finance_stamp_started_at = 0
        page.finance_stamp_rect = pygame.Rect(0, 0, 10, 10)
        page.report_rustle_sound = mock.Mock()
        page.win_lose_speed_pps = 2400
        page._winlose_last_tick = pygame.time.get_ticks()

        page.update_win_lose_animation()

        self.assertEqual(page.result_report_stage, "card_report")
        self.assertEqual(page.finance_stamp_state, "idle")
        self.assertIsNone(page.finance_stamp_rect)
        page.report_rustle_sound.play.assert_called_once_with()

        page.finance_report_y = float(-report.get_height() - 30)
        page.finance_stamp_state = "closing"
        page.update_win_lose_animation()

        self.assertEqual(page.result_transition_ready, "round_select")

    def test_all_localized_boss_popup_text_fits_the_newspaper_card(self):
        popup_height = 375
        for language in ("RU", "ENG"):
            lang = load_language(language)
            for boss_number in range(1, 11):
                with self.subTest(language=language, boss=boss_number):
                    layout = build_boss_popup_text_layout(
                        self.font_path,
                        popup_height,
                        lang[f"Boss{boss_number}Text"],
                        lang["PopUpReward"],
                        lang[f"Boss{boss_number}Reward"],
                    )
                    self.assertGreaterEqual(layout["font_size"], 18)
                    self.assertLessEqual(
                        layout["content_bottom"],
                        popup_height - POPUP_TEXT_BOTTOM_PADDING,
                    )

    def test_lifecycle_labels_and_continue_button_do_not_overlap_cards(self):
        page = SilverBlackPage(
            self.screen,
            self.font_path,
            [201, 202],
            [301],
            [401],
            active_black_cards=[301],
            lang_dict=load_language("RU"),
        )

        rows = {
            "active": page.active_rects,
            "silver": page.silver_rects,
            "black": page.black_rects,
            "gold": page.gold_rects,
        }
        for kind, rects in rows.items():
            with self.subTest(kind=kind):
                label_rect = page.row_label_rects[kind]
                self.assertGreaterEqual(label_rect.left, page.panel_rect.left)
                self.assertLessEqual(label_rect.right, rects[0].left - 24)
                self.assertFalse(any(label_rect.colliderect(card_rect) for card_rect in rects))
        all_card_rects = [rect for rects in rows.values() for rect in rects]
        self.assertFalse(any(page.continue_button_rect.colliderect(rect) for rect in all_card_rects))
        self.assertTrue(page.panel_rect.contains(page.continue_button_rect))

    def test_lifecycle_continue_button_returns_the_current_selection(self):
        page = SilverBlackPage(
            self.screen,
            self.font_path,
            [201],
            [301],
            [401],
            active_black_cards=[301],
            lang_dict=load_language("RU"),
        )

        result = page._handle_mouse_down(page.continue_button_rect.center)

        self.assertEqual(result["active_black_cards"], [301])
        self.assertEqual(result["active_gold_cards"], [])

    def test_short_seller_and_insurance_are_disabled_before_boss_rounds(self):
        page = SilverBlackPage(
            self.screen,
            self.font_path,
            [211, 220, 201],
            [],
            [],
            is_boss_fight=True,
            lang_dict=load_language("RU"),
        )

        self.assertTrue(page._is_card_disabled(211))
        self.assertTrue(page._is_card_disabled(220))
        self.assertFalse(page._is_card_disabled(201))

        page._begin_drag(page.silver_rects[0].center)
        self.assertIsNone(page.drag_source)

        page.selected_entries = [("silver", 0), ("silver", 1), ("silver", 2)]
        self.assertEqual(page._selected_payload()["active_silver_cards"], [201])

    def test_replication_storage_shows_only_silver_slots_and_requires_selection(self):
        page = ReplicationSilverPage(
            self.screen,
            self.font_path,
            [201, 203],
            lang_dict=load_language("RU"),
        )

        self.assertEqual(len(page.silver_rects), 8)
        self.assertEqual(page.black_cards, [])
        self.assertEqual(page.gold_cards, [])
        self.assertIsNone(page._handle_mouse_down(page.confirm_button_rect.center))

        self.assertIsNone(page._handle_mouse_down(page.silver_rects[1].center))
        self.assertEqual(page.selected_index, 1)
        self.assertEqual(page._handle_mouse_down(page.confirm_button_rect.center), 203)

    def test_replication_plus_storage_shows_only_gold_slots_and_requires_selection(self):
        page = ReplicationGoldPage(
            self.screen,
            self.font_path,
            [401, 405],
            lang_dict=load_language("RU"),
        )

        self.assertEqual(len(page.silver_rects), 8)
        self.assertEqual(page.silver_cards, [])
        self.assertEqual(page.black_cards, [])
        self.assertEqual(page.gold_cards, [401, 405])
        self.assertEqual(page.replication_title, "Репликация Плюс")
        self.assertIsNone(page._handle_mouse_down(page.confirm_button_rect.center))

        self.assertIsNone(page._handle_mouse_down(page.silver_rects[1].center))
        self.assertEqual(page.selected_index, 1)
        self.assertEqual(page._handle_mouse_down(page.confirm_button_rect.center), 405)

    def test_screening_choice_keeps_five_offers_inside_the_panel(self):
        page = ScreeningOfferPage(
            self.screen,
            self.font_path,
            3,
            ["trader", "profit", "junk_bond", "variance", "bailout"],
        )

        self.assertEqual(len(page.offer_rects), 5)
        self.assertTrue(all(page.panel_rect.contains(rect) for rect in page.offer_rects))
        self.assertIsNone(page._handle_mouse_down(page.confirm_rect.center))

        self.assertIsNone(page._handle_mouse_down(page.offer_rects[3].center))
        self.assertEqual(page.selected_index, 3)
        self.assertEqual(page._handle_mouse_down(page.confirm_rect.center), "variance")

    def test_retention_selection_has_no_back_path_and_requires_a_card(self):
        page = RetentionDeckPage(self.screen, self.font_path, [11, 15])

        self.assertFalse(page.allow_back)
        self.assertEqual(len(page.card_rects), 2)
        self.assertTrue(all(page.panel_rect.contains(rect) for rect in page.card_rects))

        crowded_page = RetentionDeckPage(self.screen, self.font_path, list(range(11, 20)))
        self.assertEqual(crowded_page.card_size, (116, 200))
        self.assertLess(crowded_page.card_rects[-1].bottom, crowded_page.confirm_rect.top)

    def test_active_shop_offers_fit_above_the_silver_card_pool(self):
        page = GameplayPage.__new__(GameplayPage)
        panel = pygame.Rect(168, 105, 1344, 840)

        rects = page._build_active_shop_offer_rects(panel, 16)

        self.assertEqual(len(rects), 16)
        self.assertTrue(all(panel.contains(rect) for rect in rects))
        self.assertTrue(
            all(left.right < right.left for left, right in zip(rects, rects[1:]))
        )
        self.assertLess(rects[-1].bottom, panel.bottom - 280)

    def test_positioning_requires_exact_selection_and_supports_pages(self):
        page = PositioningPage(
            self.screen,
            self.font_path,
            list(range(1, 26)),
            selection_limit=2,
            lang_dict=load_language("RU"),
        )

        self.assertEqual(page.positioning_page_count, 2)
        self.assertIsNone(
            page._handle_positioning_mouse_down(page.positioning_continue_button_rect.center)
        )
        page._handle_positioning_mouse_down(page.positioning_card_rects[0].center)
        page._handle_positioning_mouse_down(page.positioning_card_rects[1].center)
        page._handle_positioning_mouse_down(page.positioning_card_rects[2].center)

        self.assertEqual(page.selected_card_indices, [0, 1])
        self.assertEqual(
            page._handle_positioning_mouse_down(page.positioning_continue_button_rect.center),
            [1, 2],
        )
        page._handle_positioning_mouse_down(page.positioning_next_button_rect.center)
        self.assertEqual(page.positioning_page_index, 1)

    def test_positioning_keeps_up_to_twenty_four_cards_on_one_page(self):
        page = PositioningPage(
            self.screen,
            self.font_path,
            list(range(1, 25)),
            selection_limit=2,
            lang_dict=load_language("RU"),
        )

        self.assertEqual(page.positioning_page_count, 1)
        self.assertEqual(len(page._visible_positioning_entries()), 24)
        self.assertTrue(all(page.panel_rect.contains(rect) for rect in page.positioning_card_rects))
        self.assertFalse(
            any(
                rect.colliderect(page.positioning_continue_button_rect)
                or rect.colliderect(page.positioning_back_button_rect)
                for rect in page.positioning_card_rects
            )
        )

    def test_positioning_draws_price_card_action_and_turn_values(self):
        page = PositioningPage(
            self.screen,
            self.font_path,
            [11],
            selection_limit=1,
            lang_dict=load_language("RU"),
        )
        rect = page.positioning_card_rects[0]

        with (
            mock.patch("silver_black_page.draw_card_action_text") as draw_action,
            mock.patch("silver_black_page.draw_card_turns_text") as draw_turns,
            mock.patch("silver_black_page.draw_bid_modifier_text") as draw_bid,
        ):
            page._draw_positioning_card_values(11, rect)

        self.assertEqual(draw_action.call_args.args[2], {11: 2})
        self.assertEqual(draw_turns.call_args.args[2][11], 1)
        draw_bid.assert_called_once()

    def test_completed_round_lines_can_be_rebuilt_from_saved_choices(self):
        base_rects = {
            "e": pygame.Rect(350, 650, 100, 100),
            "m": pygame.Rect(350, 550, 100, 100),
            "h": pygame.Rect(350, 450, 100, 100),
        }

        lines = build_completed_round_lines(
            {1, 2, 3},
            {1: {"key": "m"}, 2: {"key": "e"}, 3: {"key": "h"}},
            base_rects,
            lambda round_num: (150 * (round_num - 1), -100 * (round_num - 1)),
            origin=(235, 832),
        )

        self.assertEqual(
            lines,
            [
                (235, 832, 400, 600),
                (400, 600, 550, 600),
                (550, 600, 700, 300),
            ],
        )

    def test_fourth_boss_choice_keeps_both_candidates_on_screen(self):
        positions = build_next_boss_positions(
            anchor_center=(800, 50),
            choice_count=2,
            vertical_spacing=150,
            screen_height=1050,
        )

        self.assertEqual(len(positions), 2)
        self.assertEqual(positions[0][0], positions[1][0])
        self.assertEqual(abs(positions[0][1] - positions[1][1]), 150)
        for _, center_y in positions:
            self.assertGreaterEqual(center_y - 50, 20)
            self.assertLessEqual(center_y + 50, 1030)

    def test_level5_keeps_the_same_spacing_through_all_four_boss_choices(self):
        self.assertEqual(get_boss_stage_rise(5, 4), LEVEL5_BOSS_STAGE_RISE)
        groups = [
            build_boss_stage_positions(
                position,
                2,
                BOSS_CHOICE_VERTICAL_SPACING,
                LEVEL5_BOSS_STAGE_RISE,
            )
            for position in range(4)
        ]

        for position, group in enumerate(groups):
            self.assertEqual(group[0][1] - group[1][1], BOSS_CHOICE_VERTICAL_SPACING)
            self.assertGreaterEqual(group[1][1] - 50, 20)
            if position > 0:
                self.assertEqual(groups[position - 1][0][1] - group[0][1], LEVEL5_BOSS_STAGE_RISE)
                self.assertEqual(group[0][0] - groups[position - 1][0][0], 200)

    def test_level5_reflows_saved_history_to_the_same_spacing(self):
        roster = [
            ["2_AdamSmith.png", "3_RobertFulton.png"],
            ["4_NicolasApper.png", "5_SamuelSlater.png"],
            ["8_List.png", "9_Laffitte.png"],
            ["11_Malthus.png", "12_Ricardo.png"],
        ]
        old_history = [
            {"filename": "3_RobertFulton.png", "rect": pygame.Rect(350, 500, 100, 100)},
            {"filename": "5_SamuelSlater.png", "rect": pygame.Rect(550, 200, 100, 100)},
            {"filename": "9_Laffitte.png", "rect": pygame.Rect(750, -100, 100, 100)},
        ]

        layout = rebuild_boss_route_layout(
            roster,
            old_history,
            BOSS_CHOICE_VERTICAL_SPACING,
            1050,
            stage_rise=LEVEL5_BOSS_STAGE_RISE,
        )

        centers = [entry["rect"].center for entry in layout["defeated_bosses"]]
        self.assertEqual(centers, [(400, 550), (600, 460), (800, 370)])
        self.assertEqual(layout["last_defeated_rect"].center, (800, 370))
        self.assertTrue(all(rect.top >= 20 for rect in [entry["rect"] for entry in layout["defeated_bosses"]]))

    def test_long_final_victory_content_stays_inside_result_window(self):
        lang = load_language("RU")
        window = pygame.Rect(560, 350, 560, 350)
        ok_button = pygame.Rect(1010, 628, 80, 42)

        layout = build_win_result_layout(
            self.font_path,
            [
                lang["RewardLevel5FinalBoss"],
                lang["BossVictoryDeckReset"],
                "Long принес прибыль: 5 наполеондоров",
            ],
            window,
            ok_button,
            card_count=2,
            extra_text_lines=1,
        )

        cards_rect = pygame.Rect(
            layout["card_start_x"],
            layout["card_y"],
            2 * layout["card_width"] + layout["card_gap"],
            layout["card_height"],
        )
        self.assertGreaterEqual(layout["card_y"], layout["text_bottom"] + 5)
        self.assertTrue(window.contains(cards_rect))
        self.assertFalse(cards_rect.colliderect(ok_button))
        self.assertEqual(
            layout["text_bottom"],
            layout["text_top"] + (len(layout["lines"]) + 1) * layout["line_height"],
        )


if __name__ == "__main__":
    unittest.main()
