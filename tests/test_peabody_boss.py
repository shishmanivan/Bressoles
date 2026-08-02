import unittest
from types import SimpleNamespace
from unittest import mock

import game_state
import profile_manager
from boss_logic import BOSS_LEVELS, apply_boss_functionality, apply_boss_reward


class PeabodyBossTests(unittest.TestCase):
    def setUp(self):
        self.original_shop_bonus = game_state.boss_shop_offer_bonus
        self.original_profit_bonus = game_state.profit_reward_bonus
        game_state.boss_shop_offer_bonus = 0
        game_state.profit_reward_bonus = 0

    def tearDown(self):
        game_state.boss_shop_offer_bonus = self.original_shop_bonus
        game_state.profit_reward_bonus = self.original_profit_bonus

    def test_peabody_is_a_category_two_boss(self):
        self.assertEqual(BOSS_LEVELS["14_Peabody.png"], 2)

    def test_regular_round_base_napoleondor_reward_is_halved(self):
        self.assertEqual(game_state.get_regular_round_napoleondor_reward(1, 14), 0.5)
        self.assertEqual(game_state.get_regular_round_napoleondor_reward(3, 14), 1.5)
        self.assertEqual(game_state.get_regular_round_napoleondor_reward(1, 13), 1)

        game_state.profit_reward_bonus = 2
        reduced_base = game_state.get_regular_round_napoleondor_reward(3, 14)
        self.assertEqual(game_state.get_victory_napoleondor_reward(reduced_base), 3.5)

    def test_functionality_marks_gameplay_with_half_reward_multiplier(self):
        gameplay = SimpleNamespace(boss_round_napoleondor_multiplier=1.0)
        apply_boss_functionality("HalfRoundNapoleondors", gameplay)
        self.assertEqual(gameplay.boss_round_napoleondor_multiplier, 0.5)

    def test_reward_increases_default_special_shop_offers_from_two_to_three(self):
        gameplay = SimpleNamespace()
        apply_boss_reward("ShopOfferPlus1", gameplay)

        with mock.patch.object(
            game_state,
            "build_shop_special_offer_pool",
            return_value=["trader", "bailout", "profit"],
        ) as build_pool:
            offers = game_state.generate_shop_offers(
                5,
                card_slots=0,
                license_slots=0,
            )

        special_offers = [offer for offer in offers if offer["kind"] == "special"]
        self.assertEqual(len(special_offers), 3)
        build_pool.assert_called_once_with(5, max_offers=3)

    def test_shop_offer_bonus_is_saved_and_removed_after_defeat(self):
        game_state.boss_shop_offer_bonus = 1
        progress = profile_manager._capture_progress()
        self.assertEqual(progress["boss_shop_offer_bonus"], 1)

        game_state.reset_level_attempt(5)

        self.assertEqual(game_state.boss_shop_offer_bonus, 0)


if __name__ == "__main__":
    unittest.main()
