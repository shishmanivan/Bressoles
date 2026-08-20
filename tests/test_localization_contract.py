import os
import unittest

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

from game_data import load_language
from gameplay_page import GameplayPage
from round_page_helpers import resolve_boss_reward_text


class LocalizationContractTests(unittest.TestCase):
    def test_boss_texts_do_not_end_with_accidental_colons(self):
        english = load_language("ENG")
        for boss_number in range(1, 7):
            for suffix in ("Text", "Reward"):
                with self.subTest(boss=boss_number, field=suffix):
                    self.assertFalse(english[f"Boss{boss_number}{suffix}"].endswith(":"))

    def test_reward_texts_match_deck_and_inventory_rules(self):
        russian = load_language("RU")
        english = load_language("ENG")

        self.assertIn("добавляется в колоду", russian["Boss2Reward"])
        self.assertIn("dealt normally", english["Boss2Reward"])
        self.assertIn("отдельный инвентарь", russian["Boss5Reward"])
        self.assertEqual(
            russian["Boss6Reward"],
            "Вы получаете 3 серебряные карты (должно быть место).",
        )
        self.assertEqual(
            english["Boss6Reward"],
            "You receive 3 silver cards (storage space required).",
        )
        self.assertNotIn("базовой", russian["BossVictoryDeckReset"])
        self.assertNotIn("base deck", english["BossVictoryDeckReset"])

    def test_level5_final_text_describes_its_campaign_reward(self):
        russian = load_language("RU")
        english = load_language("ENG")
        self.assertIn("Golden Stocks", russian["RewardLevel4FinalBoss"])
        self.assertIn("Golden Stocks", english["RewardLevel4FinalBoss"])
        popup_text = resolve_boss_reward_text(
            "4_NicolasApper.png",
            5,
            0,
            3,
            4,
            lambda filename: 4,
            lambda *args: 4,
            russian.get,
        )
        page = GameplayPage.__new__(GameplayPage)
        page.level_number = 5
        page.reward_level1_final_boss_text = "level 1"
        page.reward_level2_final_boss_text = "level 2"
        page.reward_level3_final_boss_text = "level 3"
        page.reward_level4_final_boss_text = english["RewardLevel4FinalBoss"]
        page.reward_level5_final_boss_text = english["RewardLevel5FinalBoss"]
        page.reward_final_boss_text = english["RewardFinalBoss"]

        self.assertEqual(popup_text, russian["LastBossRewardLevel5"])
        self.assertEqual(page._get_final_boss_reward_text(), english["RewardLevel5FinalBoss"])
        self.assertIn("levels six, seven, and eight", page._get_final_boss_reward_text().lower())
        self.assertIn("commission", page._get_final_boss_reward_text().lower())
        self.assertIn("4 silver, black, or gold cards", page._get_final_boss_reward_text().lower())

    def test_level6_card_uses_1850(self):
        russian = load_language("RU")
        english = load_language("ENG")
        self.assertEqual(russian["Level6Year"], "1850")
        self.assertEqual(english["Level6Year"], "1850")
        self.assertEqual(
            russian["Level6Cond"],
            "Стабилизация рынка. Биржа становится обычным финансовым институтом.",
        )


if __name__ == "__main__":
    unittest.main()
