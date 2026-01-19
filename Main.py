import pygame
import sys
import os
import random
import csv

# Initialize Pygame
pygame.init()

# Constants
SCREEN_WIDTH = 1680
SCREEN_HEIGHT = 1050
FPS = 60

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GOLD = (255, 215, 0)
LIGHT_GOLD = (255, 235, 150)
DARK_GOLD = (184, 134, 11)
PAPER_COLOR = (83, 76, 70)

# -------------------------------
# Animation helpers (dt-based)
# -------------------------------
def _clamp_dt_seconds(dt: float, max_dt: float = 0.05) -> float:
    """Clamp dt to avoid big jumps after window focus loss / stutters."""
    if dt < 0:
        return 0.0
    if dt > max_dt:
        return max_dt
    return dt


def move_towards(current: float, target: float, max_delta: float) -> float:
    """Move current towards target by at most max_delta (both float)."""
    if max_delta <= 0:
        return current
    delta = target - current
    if abs(delta) <= max_delta:
        return target
    return current + max_delta if delta > 0 else current - max_delta


def wrap_text(text, font, max_width):
    """Split text into lines that fit within max_width using rendered widths."""
    if not text:
        return []
    words = text.split()
    lines = []
    current_line = []
    for word in words:
        candidate = " ".join(current_line + [word]) if current_line else word
        candidate_width = font.render(candidate + " ", True, PAPER_COLOR).get_width()
        if candidate_width <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(" ".join(current_line))
            current_line = [word]
    if current_line:
        lines.append(" ".join(current_line))
    return lines

# Language system
Lang = {}  # Dictionary to store language strings
CURRENT_LANGUAGE = "RU"  # Default language (RUS in user's terms, but file uses RU)

# Game progress tracking
level_1_boss_defeated = False  # Track if level 1 boss is defeated
# Boss defeat tracking per level: {level_number: {"defeated": int, "last_rect": pygame.Rect or None, "lines": list}}
boss_progress = {}
# Global Dobor variable - how many cards to draw after each turn (default 1, can be increased by boss rewards)
global_dobor = 1

# Boss roster per level and boss rounds
LEVEL_BOSS_ROUNDS = {
    1: [["1_Watt.png"]],
    2: [["2_AdamSmith.png", "3_RobertFulton.png"],
        ["4_NicolasApper.png", "5_SamuelSlater.png"]],
}

# Reward cards earned by player: {level_number: [list of card_ids]}
# Cards earned from winning rounds are stored here and added to initial deck
earned_reward_cards = {}


def load_language(lang_code="RU"):
    """Load language strings from Lang.csv file"""
    global Lang
    Lang = {}
    
    lang_file = "Lang.csv"
    if not os.path.exists(lang_file):
        print(f"WARNING: Language file not found: {lang_file}")
        return
    
    try:
        with open(lang_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f, delimiter=';')
            for row in reader:
                key = row.get('Key', '').strip()
                # Use RU column (user mentioned RUS, but file has RU)
                value = row.get('RU', '').strip() if lang_code == "RU" else row.get('ENG', '').strip()
                if key:
                    Lang[key] = value
    except Exception as e:
        print(f"ERROR loading language file: {e}")
        # Fallback to English keys if file can't be read
        Lang = {
            'MenuStart': 'Start Game',
            'MenuOption': 'Options',
            'MenuQuit': 'Quit'
        }

# -------------------------------
# Rounds/Boss configuration loader
# -------------------------------
_rounds_config_cache = None
_goals_level2_cache = None


def load_goals_level2():
    """Load goals for level 2 from GoalsLevel2.csv."""
    global _goals_level2_cache
    if _goals_level2_cache is not None:
        return _goals_level2_cache
    
    goals = {
        "E": {},
        "M": {}
    }
    goals_file = "GoalsLevel2.csv"
    if not os.path.exists(goals_file):
        print(f"WARNING: GoalsLevel2.csv not found: {goals_file}")
        _goals_level2_cache = goals
        return goals
    
    try:
        with open(goals_file, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f, delimiter=";")
            for row in reader:
                button = row.get("", "").strip().upper()
                if button not in ["E", "M"]:
                    continue
                
                # Parse round goals for first boss (columns 1, 2, 3, 4)
                for round_num in ["1", "2", "3", "4"]:
                    value_str = row.get(round_num, "").strip()
                    if value_str:
                        try:
                            goals[button][(0, int(round_num))] = int(value_str)
                        except (TypeError, ValueError):
                            pass
                
                # Parse round goals for second boss (columns B2_1, B2_2, B2_3, B2_4)
                for round_num in ["1", "2", "3", "4"]:
                    col_name = f"B2_{round_num}"
                    value_str = row.get(col_name, "").strip()
                    if value_str:
                        try:
                            goals[button][(1, int(round_num))] = int(value_str)
                        except (TypeError, ValueError):
                            pass
                
                # Parse boss round goals
                boss_round_str = row.get("Boss Round", "").strip()
                if boss_round_str:
                    try:
                        goals[button][(0, "boss")] = int(boss_round_str)
                    except (TypeError, ValueError):
                        pass
                
                boss_round2_str = row.get("Boss Round2", "").strip()
                if boss_round2_str:
                    try:
                        goals[button][(1, "boss")] = int(boss_round2_str)
                    except (TypeError, ValueError):
                        pass
    except Exception as e:
        print(f"ERROR loading GoalsLevel2.csv: {e}")
    
    _goals_level2_cache = goals
    return goals


def get_boss_selection_from_filename(level_number, boss_filename):
    """
    Determine boss selection (0 = first boss round, 1 = second boss round) from boss filename.
    
    Args:
        level_number: Level number
        boss_filename: Boss filename (e.g., "2_AdamSmith.png")
    
    Returns:
        Boss selection (0 or 1) or 0 if not found
    """
    if level_number != 2 or not boss_filename:
        return 0
    
    bosses_for_level = LEVEL_BOSS_ROUNDS.get(level_number, [])
    for round_index, boss_list in enumerate(bosses_for_level):
        if boss_filename in boss_list:
            return round_index
    return 0


def get_level2_goal(round_num, button, boss_selection, is_boss_round=False):
    """
    Get goal for level 2 based on round number, button, and boss selection.
    
    Args:
        round_num: Round number (1-4) or None for boss round
        button: "e" or "m" (lowercase)
        boss_selection: 0 for first boss, 1 for second boss
        is_boss_round: True if this is a boss round
    
    Returns:
        Goal value or None if not found
    """
    if round_num is None or is_boss_round:
        round_key = "boss"
    else:
        round_key = round_num
    
    goals = load_goals_level2()
    button_upper = button.upper()
    if button_upper not in goals:
        return None
    
    goal = goals[button_upper].get((boss_selection, round_key))
    return goal


def load_rounds_config():
    """Load per-level configuration (E/M/H goals, Rounds count, Bosses count) from RoundsData.csv."""
    global _rounds_config_cache
    if _rounds_config_cache is not None:
        return _rounds_config_cache
    
    config = {}
    rounds_file = "RoundsData.csv"
    if not os.path.exists(rounds_file):
        print(f"WARNING: RoundsData.csv not found: {rounds_file}")
        _rounds_config_cache = config
        return config
    
    try:
        with open(rounds_file, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f, delimiter=";")
            for row in reader:
                try:
                    level = int(row.get("Level", 0))
                except (TypeError, ValueError):
                    continue
                if level <= 0:
                    continue
                
                def _parse_value(key):
                    raw = (row.get(key, "") or "").strip()
                    if raw == "":
                        return None
                    try:
                        val = int(raw)
                        return val if val > 0 else None
                    except (TypeError, ValueError):
                        return None
                
                config[level] = {
                    "E": _parse_value("E"),
                    "M": _parse_value("M"),
                    "H": _parse_value("H"),
                    "Rounds": _parse_value("Rounds"),
                    "Bosses": _parse_value("Bosses"),
                }
    except Exception as e:
        print(f"ERROR loading RoundsData.csv: {e}")
    
    _rounds_config_cache = config
    return config


def get_bosses_required(level_num, rounds_config):
    """Return bosses required for a level, using CSV; fallback to roster length."""
    cfg_val = rounds_config.get(level_num, {}).get("Bosses") if rounds_config else None
    if cfg_val and cfg_val > 0:
        return cfg_val
    roster = LEVEL_BOSS_ROUNDS.get(level_num)
    if roster:
        return max(1, len(roster))
    return 1


_boss_rewards_cache = None


def load_boss_rewards():
    """Load boss rewards from BossRewards.csv.
    Returns dict: {boss_number: reward_string}
    Example: {2: "Dobor=Dobor+1"}
    """
    global _boss_rewards_cache
    if _boss_rewards_cache is not None:
        return _boss_rewards_cache
    
    rewards = {}
    rewards_file = "BossRewards.csv"
    if not os.path.exists(rewards_file):
        print(f"WARNING: BossRewards.csv not found: {rewards_file}")
        _boss_rewards_cache = rewards
        return rewards
    
    try:
        with open(rewards_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f, delimiter=';')
            for row in reader:
                boss_str = row.get('Boss', '').strip()
                reward_str = row.get('Reward', '').strip()
                if boss_str and reward_str:
                    try:
                        boss_num = int(boss_str)
                        rewards[boss_num] = reward_str
                    except (TypeError, ValueError):
                        print(f"WARNING: Invalid boss number in BossRewards.csv: {boss_str}")
    except Exception as e:
        print(f"ERROR loading BossRewards.csv: {e}")
    
    _boss_rewards_cache = rewards
    return rewards


def apply_boss_reward(reward_string, gameplay_instance):
    """Apply boss reward from reward string.
    Example: "Dobor=Dobor+1" -> global_dobor += 1 and gameplay_instance.Dobor += 1
    
    Args:
        reward_string: Reward string from BossRewards.csv (e.g., "Dobor=Dobor+1")
        gameplay_instance: GameplayPage instance to apply the reward to
    """
    global global_dobor
    if not reward_string or not gameplay_instance:
        return
    
    try:
        # Parse format: "VariableName=VariableName+1" or "VariableName=VariableName-1"
        if '=' in reward_string:
            left, right = reward_string.split('=', 1)
            var_name = left.strip()
            
            # Check if right side matches pattern: "VariableName+number" or "VariableName-number"
            if right.strip().startswith(var_name):
                operation = right.strip()[len(var_name):]
                
                if operation.startswith('+'):
                    # Addition: "Dobor+1" -> Dobor += 1
                    try:
                        amount = int(operation[1:].strip())
                        if hasattr(gameplay_instance, var_name):
                            current_value = getattr(gameplay_instance, var_name)
                            new_value = current_value + amount
                            setattr(gameplay_instance, var_name, new_value)
                            # Update global variable if it's Dobor
                            if var_name == "Dobor":
                                global_dobor = new_value
                            print(f"Applied boss reward: {var_name} = {current_value} + {amount} = {new_value}")
                        else:
                            print(f"WARNING: Variable {var_name} not found in gameplay instance")
                    except (TypeError, ValueError):
                        print(f"WARNING: Invalid reward format: {reward_string}")
                elif operation.startswith('-'):
                    # Subtraction: "Dobor-1" -> Dobor -= 1
                    try:
                        amount = int(operation[1:].strip())
                        if hasattr(gameplay_instance, var_name):
                            current_value = getattr(gameplay_instance, var_name)
                            new_value = current_value - amount
                            setattr(gameplay_instance, var_name, new_value)
                            # Update global variable if it's Dobor
                            if var_name == "Dobor":
                                global_dobor = new_value
                            print(f"Applied boss reward: {var_name} = {current_value} - {amount} = {new_value}")
                        else:
                            print(f"WARNING: Variable {var_name} not found in gameplay instance")
                    except (TypeError, ValueError):
                        print(f"WARNING: Invalid reward format: {reward_string}")
                else:
                    print(f"WARNING: Unsupported reward operation: {reward_string}")
            else:
                # Direct assignment: "VariableName=value"
                try:
                    value = int(right.strip())
                    if hasattr(gameplay_instance, var_name):
                        setattr(gameplay_instance, var_name, value)
                        # Update global variable if it's Dobor
                        if var_name == "Dobor":
                            global_dobor = value
                        print(f"Applied boss reward: {var_name} = {value}")
                    else:
                        print(f"WARNING: Variable {var_name} not found in gameplay instance")
                except (TypeError, ValueError):
                    print(f"WARNING: Invalid reward format: {reward_string}")
        else:
            print(f"WARNING: Invalid reward format (no '=' found): {reward_string}")
    except Exception as e:
        print(f"ERROR applying boss reward '{reward_string}': {e}")


def get_boss_number_from_index(level_number, boss_index):
    """Get boss number from level and boss index for BossRewards.csv lookup.
    Boss numbers: 1=Watt (Level 1), 2=AdamSmith (Level 2, index 0), 3=RobertFulton (Level 2, index 1)
    
    Args:
        level_number: Level number (1 or 2)
        boss_index: Boss index (0-based)
    
    Returns:
        Boss number for BossRewards.csv or None
    """
    if level_number == 1 and boss_index == 0:
        return 1  # Watt
    elif level_number == 2 and boss_index == 0:
        return 2  # Adam Smith
    elif level_number == 2 and boss_index == 1:
        return 3  # Robert Fulton
    return None


def get_text(key, default=None):
    """Get translated text by key"""
    if default is None:
        default = key
    return Lang.get(key, default)


class StartPage:
    def __init__(self, screen, background, font_path, lang_dict=None):
        self.screen = screen
        self.clock = pygame.time.Clock()
        self.lang = lang_dict if lang_dict else Lang

        # Load StartPage image from UI folder
        start_page_path = os.path.join("UI", "StartPage.jpg")
        if os.path.exists(start_page_path):
            self.background = pygame.image.load(start_page_path).convert()
            self.background = pygame.transform.smoothscale(self.background, (SCREEN_WIDTH, SCREEN_HEIGHT)).convert()
        else:
            print("WARNING: StartPage.jpg not found:", start_page_path)
            self.background = background if background else None

        # Load fonts
        self.font_large = pygame.font.Font(font_path, 72)
        self.font_medium = pygame.font.Font(font_path, 48)
        self.font_small = pygame.font.Font(font_path, 36)

        # -------------------------------
        # MENU
        # -------------------------------
        # Use language keys for menu items
        self.menu_items = [
            self.lang.get("MenuStart", "Start Game"),
            self.lang.get("MenuOption", "Options"),
            self.lang.get("MenuQuit", "Quit"),
            self.lang.get("MenuTestMode", "Test Mode")
        ]
        self.selected_index = 0
        
        # Menu positions - adjusted for right side empty slots (centered in slots)
        # These positions are set to align with empty menu slots on the right side of StartPage.jpg
        # Shifted 150 pixels left (70 + 80) to align with decorative elements on dividing lines
        self.menu_positions = [
            (SCREEN_WIDTH - 400, 350),  # Start Game
            (SCREEN_WIDTH - 400, 450),  # Options
            (SCREEN_WIDTH - 400, 550),  # Quit
            (SCREEN_WIDTH - 400, 650),  # Test Mode
        ]

    # ------------------------------------
    # INPUT
    # ------------------------------------
    def _get_menu_rect(self, index):
        """Get the clickable rectangle for a menu item"""
        menu_x, y_pos = self.menu_positions[index]
        item = self.menu_items[index]
        text = self.font_medium.render(item, True, PAPER_COLOR)
        text_rect = text.get_rect(center=(menu_x, y_pos))
        # Expand hitbox slightly for easier clicking
        return text_rect.inflate(20, 10)
    
    def handle_input(self):
        mouse_pos = pygame.mouse.get_pos()
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_UP:
                    self.selected_index = (self.selected_index - 1) % len(self.menu_items)
                elif event.key == pygame.K_DOWN:
                    self.selected_index = (self.selected_index + 1) % len(self.menu_items)
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    # Use index to determine action instead of text content
                    if self.selected_index == 0:  # MenuStart
                        return "start"
                    elif self.selected_index == 1:  # MenuOption
                        return "options"
                    elif self.selected_index == 2:  # MenuQuit
                        return "quit"
                    elif self.selected_index == 3:  # MenuTestMode
                        return "test_mode"
            
            # Mouse support
            if event.type == pygame.MOUSEMOTION:
                # Update selected index based on mouse position
                for i in range(len(self.menu_items)):
                    menu_rect = self._get_menu_rect(i)
                    if menu_rect.collidepoint(mouse_pos):
                        self.selected_index = i
                        break
            
            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # Left click
                    for i in range(len(self.menu_items)):
                        menu_rect = self._get_menu_rect(i)
                        if menu_rect.collidepoint(mouse_pos):
                            # Use index to determine action instead of text content
                            if i == 0:  # MenuStart
                                return "start"
                            elif i == 1:  # MenuOption
                                return "options"
                            elif i == 2:  # MenuQuit
                                return "quit"
                            elif i == 3:  # MenuTestMode
                                return "test_mode"

        return None

    # ------------------------------------
    # DRAW
    # ------------------------------------
    def draw(self):
        # Background - StartPage.jpg from UI folder
        if self.background:
            self.screen.blit(self.background, (0, 0))
        else:
            self.screen.fill(BLACK)

        # Menu - positioned in empty slots on the right side (centered)
        for i, item in enumerate(self.menu_items):
            menu_x, y_pos = self.menu_positions[i]
            
            highlight = (i == self.selected_index)
            color = LIGHT_GOLD if highlight else PAPER_COLOR

            if highlight:
                indicator = self.font_medium.render(">", True, GOLD)
                rect = indicator.get_rect(center=(menu_x - 100, y_pos))
                self.screen.blit(indicator, rect)

            shadow = self.font_medium.render(item, True, BLACK)
            shadow_rect = shadow.get_rect(center=(menu_x + 2, y_pos + 2))
            self.screen.blit(shadow, shadow_rect)

            text = self.font_medium.render(item, True, color)
            text_rect = text.get_rect(center=(menu_x, y_pos))
            self.screen.blit(text, text_rect)

        pygame.display.flip()

    # ------------------------------------
    # RUN LOOP
    # ------------------------------------
    def run(self):
        while True:
            result = self.handle_input()

            if result == "quit":
                return "quit"

            if result == "start":
                return "start"

            if result == "options":
                print("Opening options…")
            
            if result == "test_mode":
                return "test_mode"

            self.draw()
            self.clock.tick(FPS)


class GameScreen:
    def __init__(self, screen, background, font_path, test_mode=False):
        self.screen = screen
        self.clock = pygame.time.Clock()
        self.test_mode = test_mode
        
        # Load Back3.png from UI folder
        back3_path = os.path.join("UI", "Back3.png")
        if os.path.exists(back3_path):
            self.background = pygame.image.load(back3_path).convert()
            self.background = pygame.transform.smoothscale(self.background, (SCREEN_WIDTH, SCREEN_HEIGHT)).convert()
        else:
            print("WARNING: Back3.png not found:", back3_path)
            self.background = background if background else None
        
        # Load LevelCard image
        levelcard_path = os.path.join("LevelPage", "LevelCard.jpg")
        if os.path.exists(levelcard_path):
            original_image = pygame.image.load(levelcard_path).convert_alpha()
            # Reduce card size by 20% (scale to 80%)
            original_width = original_image.get_width()
            original_height = original_image.get_height()
            new_width = int(original_width * 0.8)
            new_height = int(original_height * 0.8)
            self.levelcard_image = pygame.transform.smoothscale(original_image, (new_width, new_height)).convert_alpha()
        else:
            print("WARNING: LevelCard.jpg not found:", levelcard_path)
            self.levelcard_image = None
        
        # Single card position in top left corner with padding to fit within frame on Back3
        padding_x = 40  # Horizontal padding from frame edge
        padding_y = 75  # Vertical padding from frame edge
        self.card_position = (padding_x, padding_y)
        
        # Load fonts for card text
        self.font_card = pygame.font.Font(font_path, 48)  # For title
        self.font_card_desc = pygame.font.Font(font_path, 32)  # For description
        
        # Load StartArrow image
        startarrow_path = os.path.join("LevelPage", "StartArrow.jpg")
        if os.path.exists(startarrow_path):
            original_arrow = pygame.image.load(startarrow_path).convert_alpha()
            # Reduce arrow size to 50% to fit organically on the card
            original_width = original_arrow.get_width()
            original_height = original_arrow.get_height()
            new_width = int(original_width * 0.5)
            new_height = int(original_height * 0.5)
            self.startarrow_image = pygame.transform.smoothscale(original_arrow, (new_width, new_height)).convert_alpha()
        else:
            print("WARNING: StartArrow.jpg not found:", startarrow_path)
            self.startarrow_image = None
        
        # Calculate StartArrow position in bottom right corner of card
        if self.levelcard_image and self.startarrow_image:
            card_width = self.levelcard_image.get_width()
            card_height = self.levelcard_image.get_height()
            arrow_width = self.startarrow_image.get_width()
            arrow_height = self.startarrow_image.get_height()
            # Position: bottom right corner with small padding
            arrow_padding = 15
            self.arrow_position = (
                self.card_position[0] + card_width - arrow_width - arrow_padding,
                self.card_position[1] + card_height - arrow_height - arrow_padding
            )
            self.arrow_rect = pygame.Rect(self.arrow_position[0], self.arrow_position[1], arrow_width, arrow_height)
        else:
            self.arrow_position = (0, 0)
            self.arrow_rect = None
        
        # Level 2 card position will be set in the else block below for normal mode
        # Initialize to None for now
        self.card2_position = None
        self.arrow2_rect = None
        self.arrow2_position = (0, 0)
        
        # Load level pictures for cards (left side dark square area)
        # Level 1 picture - try PNG first, then JPG
        level1_picture_path = None
        level1_picture_path_png = os.path.join("LevelPage", "Level1Picture.png")
        level1_picture_path_jpg = os.path.join("LevelPage", "Level1Picture.jpg")
        
        if os.path.exists(level1_picture_path_png):
            level1_picture_path = level1_picture_path_png
        elif os.path.exists(level1_picture_path_jpg):
            level1_picture_path = level1_picture_path_jpg
        
        if level1_picture_path:
            level1_picture_original = pygame.image.load(level1_picture_path).convert_alpha()
            # Scale to fit in the dark square on the left side of the card
            # Fixed size for all levels: 262 pixels
            picture_size = 262  # Size for the dark square area (fixed for all levels)
            original_pic_width = level1_picture_original.get_width()
            original_pic_height = level1_picture_original.get_height()
            # Maintain aspect ratio and fit within the square
            scale_factor = min(picture_size / original_pic_width, picture_size / original_pic_height) * 0.9  # 90% to leave some padding
            new_pic_width = int(original_pic_width * scale_factor)
            new_pic_height = int(original_pic_height * scale_factor)
            self.level1_picture = pygame.transform.smoothscale(level1_picture_original, (new_pic_width, new_pic_height)).convert_alpha()
        else:
            print("WARNING: Level1Picture.png and Level1Picture.jpg not found in LevelPage folder")
            self.level1_picture = None
        
        # Load Level 1 animation frames from Level1Animation folder
        self.level1_animation_frames = []
        animation_folder = os.path.join("LevelPage", "Level1Animation")
        if os.path.exists(animation_folder):
            # Get all PNG files and sort them by filename
            frame_files = sorted([f for f in os.listdir(animation_folder) if f.lower().endswith('.png')])
            for frame_file in frame_files:
                frame_path = os.path.join(animation_folder, frame_file)
                try:
                    frame_img = pygame.image.load(frame_path).convert_alpha()
                    # Scale to same size as level1_picture
                    if self.level1_picture:
                        frame_img = pygame.transform.smoothscale(frame_img, (new_pic_width, new_pic_height)).convert_alpha()
                    self.level1_animation_frames.append(frame_img)
                except Exception as e:
                    print(f"WARNING: Could not load animation frame {frame_file}: {e}")
        else:
            print("WARNING: Level1Animation folder not found:", animation_folder)
        
        # Animation state for level 1 card hover
        self.is_hovering_level1 = False
        self.level1_animation_frame_index = 0
        self.level1_animation_timer = 0.0
        self.level1_animation_frame_duration = 0.12  # Slow but not too slow: 0.12 seconds per frame (2.88 seconds total for 24 frames)
        
        # Level 2 picture
        level2_picture_path = os.path.join("LevelPage", "Level2Picture.jpg")
        if os.path.exists(level2_picture_path):
            level2_picture_original = pygame.image.load(level2_picture_path).convert_alpha()
            # Scale to fit in the dark square on the left side of the card
            picture_size = 262  # Size for the dark square area (fixed for all levels)
            original_pic_width = level2_picture_original.get_width()
            original_pic_height = level2_picture_original.get_height()
            # Maintain aspect ratio and fit within the square
            scale_factor = min(picture_size / original_pic_width, picture_size / original_pic_height) * 0.9  # 90% to leave some padding
            new_pic_width = int(original_pic_width * scale_factor)
            new_pic_height = int(original_pic_height * scale_factor)
            self.level2_picture = pygame.transform.smoothscale(level2_picture_original, (new_pic_width, new_pic_height)).convert_alpha()
        else:
            print("WARNING: Level2Picture.jpg not found:", level2_picture_path)
            self.level2_picture = None
        
        # Scroll state for when cards don't fit on screen
        self.scroll_y = 0
        self.max_scroll_y = 0
        
        # Initialize card rect for hover detection (will be set in normal mode)
        self.card1_rect = None
        
        # In test mode, prepare for all 12 levels
        if self.test_mode:
            # Calculate grid layout: 2 columns x 6 rows for 12 cards
            self.num_levels = 12
            self.cards_per_row = 2
            self.cards_per_col = 6
            
            # Calculate card positions for grid
            if self.levelcard_image:
                card_width = self.levelcard_image.get_width()
                card_height = self.levelcard_image.get_height()
                card_spacing = 50
                
                # Calculate total width of 2 cards with spacing
                total_cards_width = 2 * card_width + card_spacing
                # Center cards horizontally
                grid_start_x = (SCREEN_WIDTH - total_cards_width) // 2
                grid_start_y = padding_y
                
                # Calculate positions for all 12 cards
                self.test_card_positions = []
                self.test_card_rects = []
                self.test_level_pictures = []
                
                for level_num in range(1, self.num_levels + 1):
                    row = (level_num - 1) // self.cards_per_row
                    col = (level_num - 1) % self.cards_per_row
                    
                    card_x = grid_start_x + col * (card_width + card_spacing)
                    card_y = grid_start_y + row * (card_height + card_spacing)
                    self.test_card_positions.append((card_x, card_y))
                    
                    # Create rect for click detection
                    if self.startarrow_image:
                        arrow_width = self.startarrow_image.get_width()
                        arrow_height = self.startarrow_image.get_height()
                        arrow_padding = 15
                        arrow_x = card_x + card_width - arrow_width - arrow_padding
                        arrow_y = card_y + card_height - arrow_height - arrow_padding
                        self.test_card_rects.append(pygame.Rect(arrow_x, arrow_y, arrow_width, arrow_height))
                    else:
                        self.test_card_rects.append(None)
                    
                    # Try to load level picture - try PNG first, then JPG
                    level_pic_path = None
                    level_pic_path_png = os.path.join("LevelPage", f"Level{level_num}Picture.png")
                    level_pic_path_jpg = os.path.join("LevelPage", f"Level{level_num}Picture.jpg")
                    
                    if os.path.exists(level_pic_path_png):
                        level_pic_path = level_pic_path_png
                    elif os.path.exists(level_pic_path_jpg):
                        level_pic_path = level_pic_path_jpg
                    
                    if level_pic_path:
                        level_pic_original = pygame.image.load(level_pic_path).convert_alpha()
                        picture_size = 262
                        original_pic_width = level_pic_original.get_width()
                        original_pic_height = level_pic_original.get_height()
                        scale_factor = min(picture_size / original_pic_width, picture_size / original_pic_height) * 0.9
                        new_pic_width = int(original_pic_width * scale_factor)
                        new_pic_height = int(original_pic_height * scale_factor)
                        level_pic = pygame.transform.smoothscale(level_pic_original, (new_pic_width, new_pic_height)).convert_alpha()
                    else:
                        level_pic = None
                    self.test_level_pictures.append(level_pic)
                
                # Calculate max scroll (if content is taller than screen)
                total_content_height = self.cards_per_col * (card_height + card_spacing) - card_spacing
                available_height = SCREEN_HEIGHT - padding_y - padding_y  # Top and bottom padding
                if total_content_height > available_height:
                    self.max_scroll_y = total_content_height - available_height
                else:
                    self.max_scroll_y = 0
            else:
                self.test_card_positions = []
                self.test_card_rects = []
                self.test_level_pictures = []
        else:
            # Normal mode: also use 2 cards in a row, centered
            if self.levelcard_image:
                card_width = self.levelcard_image.get_width()
                card_height = self.levelcard_image.get_height()
                card_spacing = 50
                
                # Calculate total width of 2 cards with spacing
                total_cards_width = 2 * card_width + card_spacing
                # Center cards horizontally
                centered_x = (SCREEN_WIDTH - total_cards_width) // 2
                
                # Update card positions to be centered
                self.card_position = (centered_x, padding_y)
                self.card2_position = (centered_x + card_width + card_spacing, padding_y)
                
                # Update arrow positions for centered cards
                if self.startarrow_image:
                    arrow_width = self.startarrow_image.get_width()
                    arrow_height = self.startarrow_image.get_height()
                    arrow_padding = 15
                    # Update arrow position for level 1 (already set, but update for consistency)
                    self.arrow_position = (
                        self.card_position[0] + card_width - arrow_width - arrow_padding,
                        self.card_position[1] + card_height - arrow_height - arrow_padding
                    )
                    self.arrow_rect = pygame.Rect(self.arrow_position[0], self.arrow_position[1], arrow_width, arrow_height)
                    
                    # Level 2 arrow position
                    self.arrow2_position = (
                        self.card2_position[0] + card_width - arrow_width - arrow_padding,
                        self.card2_position[1] + card_height - arrow_height - arrow_padding
                    )
                    self.arrow2_rect = pygame.Rect(self.arrow2_position[0], self.arrow2_position[1], arrow_width, arrow_height)
                else:
                    self.arrow2_rect = None
                
                # Create rect for level 1 card hover detection
                self.card1_rect = pygame.Rect(self.card_position[0], self.card_position[1], card_width, card_height)
    
    def handle_input(self):
        mouse_pos = pygame.mouse.get_pos()
        
        # Check if mouse is hovering over level 1 card (only in normal mode, not test mode)
        if not self.test_mode and self.card1_rect:
            was_hovering = self.is_hovering_level1
            self.is_hovering_level1 = self.card1_rect.collidepoint(mouse_pos)
            
            # If mouse just left the card, reset animation to first frame
            if was_hovering and not self.is_hovering_level1:
                self.level1_animation_frame_index = 0
                self.level1_animation_timer = 0.0
            
            # If mouse just entered the card, start animation from beginning
            if not was_hovering and self.is_hovering_level1:
                self.level1_animation_frame_index = 0
                self.level1_animation_timer = 0.0
        else:
            self.is_hovering_level1 = False
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"
            
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return "back"
                # Handle scrolling with arrow keys
                if event.key == pygame.K_UP:
                    self.scroll_y = max(0, self.scroll_y - 50)
                elif event.key == pygame.K_DOWN:
                    self.scroll_y = min(self.max_scroll_y, self.scroll_y + 50)
            
            # Handle mouse wheel scrolling
            if event.type == pygame.MOUSEWHEEL:
                scroll_amount = event.y * 30  # Scroll speed
                self.scroll_y = max(0, min(self.max_scroll_y, self.scroll_y - scroll_amount))
            
            # Handle StartArrow click for level 1
            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # Left click
                    if self.test_mode:
                        # In test mode, check all 12 level cards (account for scroll)
                        for level_num in range(1, self.num_levels + 1):
                            card_index = level_num - 1
                            if (card_index < len(self.test_card_rects) and 
                                self.test_card_rects[card_index]):
                                # Adjust rect position for scroll
                                # When scroll_y > 0, cards are drawn higher, so rect needs to be adjusted up
                                rect = self.test_card_rects[card_index]
                                adjusted_rect = pygame.Rect(rect.x, rect.y - self.scroll_y, rect.width, rect.height)
                                if adjusted_rect.collidepoint(mouse_pos):
                                    return f"level_{level_num}"
                    else:
                        # Normal mode: only check level 1 and level 2
                        if self.arrow_rect and self.arrow_rect.collidepoint(mouse_pos):
                            # Navigate to boss page for level 1
                            return "level_1"
                        # Handle StartArrow click for level 2 (if unlocked)
                        global level_1_boss_defeated
                        if level_1_boss_defeated and self.arrow2_rect and self.arrow2_rect.collidepoint(mouse_pos):
                            # Navigate to boss page for level 2
                            return "level_2"
        
        return None
    
    def _draw_level_card(self, card_position, level_num, level_picture):
        """Helper method to draw a single level card"""
        if not self.levelcard_image:
            return
        
        card_width = self.levelcard_image.get_width()
        card_height = self.levelcard_image.get_height()
        
        # Draw card
        self.screen.blit(self.levelcard_image, card_position)
        
        # Draw level picture in the left side dark square area (only if picture exists)
        if level_picture:
            dark_square_size = 262
            picture_x = card_position[0] + dark_square_size // 2
            picture_y = card_position[1] + card_height // 2
            picture_x -= level_picture.get_width() // 2
            picture_y -= level_picture.get_height() // 2
            picture_x -= 4
            picture_y -= 11
            self.screen.blit(level_picture, (picture_x, picture_y))
        
        # Check if level text exists in Lang dictionary
        desc_key = f"Level{level_num}Cond"
        desc_text = get_text(desc_key, None)
        
        # Only draw title and description if text exists (not just the key)
        if desc_text and desc_text != desc_key:
            # Draw card title (year based on level number)
            # For now, use a simple pattern: 1815 + (level_num - 1) * 10
            year = 1815 + (level_num - 1) * 10
            card_text = str(year)
            text_surface = self.font_card.render(card_text, True, PAPER_COLOR)
            text_x = card_position[0] + 390
            text_y = card_position[1] + 8
            self.screen.blit(text_surface, (text_x, text_y))
            
            # Split text into multiple lines
            max_width = 400
            lines = wrap_text(desc_text, self.font_card_desc, max_width)
            
            # Draw each line below the title
            line_height = self.font_card_desc.get_height() + 5
            start_y = text_y + text_surface.get_height() + 20
            start_x = card_position[0] + 250
            
            for i, line in enumerate(lines):
                line_surface = self.font_card_desc.render(line, True, PAPER_COLOR)
                self.screen.blit(line_surface, (start_x, start_y + i * line_height))
        
        # Draw StartArrow in bottom right corner
        if self.startarrow_image:
            arrow_x = card_position[0] + card_width - self.startarrow_image.get_width() - 15
            arrow_y = card_position[1] + card_height - self.startarrow_image.get_height() - 15
            self.screen.blit(self.startarrow_image, (arrow_x, arrow_y))
    
    def draw(self):
        # Background
        if self.background:
            self.screen.blit(self.background, (0, 0))
        else:
            self.screen.fill(BLACK)
        
        # In test mode, draw all 12 level cards with scroll
        if self.test_mode and self.levelcard_image:
            # Create a surface for scrolling content
            for level_num in range(1, self.num_levels + 1):
                card_index = level_num - 1
                if card_index < len(self.test_card_positions):
                    card_x, card_y = self.test_card_positions[card_index]
                    # Adjust position for scroll
                    adjusted_y = card_y - self.scroll_y
                    # Only draw if card is visible on screen
                    if -self.levelcard_image.get_height() <= adjusted_y <= SCREEN_HEIGHT:
                        card_position = (card_x, adjusted_y)
                        level_picture = self.test_level_pictures[card_index] if card_index < len(self.test_level_pictures) else None
                        self._draw_level_card(card_position, level_num, level_picture)
            pygame.display.flip()
            return
        
        # Normal mode: Draw single level card in top left corner
        if self.levelcard_image:
            self.screen.blit(self.levelcard_image, self.card_position)
            
            # Update animation when hovering
            if self.is_hovering_level1 and self.level1_animation_frames:
                # Update animation timer
                dt = self.clock.get_time() / 1000.0  # Convert to seconds
                dt = _clamp_dt_seconds(dt)
                self.level1_animation_timer += dt
                
                # Advance to next frame if timer exceeds frame duration
                # Play animation only once (stop at last frame)
                max_frame_index = len(self.level1_animation_frames) - 1
                if self.level1_animation_frame_index < max_frame_index:
                    if self.level1_animation_timer >= self.level1_animation_frame_duration:
                        self.level1_animation_frame_index += 1
                        self.level1_animation_timer = 0.0
            
            # Draw level 1 picture or animation frame in the left side dark square area
            picture_to_draw = None
            if self.is_hovering_level1 and self.level1_animation_frames:
                # Use animation frame when hovering
                if self.level1_animation_frame_index < len(self.level1_animation_frames):
                    picture_to_draw = self.level1_animation_frames[self.level1_animation_frame_index]
            elif self.level1_picture:
                # Use static picture when not hovering
                picture_to_draw = self.level1_picture
            
            if picture_to_draw:
                # Position in the left side dark square (centered in left area of card)
                # Dark square is approximately in the left 200-250px area, centered vertically
                card_width = self.levelcard_image.get_width()
                card_height = self.levelcard_image.get_height()
                # Dark square is in left side, approximately 100px from left edge, centered vertically
                dark_square_size = 262  # Size of dark square
                picture_x = self.card_position[0] + dark_square_size // 2  # Center horizontally in dark square
                picture_y = self.card_position[1] + card_height // 2  # Center vertically in card
                # Center the picture within the dark square
                picture_x -= picture_to_draw.get_width() // 2
                picture_y -= picture_to_draw.get_height() // 2
                # Adjust position: 12 pixels right, 7 pixels up
                picture_x -= 4
                picture_y -= 11
                self.screen.blit(picture_to_draw, (picture_x, picture_y))
            
            # Draw card title "1815" in upper part, slightly shifted to the right
            card_text = "1815"
            text_surface = self.font_card.render(card_text, True, PAPER_COLOR)
            # Position: card top + small offset, card left + right shift
            text_x = self.card_position[0] + 390  # Shift 30px to the right from card left edge
            text_y = self.card_position[1] + 8  # 20px from card top
            self.screen.blit(text_surface, (text_x, text_y))
            
            # Draw card description with Level1Cond key below the title
            desc_text = get_text("Level1Cond", "Level1Cond")
            # Split long text into multiple lines (max width ~400px for card)
            max_width = 400
            lines = wrap_text(desc_text, self.font_card_desc, max_width)
            
            # Draw each line below the title
            line_height = self.font_card_desc.get_height() + 5  # 5px spacing between lines
            start_y = text_y + text_surface.get_height() + 20  # 20px below title
            start_x = self.card_position[0] + 250  # Left margin for description
            
            for i, line in enumerate(lines):
                line_surface = self.font_card_desc.render(line, True, PAPER_COLOR)
                self.screen.blit(line_surface, (start_x, start_y + i * line_height))
            
            # Draw StartArrow in bottom right corner
            if self.startarrow_image:
                self.screen.blit(self.startarrow_image, self.arrow_position)
        
        # Draw level 2 card if level 1 boss is defeated
        global level_1_boss_defeated
        if level_1_boss_defeated and self.levelcard_image:
            # Draw level 2 card
            self.screen.blit(self.levelcard_image, self.card2_position)
            
            # Draw level 2 picture in the left side dark square area
            if self.level2_picture:
                # Position in the left side dark square (centered in left area of card)
                # Dark square is approximately in the left 200-250px area, centered vertically
                card_width = self.levelcard_image.get_width()
                card_height = self.levelcard_image.get_height()
                # Dark square is in left side, approximately 100px from left edge, centered vertically
                dark_square_size = 262  # Size of dark square (fixed for all levels)
                picture_x = self.card2_position[0] + dark_square_size // 2  # Center horizontally in dark square
                picture_y = self.card2_position[1] + card_height // 2  # Center vertically in card
                # Center the picture within the dark square
                picture_x -= self.level2_picture.get_width() // 2
                picture_y -= self.level2_picture.get_height() // 2
                # Adjust position: fixed offsets for all levels (4 pixels left, 11 pixels up)
                picture_x -= 4
                picture_y -= 11
                self.screen.blit(self.level2_picture, (picture_x, picture_y))
            
            # Draw card title "1825" in upper part, slightly shifted to the right
            card_text = "1825"
            text_surface = self.font_card.render(card_text, True, PAPER_COLOR)
            # Position: card top + small offset, card left + right shift
            text_x = self.card2_position[0] + 390  # Shift 30px to the right from card left edge
            text_y = self.card2_position[1] + 8  # 20px from card top
            self.screen.blit(text_surface, (text_x, text_y))
            
            # Draw card description with Level2Cond key below the title
            desc_text = get_text("Level2Cond", "Level2Cond")
            # Split long text into multiple lines (max width ~400px for card)
            max_width = 400
            lines = wrap_text(desc_text, self.font_card_desc, max_width)
            
            # Draw each line below the title
            line_height = self.font_card_desc.get_height() + 5  # 5px spacing between lines
            start_y = text_y + text_surface.get_height() + 20  # 20px below title
            start_x = self.card2_position[0] + 250  # Left margin for description
            
            for i, line in enumerate(lines):
                line_surface = self.font_card_desc.render(line, True, PAPER_COLOR)
                self.screen.blit(line_surface, (start_x, start_y + i * line_height))
            
            # Draw StartArrow in bottom right corner of level 2 card
            if self.startarrow_image:
                self.screen.blit(self.startarrow_image, self.arrow2_position)
        
        pygame.display.flip()
    
    def run(self):
        while True:
            result = self.handle_input()
            
            if result == "quit":
                pygame.quit()
                sys.exit()
            
            if result == "back":
                return "back"
            
            # Handle level selection - navigate to boss page
            if result and result.startswith("level_"):
                return result
            
            self.draw()
            self.clock.tick(FPS)


class GameplayPage:
    def __init__(self, screen, font_path, difficulty="e", goal=None, level_number=1, is_boss_fight=False, boss_index=None, round_num=None):
        self.screen = screen
        self.clock = pygame.time.Clock()
        self.difficulty = difficulty  # "e", "m", or "h"
        self.Goal = goal  # Goal for this round
        self.level_number = level_number  # Level number for deck initialization
        self.is_boss_fight = is_boss_fight
        self.boss_index = boss_index  # Boss index (0-based) for applying boss modifiers
        self.is_final_boss = self.is_boss_fight and self.level_number == 1
        self.round_num = round_num  # Current round number for reward lookup
        
        # Save font path for dynamic font creation
        self.font_path = font_path
        
        # Load fonts
        self.font_large = pygame.font.Font(font_path, 72)
        self.font_medium = pygame.font.Font(font_path, 48)
        self.font_small = pygame.font.Font(font_path, 36)
        
        # Load background from GameplayPage folder
        bg_path = os.path.join("GameplayPage", "Background.png")
        if os.path.exists(bg_path):
            bg_image = pygame.image.load(bg_path).convert()
            self.background = pygame.transform.smoothscale(bg_image, (SCREEN_WIDTH, SCREEN_HEIGHT)).convert()
        else:
            print("WARNING: GameplayPage background not found:", bg_path)
            self.background = None
        
        # Load Frame.png for the three top frames
        frame_path = os.path.join("GameplayPage", "Frame.png")
        if os.path.exists(frame_path):
            frame_original = pygame.image.load(frame_path).convert_alpha()
            # Scale frame appropriately - need to determine size based on layout
            # For three frames at top, each should be about 1/3 of screen width
            # Then reduce by 30% (multiply by 0.7)
            frame_width = int((SCREEN_WIDTH // 3 - 20) * 0.7)  # Leave some spacing, then reduce by 30%
            # Maintain aspect ratio
            original_width = frame_original.get_width()
            original_height = frame_original.get_height()
            scale_factor = frame_width / original_width
            frame_height = int(original_height * scale_factor)
            self.frame = pygame.transform.smoothscale(frame_original, (frame_width, frame_height)).convert_alpha()
        else:
            print("WARNING: Frame.png not found:", frame_path)
            self.frame = None

        # Load arrows: outer up from ArrowAll, outer down from ArrowAllDown, middle from ArrowMiddle/Arrow1.png, all scaled to 60x60
        arrow_path = os.path.join("GameplayPage", "ArrowAll", "ArrowAll.png")
        arrow_path_1 = os.path.join("GameplayPage", "ArrowAll", "ArrowAll1.png")
        arrow_path_2 = os.path.join("GameplayPage", "ArrowAll", "ArrowAll2.png")
        arrow_down_path = os.path.join("GameplayPage", "ArrowAllDown", "ArrowAll.png")
        arrow_down_path_1 = os.path.join("GameplayPage", "ArrowAllDown", "ArrowAll1.png")
        arrow_down_path_2 = os.path.join("GameplayPage", "ArrowAllDown", "ArrowAll2.png")
        arrow_mid_path = os.path.join("GameplayPage", "ArrowMiddle", "Arrow1.png")

        # Outer up arrows (ArrowAll)
        self.arrow_anim_frames = []
        if os.path.exists(arrow_path):
            base_img = pygame.image.load(arrow_path).convert_alpha()
            base_img = pygame.transform.smoothscale(base_img, (60, 60)).convert_alpha()
            self.arrow_anim_frames.append(base_img)
            self.arrow_up = base_img
        else:
            print("WARNING: Arrow image not found:", arrow_path)
            self.arrow_up = None
        for extra_path in [arrow_path_1, arrow_path_2]:
            if os.path.exists(extra_path):
                img = pygame.image.load(extra_path).convert_alpha()
                img = pygame.transform.smoothscale(img, (60, 60)).convert_alpha()
                self.arrow_anim_frames.append(img)
        while len(self.arrow_anim_frames) < 3 and self.arrow_anim_frames:
            self.arrow_anim_frames.append(self.arrow_anim_frames[-1])

        # Outer down arrows (ArrowAllDown)
        self.arrow_down_frames = []
        if os.path.exists(arrow_down_path):
            base_img = pygame.image.load(arrow_down_path).convert_alpha()
            base_img = pygame.transform.smoothscale(base_img, (60, 60)).convert_alpha()
            self.arrow_down_frames.append(base_img)
            self.arrow_down = base_img
        else:
            print("WARNING: Arrow image not found:", arrow_down_path)
            self.arrow_down = None
        for extra_path in [arrow_down_path_1, arrow_down_path_2]:
            if os.path.exists(extra_path):
                img = pygame.image.load(extra_path).convert_alpha()
                img = pygame.transform.smoothscale(img, (60, 60)).convert_alpha()
                self.arrow_down_frames.append(img)
        while len(self.arrow_down_frames) < 3 and self.arrow_down_frames:
            self.arrow_down_frames.append(self.arrow_down_frames[-1])

        # Middle arrows - load animation frames for middle up arrow
        arrow_mid_path_2 = os.path.join("GameplayPage", "ArrowMiddle", "Arrow2.png")
        arrow_mid_path_3 = os.path.join("GameplayPage", "ArrowMiddle", "Arrow3.png")
        
        self.arrow_mid_up_frames = []
        if os.path.exists(arrow_mid_path):
            arrow_mid_img = pygame.image.load(arrow_mid_path).convert_alpha()
            arrow_mid_img = pygame.transform.smoothscale(arrow_mid_img, (60, 60)).convert_alpha()
            self.arrow_mid_up_frames.append(arrow_mid_img)
            self.arrow_mid_up = arrow_mid_img
        else:
            print("WARNING: Middle Arrow image not found:", arrow_mid_path)
            self.arrow_mid_up = None
        
        # Load additional animation frames for middle up arrow
        for extra_path in [arrow_mid_path_2, arrow_mid_path_3]:
            if os.path.exists(extra_path):
                img = pygame.image.load(extra_path).convert_alpha()
                img = pygame.transform.smoothscale(img, (60, 60)).convert_alpha()
                self.arrow_mid_up_frames.append(img)
        
        # Ensure we have 3 frames by duplicating if missing
        while len(self.arrow_mid_up_frames) < 3 and self.arrow_mid_up_frames:
            self.arrow_mid_up_frames.append(self.arrow_mid_up_frames[-1])
        
        # Middle down arrow - use ArrowDown1.png as base, then load animation frames from ArrowMiddleDown folder
        arrow_mid_down_path_1 = os.path.join("GameplayPage", "ArrowMiddleDown", "ArrowDown1.png")
        arrow_mid_down_path_2 = os.path.join("GameplayPage", "ArrowMiddleDown", "ArrowDown2.png")
        arrow_mid_down_path_3 = os.path.join("GameplayPage", "ArrowMiddleDown", "ArrowDown3.png")
        
        self.arrow_mid_down_frames = []
        if os.path.exists(arrow_mid_down_path_1):
            arrow_mid_down_base = pygame.image.load(arrow_mid_down_path_1).convert_alpha()
            arrow_mid_down_base = pygame.transform.smoothscale(arrow_mid_down_base, (60, 60)).convert_alpha()
            self.arrow_mid_down_frames.append(arrow_mid_down_base)
            self.arrow_mid_down = arrow_mid_down_base
        else:
            print("WARNING: Middle Down Arrow image not found:", arrow_mid_down_path_1)
            self.arrow_mid_down = None
        
        # Load additional animation frames for middle down arrow
        for extra_path in [arrow_mid_down_path_2, arrow_mid_down_path_3]:
            if os.path.exists(extra_path):
                img = pygame.image.load(extra_path).convert_alpha()
                img = pygame.transform.smoothscale(img, (60, 60)).convert_alpha()
                self.arrow_mid_down_frames.append(img)
        
        # Ensure we have 3 frames by duplicating if missing
        while len(self.arrow_mid_down_frames) < 3 and self.arrow_mid_down_frames:
            self.arrow_mid_down_frames.append(self.arrow_mid_down_frames[-1])

        # Arrow animation state (per clickable arrow)
        self.arrow_anim_interval = 120  # ms
        self.arrow_anim_sequence = [0, 1, 2, 1, 0]  # ping-pong once
        self.arrow_entries = []  # populated each draw: [{'rect':Rect,'animating':bool,'idx':int,'last':ms}]

        # Load bottom frame for the strategy cards area
        bottom_frame_path = os.path.join("GameplayPage", "Bottom Frame.png")
        if os.path.exists(bottom_frame_path):
            bottom_original = pygame.image.load(bottom_frame_path).convert_alpha()
            # Scale bottom frame - enlarge by 40% to accommodate larger hand cards (57.6% * 1.4 = 80.64%)
            target_width = int(SCREEN_WIDTH * 0.8064)
            b_orig_w = bottom_original.get_width()
            b_orig_h = bottom_original.get_height()
            b_scale = target_width / b_orig_w
            target_height = int(b_orig_h * b_scale)
            self.bottom_frame = pygame.transform.smoothscale(bottom_original, (target_width, target_height)).convert_alpha()
        else:
            print("WARNING: Bottom Frame.png not found:", bottom_frame_path)
            self.bottom_frame = None

        # Load sound for arrow click
        woodtap_path = os.path.join("Sounds", "WoodTap.wav")
        if os.path.exists(woodtap_path):
            self.arrow_sound = pygame.mixer.Sound(woodtap_path)
        else:
            print("WARNING: WoodTap.wav not found at", woodtap_path)
            self.arrow_sound = None

        # Load sound for price animation
        typewriter_path = os.path.join("Sounds", "Typewriter.wav")
        if os.path.exists(typewriter_path):
            self.typewriter_sound = pygame.mixer.Sound(typewriter_path)
        else:
            print("WARNING: Typewriter.wav not found at", typewriter_path)
            self.typewriter_sound = None

        # Load price unchanged animation from Graph= folder
        graph_folder = os.path.join("GameplayPage", "Graph=")
        self.price_unchanged_frames = []
        # Animation size: increased by 40% from 84x72 to 118x101 (total 68% increase from original 70x60)
        self.animation_width = 118
        self.animation_height = 101
        if os.path.exists(graph_folder):
            # Load frames 0.png to 20.png (21 frames)
            for i in range(21):
                frame_path = os.path.join(graph_folder, f"{i}.png")
                if os.path.exists(frame_path):
                    frame_img = pygame.image.load(frame_path).convert_alpha()
                    # Scale to 84x72 (20% increase from 70x60)
                    frame_img = pygame.transform.smoothscale(frame_img, (self.animation_width, self.animation_height)).convert_alpha()
                    self.price_unchanged_frames.append(frame_img)
                else:
                    print(f"WARNING: Frame {i}.png not found in Graph= folder")
        else:
            print("WARNING: Graph= folder not found:", graph_folder)

        # Load price rise animation from GraphRise folder
        graph_rise_folder = os.path.join("GameplayPage", "GraphRise")
        self.price_rise_frames = []
        if os.path.exists(graph_rise_folder):
            # Load frames 1.png to 15.png (15 frames)
            for i in range(1, 16):
                frame_path = os.path.join(graph_rise_folder, f"{i}.png")
                if os.path.exists(frame_path):
                    frame_img = pygame.image.load(frame_path).convert_alpha()
                    # Scale to 84x72 (20% increase from 70x60)
                    frame_img = pygame.transform.smoothscale(frame_img, (self.animation_width, self.animation_height)).convert_alpha()
                    self.price_rise_frames.append(frame_img)
                else:
                    print(f"WARNING: Frame {i}.png not found in GraphRise folder")
        else:
            print("WARNING: GraphRise folder not found:", graph_rise_folder)

        # Load price fall animation from GraphDown folder
        graph_down_folder = os.path.join("GameplayPage", "GraphDown")
        self.price_fall_frames = []
        if os.path.exists(graph_down_folder):
            # Load frames 1.png to 17.png (17 frames)
            for i in range(1, 18):
                frame_path = os.path.join(graph_down_folder, f"{i}.png")
                if os.path.exists(frame_path):
                    frame_img = pygame.image.load(frame_path).convert_alpha()
                    # Scale to 84x72 (20% increase from 70x60)
                    frame_img = pygame.transform.smoothscale(frame_img, (self.animation_width, self.animation_height)).convert_alpha()
                    self.price_fall_frames.append(frame_img)
                else:
                    print(f"WARNING: Frame {i}.png not found in GraphDown folder")
        else:
            print("WARNING: GraphDown folder not found:", graph_down_folder)

        # Price animation state (for sequential playback)
        self.price_animation_queue = []  # List of {'market': 0-2, 'type': 'unchanged'|'rise'} that need animation
        self.current_price_animation = None  # Current animation: {'market': 0-2, 'type': 'unchanged'|'rise', 'frame_idx': int, 'last_update': ms}
        self.price_animation_speed = 12  # frames per second (increased by 30% from 9 to 12, approximately 83ms per frame)
        self.price_animation_interval = 1000 // self.price_animation_speed  # ms per frame

        # Load column logos (A, B, C)
        logo_a_path = os.path.join("GameplayPage", "A logo New.png")
        logo_b_path = os.path.join("GameplayPage", "B Logo New.png")
        logo_c_path = os.path.join("GameplayPage", "C Logo New.png")

        self.logo_a = pygame.image.load(logo_a_path).convert_alpha() if os.path.exists(logo_a_path) else None
        self.logo_b = pygame.image.load(logo_b_path).convert_alpha() if os.path.exists(logo_b_path) else None
        self.logo_c = pygame.image.load(logo_c_path).convert_alpha() if os.path.exists(logo_c_path) else None

        # Scale logos to fit inside frames (approx top-left area) without distorting aspect ratio
        max_logo_w, max_logo_h = 112, 128  # previous target box, but preserve aspect ratio per logo
        def scale_logo(img):
            if not img:
                return None
            w, h = img.get_width(), img.get_height()
            scale = min(max_logo_w / w, max_logo_h / h)
            new_size = (int(w * scale), int(h * scale))
            return pygame.transform.smoothscale(img, new_size).convert_alpha()

        self.logo_a = scale_logo(self.logo_a)
        self.logo_b = scale_logo(self.logo_b)
        self.logo_c = scale_logo(self.logo_c)
        
        # Load rewards from Rewards.csv
        # Format: {(level, round, button): {'reward1': [list of card_numbers or single int], 'reward2': card_number or None}}
        self.rewards = {}
        rewards_file = "Rewards.csv"
        if os.path.exists(rewards_file):
            try:
                with open(rewards_file, 'r', encoding='utf-8-sig') as f:
                    reader = csv.DictReader(f, delimiter=';')
                    for row in reader:
                        level = int(row.get('Level', 0))
                        round_num = int(row.get('Round', 0))
                        button_val = row.get('Button') or ''
                        button = button_val.strip().upper() if button_val else ''
                        reward1_val = row.get('Reward1') or ''
                        reward1_str = reward1_val.strip() if reward1_val else ''
                        reward2_val = row.get('Reward2') or ''
                        reward2_str = reward2_val.strip() if reward2_val else ''
                        reward_text_val = row.get('Text') or ''
                        reward_text = reward_text_val.strip() if reward_text_val else ''
                        
                        if level > 0 and round_num > 0 and button and reward1_str:
                            # Parse Reward1 - can be single card or multiple cards separated by comma
                            reward1_list = []
                            for card_str in reward1_str.split(','):
                                card_str = card_str.strip()
                                if card_str:
                                    try:
                                        card_num = int(card_str)
                                        if card_num == 0:
                                            card_num = 100
                                        reward1_list.append(card_num)
                                    except ValueError:
                                        pass
                            
                            if reward1_list:
                                # Parse Reward2 - can be single card, multiple cards separated by comma, or None
                                reward2_list = []
                                if reward2_str and reward2_str.strip():
                                    for card_str in reward2_str.split(','):
                                        card_str = card_str.strip()
                                        if card_str:
                                            try:
                                                card_num = int(card_str)
                                                if card_num == 0:
                                                    card_num = 100
                                                if card_num >= 0:  # Allow 0 as valid card
                                                    reward2_list.append(card_num)
                                            except ValueError:
                                                pass
                                
                                reward_entry = {
                                    'reward1': reward1_list,
                                    'reward2': reward2_list if reward2_list else None,
                                    'text': reward_text if reward_text else None
                                }
                                self.rewards[(level, round_num, button)] = reward_entry
            except Exception as e:
                print(f"ERROR loading rewards file in GameplayPage: {e}")
                import traceback
                traceback.print_exc()

        # Load bundle of shares image
        bundle_path = os.path.join("GameplayPage", "A bundle of shares.png")
        if os.path.exists(bundle_path):
            bundle_original = pygame.image.load(bundle_path).convert_alpha()
            # Scale bundle image to 50% of original size
            w, h = bundle_original.get_width(), bundle_original.get_height()
            new_size = (int(w * 0.5), int(h * 0.5))
            self.bundle_image = pygame.transform.smoothscale(bundle_original, new_size).convert_alpha()
        else:
            print("WARNING: A bundle of shares.png not found:", bundle_path)
            self.bundle_image = None

        # Load Dollar image
        dollar_path = os.path.join("GameplayPage", "Dollar.png")
        if os.path.exists(dollar_path):
            dollar_original = pygame.image.load(dollar_path).convert_alpha()
            # Scale dollar image to match bundle image proportions (50% of original)
            w, h = dollar_original.get_width(), dollar_original.get_height()
            new_size = (int(w * 0.5), int(h * 0.5))
            self.dollar_image = pygame.transform.smoothscale(dollar_original, new_size).convert_alpha()
        else:
            print("WARNING: Dollar.png not found:", dollar_path)
            self.dollar_image = None

        # Initialize quantity variables
        self.Aquantity = 2
        self.Bquantity = 0
        self.Cquantity = 0

        # Initialize price variables
        self.Aprice = 2
        self.BPrice = 2
        self.CPrice = 2

        # Initialize step variables (price change steps)
        self.StepA = 2
        self.StepB = 4
        self.StepC = 6

        # Initialize game state variables
        self.Goal = goal if goal is not None else 0  # Use passed goal or default to 0
        self.Money = 0  # Starts at 0
        self.Day = 1  # Current day/turn (starts at 1)
        
        # Apply boss modifiers to LastTurn
        # IMPORTANT: Modifiers apply ONLY during boss fight, not to regular rounds
        # After boss victory, modifiers are reset - next boss/rounds use default values
        base_last_turn = 8  # Default LastTurn value
        if self.is_boss_fight and self.boss_index is not None:
            # Boss 2 (Adam Smith) - Level 2, boss_index 0: LastTurn - 1
            if self.level_number == 2 and self.boss_index == 0:
                self.LastTurn = base_last_turn - 1  # 7 turns
            else:
                self.LastTurn = base_last_turn
        else:
            self.LastTurn = base_last_turn  # Default: 8 turns (for regular rounds and after boss victory)

        # Load End Turn button
        end_button_path = os.path.join("GameplayPage", "EndButton.png")
        if os.path.exists(end_button_path):
            end_button_original = pygame.image.load(end_button_path).convert_alpha()
            # Scale button appropriately - adjust size as needed
            button_scale = 0.3  # Adjust this value to match screenshot size
            w, h = end_button_original.get_width(), end_button_original.get_height()
            new_size = (int(w * button_scale), int(h * button_scale))
            self.end_button = pygame.transform.smoothscale(end_button_original, new_size).convert_alpha()
            # Calculate button position in bottom-right corner
            button_margin_right = 50
            button_margin_bottom = 50
            button_x = SCREEN_WIDTH - new_size[0] - button_margin_right
            button_y = SCREEN_HEIGHT - new_size[1] - button_margin_bottom
            self.end_button_rect = pygame.Rect(button_x, button_y, new_size[0], new_size[1])
        else:
            print("WARNING: EndButton.png not found:", end_button_path)
            self.end_button = None
            self.end_button_rect = None

        # Hand state and placeholder
        self.hand = 7  # initial hand size
        # Use global Dobor value (can be modified by boss rewards)
        global global_dobor
        self.Dobor = global_dobor
        placeholder_path = os.path.join("GameplayPage", "Placeholder.png")
        self.placeholder = pygame.image.load(placeholder_path).convert_alpha() if os.path.exists(placeholder_path) else None
        if self.placeholder:
            # Scale placeholder for bottom area: 138x240 (40% larger than 96x168: 30% + 10%)
            self.placeholder_bottom = pygame.transform.smoothscale(self.placeholder, (138, 240)).convert_alpha()
            # Scale placeholder for market area: also 96x168 (увеличены на 20%)
            self.placeholder_market = pygame.transform.smoothscale(self.placeholder, (96, 168)).convert_alpha()
        else:
            self.placeholder_bottom = None
            self.placeholder_market = None
        
        # Load card images
        self.card_images_original = {}  # Original card images
        self.card_images_bottom = {}  # Scaled for bottom area
        self.card_images_market = {}  # Pre-scaled for market area (for performance)
        self.card_size_bottom = (142, 244)  # 4 pixels larger than bottom placeholder (138+4, 240+4)
        self.card_size_market = (99, 171)  # 3 pixels larger than market placeholder (96+3, 168+3)
        
        # Card base mapping: which base image to use for each card
        # Cards 11, 12, 13, 14 use Card_11.png as base
        # Cards 15, 16 use Card_15.png as base
        # Cards 17, 18 use Card_17.png as base
        card_base_mapping = {}
        original_card_ids = [1, 2, 3, 4, 100]
        for card_id in original_card_ids:
            card_base_mapping[card_id] = card_id  # Original cards use their own images
        card_base_mapping[11] = 11
        card_base_mapping[12] = 11
        card_base_mapping[13] = 11
        card_base_mapping[14] = 11
        card_base_mapping[15] = 15
        card_base_mapping[16] = 15
        card_base_mapping[17] = 17
        card_base_mapping[18] = 17
        
        # Load all card images (original 1-4 and 100, plus new cards 11-14, 15-16, 17-18)
        all_card_ids = original_card_ids + [11, 12, 13, 14, 15, 16, 17, 18]
        for card_id in all_card_ids:
            base_id = card_base_mapping[card_id]
            # Try both formats: Card_X.png (with underscore) and Card X.png (with space)
            card_path_underscore = os.path.join("Cards", f"Card_{base_id}.png")
            card_path_space = os.path.join("Cards", f"Card {base_id}.png")
            
            card_path = None
            if os.path.exists(card_path_underscore):
                card_path = card_path_underscore
            elif os.path.exists(card_path_space):
                card_path = card_path_space
            
            if card_path:
                try:
                    card_img = pygame.image.load(card_path).convert_alpha()
                    # Store original
                    self.card_images_original[card_id] = card_img
                    # Pre-scale card for bottom area (larger)
                    self.card_images_bottom[card_id] = pygame.transform.smoothscale(card_img, self.card_size_bottom).convert_alpha()
                    # Pre-scale card for market area (smaller) - this prevents scaling on every frame
                    self.card_images_market[card_id] = pygame.transform.smoothscale(card_img, self.card_size_market).convert_alpha()
                    print(f"Loaded card {card_id} (base: {base_id}) from {card_path}")
                except Exception as e:
                    print(f"ERROR loading card {card_id} (base: {base_id}): {e}")
                    self.card_images_original[card_id] = None
                    self.card_images_bottom[card_id] = None
                    self.card_images_market[card_id] = None
            else:
                print(f"WARNING: Card file not found for card {card_id} (base: {base_id}). Tried: {card_path_underscore} and {card_path_space}")
                self.card_images_original[card_id] = None
                self.card_images_bottom[card_id] = None
                self.card_images_market[card_id] = None
        
        # Initialize CardAction system: dictionary mapping card_id to CardAction value
        # Cards 11, 12: CardAction = 2
        # Cards 13, 14: CardAction = 4
        # Cards 15, 16: CardAction = -2
        # Cards 17, 18: CardAction = 2
        self.card_actions = {}
        self.card_actions[11] = 2
        self.card_actions[12] = 2
        self.card_actions[13] = 4
        self.card_actions[14] = 4
        self.card_actions[15] = -2
        self.card_actions[16] = -2
        self.card_actions[17] = 2
        self.card_actions[18] = 2
        
        # Initialize CardTurns system: dictionary mapping card_id to CardTurns value
        # Cards 11, 13: CardTurns = 1
        # Cards 12, 14: CardTurns = 2
        # Card 15: CardTurns = 1
        # Card 16: CardTurns = 2
        # Card 17: CardTurns = 1
        # Card 18: CardTurns = 2
        self.card_turns = {}
        self.card_turns[11] = 1
        self.card_turns[13] = 1
        self.card_turns[12] = 2
        self.card_turns[14] = 2
        self.card_turns[15] = 1
        self.card_turns[16] = 2
        self.card_turns[17] = 1
        self.card_turns[18] = 2
        
        # Initialize deck based on level
        self.deck = self._get_initial_deck(self.level_number)
        # Safety net: if something still produced card 0 (old save, legacy rewards), map it to 100
        self.deck = [100 if c == 0 else c for c in self.deck]
        # Shuffle deck
        random.shuffle(self.deck)
        
        # Deal cards to hand (first 7 cards from deck, 8th stays in deck) - keep fixed slots length
        initial_hand = self.deck[:self.hand] if len(self.deck) >= self.hand else self.deck.copy()
        self.hand_cards = [None] * self.hand
        for idx, card_id in enumerate(initial_hand):
            if idx < self.hand:
                self.hand_cards[idx] = 100 if card_id == 0 else card_id
        # Remove dealt cards from deck
        self.deck = self.deck[self.hand:] if len(self.deck) > self.hand else []
        
        # Drag and drop state
        self.dragged_card_index = None  # Index of card being dragged, or None
        self.drag_offset = (0, 0)  # Offset from mouse to card top-left corner
        self.dragged_card_pos = (0, 0)  # Current position of dragged card
        self.dragged_card_source = None  # 'hand' or 'market'
        self.dragged_card_market = None  # market index when dragging from market
        self.dragged_card_market_slot = None  # slot index when dragging from market

        # Card draw state
        self.pending_draws = 0  # Cards to draw after end-turn animations finish
        
        # Market placeholders positions (for drop detection)
        self.market_placeholders = []  # Will be populated in draw method: [{'market': 0-2, 'slot': 0-2, 'rect': Rect}]
        # Bottom hand placeholders positions
        self.bottom_placeholders = []  # Populated in draw: [{'slot': int, 'rect': Rect}]
        
        # Cards placed on market placeholders: {market: {slot: card_id}}
        self.market_cards = {0: {}, 1: {}, 2: {}}  # Store cards on market placeholders
        # Original hand slot for each card on market: {market: {slot: hand_index}}
        self.market_card_origins = {0: {}, 1: {}, 2: {}}
        # Locked state for market cards after end turn: {market: {slot: bool}}
        self.market_cards_locked = {0: {}, 1: {}, 2: {}}
        # CardTurns tracking for cards on market: {market: {slot: turns_remaining}}
        self.market_card_turns = {0: {}, 1: {}, 2: {}}

        # Card jump animation state for cards 11-18: {market: {slot: {'offset_y': float, 'velocity': float, 'start_time': int}}}
        self.card_jump_animations = {0: {}, 1: {}, 2: {}}
        
        # Queue for processing cards 11-18 sequentially: list of (market, slot) tuples
        self.cards_11_14_queue = []
        self.current_card_processing = None  # (market, slot) currently being processed
        self.card_processing_start_time = 0
        self.card_processing_delay = 300  # ms delay between processing each card

        # Hand compaction animation state (after end turn)
        self.hand_compact_anim = []  # [{'card_id', 'from_index', 'to_index', 'from_pos', 'to_pos', 'progress'}]
        self.hand_compact_target_hand = None  # final hand_cards order after compaction
        self.hand_compact_draw_count = 0  # how many cards to draw after compaction
        self.hand_compact_start_time = 0
        self.hand_compact_duration = 300  # ms
        
        # Hand draw animation state (cards flying in from bottom of screen)
        self.hand_draw_anim = []  # [{'card_id', 'target_slot', 'target_pos', 'from_pos', 'progress'}]
        self.hand_draw_start_time = 0
        self.hand_draw_duration = 400  # ms
        
        # Win/Lose state
        self.win_lose_state = None  # None, "win", or "lose"
        self.ok_button_rect = None  # Will be calculated in draw method
        
        # Load WinLose.png
        winlose_path = os.path.join("GameplayPage", "WinLose.png")
        if os.path.exists(winlose_path):
            winlose_original = pygame.image.load(winlose_path).convert_alpha()
            # Scale to 1/3 of screen size (3 times smaller)
            winlose_width = SCREEN_WIDTH // 3
            winlose_height = SCREEN_HEIGHT // 3
            self.win_lose_image = pygame.transform.smoothscale(winlose_original, (winlose_width, winlose_height)).convert_alpha()
            # Calculate centered position
            self.win_lose_x = (SCREEN_WIDTH - winlose_width) // 2
            # Use float positions + dt-based movement for smooth sliding
            self.win_lose_y = float(-winlose_height)  # Start off-screen at top
            self.win_lose_target_y = float((SCREEN_HEIGHT - winlose_height) // 2)  # Centered vertically
            self.win_lose_speed_pps = 1200.0  # pixels per second
            self._winlose_last_tick = pygame.time.get_ticks()
        else:
            print("WARNING: WinLose.png not found:", winlose_path)
            self.win_lose_image = None
            self.win_lose_x = 0
            self.win_lose_y = 0.0
            self.win_lose_target_y = 0
            self.win_lose_speed_pps = 0.0
            self._winlose_last_tick = pygame.time.get_ticks()
        
        # Load Ok1.png button (for win)
        ok1_path = os.path.join("GameplayPage", "Ok1.png")
        if os.path.exists(ok1_path):
            ok1_original = pygame.image.load(ok1_path).convert_alpha()
            # Scale button larger - make it more visible
            ok_scale = 1.0  # Full size or larger
            w, h = ok1_original.get_width(), ok1_original.get_height()
            ok_size = (int(w * ok_scale), int(h * ok_scale))
            self.ok1_button = pygame.transform.smoothscale(ok1_original, ok_size).convert_alpha()
            self.ok_button_base_size = ok_size
        else:
            print("WARNING: Ok1.png not found:", ok1_path)
            self.ok1_button = None
        
        # Load Ok2.png button (for lose)
        ok2_path = os.path.join("GameplayPage", "Ok2.png")
        if os.path.exists(ok2_path):
            ok2_original = pygame.image.load(ok2_path).convert_alpha()
            # Scale button larger - make it more visible
            ok_scale = 1.0  # Full size or larger
            w, h = ok2_original.get_width(), ok2_original.get_height()
            ok_size = (int(w * ok_scale), int(h * ok_scale))
            self.ok2_button = pygame.transform.smoothscale(ok2_original, ok_size).convert_alpha()
            # Use same size for both buttons
            if not hasattr(self, 'ok_button_base_size'):
                self.ok_button_base_size = ok_size
        else:
            print("WARNING: Ok2.png not found:", ok2_path)
            self.ok2_button = None
        
        # Set ok_button_base_size if not set
        if not hasattr(self, 'ok_button_base_size'):
            self.ok_button_base_size = (0, 0)
        
        # Store last earned reward cards for WinLose window display
        self.last_earned_cards = []  # List of card numbers earned in this round
        
        # Load WinLose window texts from Lang.csv
        self.reward_window_text = get_text("RewardWindowText", "RewardWindowText")
        self.reward_final_boss_text = get_text("RewardFinalBoss", "RewardWindowText")
        self.lose_window_text = get_text("LoseWindowText", "LoseWindowText")
        
        # Cache for WinLose window reward card images
        self.winlose_card_images = {}
    
    def _load_winlose_card(self, card_number):
        """Load and cache a reward card image for WinLose window. For cards 11-18, uses base card and draws CardAction/CardTurns."""
        # Safety net: legacy configs may still reference card 0
        if card_number == 0:
            card_number = 100
        if card_number in self.winlose_card_images:
            return self.winlose_card_images[card_number]
        
        # Target size for WinLose window - increased size
        target_width = 100
        # Calculate height to maintain same aspect ratio as market cards (99x171)
        market_card_ratio = 99 / 171.0
        target_height = int(target_width / market_card_ratio)
        
        # Get base card ID
        if card_number in (1, 2, 3, 4, 100):
            # Base cards use their own images
            base_card_id = card_number
        elif card_number in [11, 12, 13, 14]:
            base_card_id = 11
        elif card_number in [15, 16]:
            base_card_id = 15
        elif card_number in [17, 18]:
            base_card_id = 17
        else:
            base_card_id = card_number
        
        card_path = os.path.join("Cards", f"Card_{base_card_id}.png")
        if not os.path.exists(card_path):
            print(f"WARNING: WinLose card base not found: {card_path}")
            self.winlose_card_images[card_number] = None
            return None
        
        # Load base card image
        card_image = pygame.image.load(card_path).convert_alpha()
        
        # Scale to final WinLose size
        card_surface = pygame.transform.smoothscale(card_image, (target_width, target_height)).convert_alpha()
        
        # Draw CardAction and CardTurns if this card has them
        if card_number in self.card_actions or card_number in self.card_turns:
            # Draw CardAction
            if card_number in self.card_actions:
                action_value = self.card_actions[card_number]
                self._draw_winlose_card_action(card_surface, action_value, card_number, target_width, target_height)
            
            # Draw CardTurns
            if card_number in self.card_turns:
                turns_value = self.card_turns[card_number]
                self._draw_winlose_card_turns(card_surface, turns_value, card_number, target_width, target_height)
        
        self.winlose_card_images[card_number] = card_surface
        return card_surface
    
    def _draw_winlose_card_action(self, surface, action_value, card_id, card_width, card_height):
        """Draw CardAction value on a WinLose card surface"""
        base_market_width = 99
        scale_factor = card_width / base_market_width
        base_font_size = 36
        scaled_font_size = int(base_font_size * 0.85 * 0.9 * scale_factor)
        if scaled_font_size < 1:
            scaled_font_size = 1
        
        gadugib_path = "Gadugib.ttf"
        if os.path.exists(gadugib_path):
            font_path_use = gadugib_path
        else:
            font_path_use = self.font_path
        
        try:
            font = pygame.font.Font(font_path_use, scaled_font_size)
            action_text = font.render(str(action_value), True, PAPER_COLOR)
            
            plus_x = card_width - 25 * scale_factor
            plus_y = 10 * scale_factor
            action_x = plus_x - 29 * scale_factor
            action_y = plus_y + 14 * scale_factor
            
            if card_id in (15, 16):
                action_x -= 11 * scale_factor
            
            surface.blit(action_text, (int(action_x), int(action_y)))
        except Exception as e:
            print(f"ERROR drawing CardAction on WinLose card: {e}")
    
    def _draw_winlose_card_turns(self, surface, turns_value, card_id, card_width, card_height):
        """Draw CardTurns value on a WinLose card surface"""
        base_market_width = 99
        scale_factor = card_width / base_market_width
        base_font_size = 36
        card_action_font_size = int(base_font_size * 0.85 * 0.9 * scale_factor)
        turns_font_size = int(card_action_font_size * 0.648)
        if turns_font_size < 1:
            turns_font_size = 1
        
        gadugib_path = "Gadugib.ttf"
        if os.path.exists(gadugib_path):
            font_path_use = gadugib_path
        else:
            font_path_use = self.font_path
        
        try:
            font = pygame.font.Font(font_path_use, turns_font_size)
            turns_text = font.render(str(turns_value), True, PAPER_COLOR)
            
            base_bottom_height = 244.0
            height_scale = card_height / base_bottom_height if base_bottom_height > 0 else 1.0
            offset_from_bottom = 75.0 * height_scale
            
            card_center_x = card_width / 2
            turns_x = card_center_x + 10 * scale_factor
            turns_y = card_height - offset_from_bottom
            
            if card_id in (17, 18):
                base_market_width_for_adjust = 99.0
                base_market_height_for_adjust = 171.0
                x_scale = card_width / base_market_width_for_adjust if base_market_width_for_adjust else 1.0
                y_scale = card_height / base_market_height_for_adjust if base_market_height_for_adjust else 1.0
                turns_x -= 7.0 * x_scale
                turns_y += 2.0 * y_scale
            
            surface.blit(turns_text, (int(turns_x), int(turns_y)))
        except Exception as e:
            print(f"ERROR drawing CardTurns on WinLose card: {e}")
    
    def _get_initial_deck(self, level_number):
        """Get initial deck composition for a given level"""
        global earned_reward_cards
        
        if level_number == 1:
            # Level 1 deck: 100, 1 (x2), 2, 3, 4, 11
            base_deck = [100, 1, 1, 2, 3, 4, 11]
        elif level_number == 2:
            # Level 2 deck: level 1 set + one extra card 12
            base_deck = [100, 1, 1, 2, 3, 4, 11, 12]
        else:
            # Default deck for other levels: Card 100 (2x), Card 1 (2x), Card 2 (1x), Card 3 (2x), Card 4 (1x), Cards 11-14 (1x each), Cards 15-16 (1x each), Cards 17-18 (1x each)
            base_deck = [100, 100, 1, 1, 2, 3, 3, 4, 11, 12, 13, 14, 15, 16, 17, 18]
        
        # Add earned reward cards for this level
        earned_cards = earned_reward_cards.get(level_number, [])
        if earned_cards:
            base_deck.extend(earned_cards)
            print(f"Added {len(earned_cards)} earned reward card(s) to level {level_number} deck: {earned_cards}")

        # Safety net: old saves/configs may still reference card 0; map it to 100.
        base_deck = [100 if c == 0 else c for c in base_deck]
        
        return base_deck
    
    def handle_input(self):
        mouse_pos = pygame.mouse.get_pos()
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"
            
            # Handle Ok button click if WinLose screen is shown
            if self.win_lose_state is not None and self.win_lose_image:
                # Determine which button to show based on win/lose state
                ok_button = None
                if self.win_lose_state == "win" and self.ok1_button:
                    ok_button = self.ok1_button
                elif self.win_lose_state == "lose" and self.ok2_button:
                    ok_button = self.ok2_button
                
                if ok_button:
                    # Use ok_button_rect from draw method (calculated there)
                    # If not set yet, calculate it (same calculation as in draw method)
                    if not hasattr(self, 'ok_button_rect') or self.ok_button_rect is None:
                        winlose_width = self.win_lose_image.get_width()
                        winlose_height = self.win_lose_image.get_height()
                        ok_margin_right = 30
                        ok_margin_bottom = 30
                        ok_x = self.win_lose_x + winlose_width - self.ok_button_base_size[0] - ok_margin_right
                        win_lose_y_draw = int(round(self.win_lose_y))
                        ok_y = win_lose_y_draw + winlose_height - self.ok_button_base_size[1] - ok_margin_bottom
                        self.ok_button_rect = pygame.Rect(int(ok_x), int(ok_y), self.ok_button_base_size[0], self.ok_button_base_size[1])
                    
                    if event.type == pygame.MOUSEBUTTONDOWN:
                        if event.button == 1:  # Left click
                            # Check if click is on Ok button
                            if self.ok_button_rect.collidepoint(event.pos):
                                print(f"Ok button clicked! State: {self.win_lose_state}, Button: {'Ok1' if self.win_lose_state == 'win' else 'Ok2'}")
                                if self.win_lose_state == "lose":
                                    # Lost: return to level selection screen
                                    print("Returning to level_select")
                                    return "level_select"
                                elif self.win_lose_state == "win":
                                    # Won: return to round selection (boss victory handling is done in main loop)
                                    # The main loop will check if it's a boss fight and handle level 1 boss defeat
                                    print("Returning to round_select")
                                    return "round_select"
                            else:
                                # Debug: print click position and button rect
                                print(f"WinLose screen active. Click at: {event.pos}, Ok button rect: {self.ok_button_rect if hasattr(self, 'ok_button_rect') else 'None'}, win_lose_y: {self.win_lose_y}, State: {self.win_lose_state}")
                    
                    # Skip other events when WinLose screen is shown (but allow QUIT and MOUSEBUTTONDOWN which are handled above)
                    if event.type != pygame.QUIT and event.type != pygame.MOUSEBUTTONDOWN:
                        continue
            
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return "back"
            
            # Handle drag and drop
            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # Left click
                    # Check if clicking on a card in hand (only if not already dragging)
                    if self.dragged_card_index is None:
                        # Calculate hand card positions (same spacing pattern as market placeholders, но плотнее)
                        if self.bottom_frame and self.hand > 0:
                            bf_w = self.bottom_frame.get_width()
                            bf_h = self.bottom_frame.get_height()
                            bf_x = (SCREEN_WIDTH - bf_w) // 2 - 200
                            bf_y = SCREEN_HEIGHT - bf_h - 150
                            
                            ph_w = 138  # Bottom placeholder width (40% larger)
                            ph_h = 240  # Bottom placeholder height (40% larger)
                            # Equal spacing, но немного уплотнённые (меньше промежутков)
                            base_spacing = (bf_w - ph_w * self.hand) / (self.hand + 1)
                            spacing = base_spacing * 0.7
                            total_width = ph_w * self.hand + spacing * (self.hand - 1)
                            start_x = bf_x + (bf_w - total_width) / 2
                            start_y = bf_y + (bf_h - ph_h) // 2
                            
                            # Check if clicking on a card
                            for i in range(self.hand):
                                if i >= len(self.hand_cards) or self.hand_cards[i] is None:
                                    continue
                                slot_x = start_x + i * (ph_w + spacing)
                                slot_y = start_y
                                card_rect = pygame.Rect(slot_x - 2, slot_y - 2, self.card_size_bottom[0], self.card_size_bottom[1])
                                if card_rect.collidepoint(mouse_pos):
                                    self.dragged_card_index = i
                                    self.drag_offset = (mouse_pos[0] - slot_x, mouse_pos[1] - slot_y)
                                    self.dragged_card_pos = mouse_pos
                                    self.dragged_card_source = "hand"
                                    break
                    # Check if clicking a card on market placeholders (only if not already dragging)
                    if self.dragged_card_index is None:
                        for ph_info in self.market_placeholders:
                            market = ph_info["market"]
                            slot = ph_info["slot"]
                            if slot in self.market_cards[market] and self.market_cards[market][slot] is not None:
                                # Skip cards, которые уже заблокированы после конца хода
                                if self.market_cards_locked[market].get(slot):
                                    continue
                                # Only allow dragging the last (rightmost) card in this market
                                occupied_slots = [s for s, cid in self.market_cards[market].items() if cid is not None]
                                if not occupied_slots:
                                    continue
                                last_slot = max(occupied_slots)
                                if slot != last_slot:
                                    continue
                                if ph_info["rect"].collidepoint(mouse_pos):
                                    self.dragged_card_index = None  # not used for market
                                    self.dragged_card_source = "market"
                                    self.dragged_card_market = market
                                    self.dragged_card_market_slot = slot
                                    self.drag_offset = (mouse_pos[0] - ph_info["rect"].x, mouse_pos[1] - ph_info["rect"].y)
                                    self.dragged_card_pos = mouse_pos
                                    break
                    
                    # Only process arrows/buttons if not dragging a card
                    if self.dragged_card_index is None:
                        mouse_pos = event.pos
                        for entry in self.arrow_entries:
                            if not entry["rect"].collidepoint(mouse_pos):
                                continue
                            
                            frame_idx = entry.get("frame_index")
                            if frame_idx is None:
                                continue
                            
                            # Top arrow (arrow_type == 0) - Buy maximum shares with available money
                            if entry.get("arrow_type") == 0:
                                # Determine which market and get price
                                price = None
                                if frame_idx == 0:  # Market A
                                    price = self.Aprice
                                elif frame_idx == 1:  # Market B
                                    price = self.BPrice
                                elif frame_idx == 2:  # Market C
                                    price = self.CPrice
                                
                                if price and price > 0:
                                    # Calculate how many shares we can buy
                                    shares_to_buy = self.Money // price
                                    if shares_to_buy > 0:
                                        # Calculate cost
                                        cost = shares_to_buy * price
                                        # Update money
                                        self.Money -= cost
                                        # Check win/lose conditions
                                        self._check_win_lose()
                                        # Update quantity in corresponding market
                                        if frame_idx == 0:
                                            self.Aquantity += shares_to_buy
                                        elif frame_idx == 1:
                                            self.Bquantity += shares_to_buy
                                        elif frame_idx == 2:
                                            self.Cquantity += shares_to_buy
                            
                            # Second arrow from top (arrow_type == 1) - Buy ONE share in THIS market
                            elif entry.get("arrow_type") == 1:
                                # Determine which market and get price
                                price = None
                                if frame_idx == 0:  # Market A
                                    price = self.Aprice
                                elif frame_idx == 1:  # Market B
                                    price = self.BPrice
                                elif frame_idx == 2:  # Market C
                                    price = self.CPrice
                                
                                if price and price > 0 and self.Money >= price:
                                    # Buy one share
                                    self.Money -= price
                                    # Check win/lose conditions
                                    self._check_win_lose()
                                    if frame_idx == 0:
                                        self.Aquantity += 1
                                    elif frame_idx == 1:
                                        self.Bquantity += 1
                                    elif frame_idx == 2:
                                        self.Cquantity += 1
                            
                            # Third arrow from top (arrow_type == 2) - Sell ONE share from THIS market
                            elif entry.get("arrow_type") == 2:
                                # Determine which market and sell one share
                                if frame_idx == 0:  # Market A
                                    if self.Aquantity > 0:
                                        self.Money += self.Aprice
                                        self.Aquantity -= 1
                                        # Check win/lose conditions
                                        self._check_win_lose()
                                elif frame_idx == 1:  # Market B
                                    if self.Bquantity > 0:
                                        self.Money += self.BPrice
                                        self.Bquantity -= 1
                                        # Check win/lose conditions
                                        self._check_win_lose()
                                elif frame_idx == 2:  # Market C
                                    if self.Cquantity > 0:
                                        self.Money += self.CPrice
                                        self.Cquantity -= 1
                                        # Check win/lose conditions
                                        self._check_win_lose()
                            
                            # Bottom arrow (arrow_type == 3) - Sell all shares from THIS market only
                            elif entry.get("arrow_type") == 3:
                                # Determine which market and sell only its shares
                                if frame_idx == 0:  # Market A
                                    total_money = self.Aquantity * self.Aprice
                                    self.Money += total_money
                                    self.Aquantity = 0
                                    # Check win/lose conditions
                                    self._check_win_lose()
                                elif frame_idx == 1:  # Market B
                                    total_money = self.Bquantity * self.BPrice
                                    self.Money += total_money
                                    self.Bquantity = 0
                                    # Check win/lose conditions
                                    self._check_win_lose()
                                elif frame_idx == 2:  # Market C
                                    total_money = self.Cquantity * self.CPrice
                                    self.Money += total_money
                                    self.Cquantity = 0
                                    # Check win/lose conditions
                                    self._check_win_lose()
                            
                            # Start animation (if entry has frames)
                            if entry.get("frames"):
                                entry["animating"] = True
                                entry["idx"] = 0
                                entry["last"] = pygame.time.get_ticks()
                                if self.arrow_sound:
                                    self.arrow_sound.play()
                            break
                    
                    # Check if End Turn button was clicked (outside arrow loop)
                    if self.end_button_rect and self.end_button_rect.collidepoint(mouse_pos):
                        # Don't allow EndTurn if price animation is in progress
                        if self.current_price_animation is not None:
                            break
                        
                        # Play sound
                        if self.arrow_sound:
                            self.arrow_sound.play()
                        # Calculate price changes based on probability distributions
                        animation_queue = self.update_stock_prices()
                        # Lock all currently played market cards for future turns
                        self._lock_market_cards()
                        # Queue animations for markets
                        if animation_queue:
                            self.price_animation_queue = animation_queue.copy()
                            # Start first animation if queue is not empty
                            if self.price_animation_queue:
                                next_anim = self.price_animation_queue.pop(0)
                                # Apply price change when animation starts
                                self._apply_price_change(next_anim['market'], next_anim['price_change'])
                                self.current_price_animation = {
                                    'market': next_anim['market'],
                                    'type': next_anim['type'],
                                    'frame_idx': 0,
                                    'last_update': pygame.time.get_ticks()
                                }
                                # Play sound for first animation
                                if self.typewriter_sound:
                                    self.typewriter_sound.play()
                        else:
                            # No animations needed, increment day immediately
                            # CRITICAL: Check win/lose conditions BEFORE changing day
                            # If Day == LastTurn, game MUST end here
                            self._check_win_lose()
                            
                            # If game ended, stop here - don't change day
                            if self.win_lose_state is not None:
                                # Game ended, don't do anything else
                                pass
                            elif self.Day < self.LastTurn:
                                # Game continues, increment day
                                self.Day += 1
                                # Check again after increment (in case we won on this turn)
                                self._check_win_lose()
                            else:
                                # Day == LastTurn but game didn't end - FORCE END
                                print(f"ERROR: Day==LastTurn but game didn't end! Forcing end.")
                                if self.Money >= self.Goal:
                                    self.win_lose_state = "win"
                                else:
                                    self.win_lose_state = "lose"
                                    # Reset earned cards for this level when player loses
                                    self._reset_earned_cards_for_level()
                                if self.win_lose_image:
                                    winlose_height = self.win_lose_image.get_height()
                                    self.win_lose_y = float(-winlose_height)
                            # Draw cards that were delayed until animations finished
                            self._draw_pending_cards()
                        break  # Exit event processing after button click
            
            # MOUSEMOTION events are handled in run() loop for smoother updates
            
            if event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1 and (self.dragged_card_index is not None or self.dragged_card_source == "market"):
                    # Try to drop card on market placeholder
                    dropped = False
                    for ph_info in self.market_placeholders:
                        if ph_info['rect'].collidepoint(event.pos):
                            # Drop card on market placeholder
                            market = ph_info['market']
                            slot = ph_info['slot']
                            # If slot is already occupied, skip (except for original source slot when dragging from market)
                            if not (
                                self.dragged_card_source == "market"
                                and market == self.dragged_card_market
                                and slot == self.dragged_card_market_slot
                            ):
                                if slot in self.market_cards[market] and self.market_cards[market][slot] is not None:
                                    continue
                            # Moving from hand to market
                            if self.dragged_card_source == "hand" and self.dragged_card_index is not None:
                                # Only allow drop to the FIRST free placeholder of this market
                                # (index of the first empty slot or None if market full)
                                first_free = None
                                for s in range(3):
                                    if self.market_cards[market].get(s) is None:
                                        first_free = s
                                        break
                                if first_free is None or slot != first_free:
                                    continue
                                if self.dragged_card_index < len(self.hand_cards):
                                    card_id = self.hand_cards[self.dragged_card_index]
                                    if card_id is not None:
                                        self.market_cards[market][slot] = card_id
                                        # Remember original hand slot for this market card
                                        self.market_card_origins[market][slot] = self.dragged_card_index
                                        # Новая сыгранная карта пока НЕ заблокирована
                                        self.market_cards_locked[market][slot] = False
                                        # Initialize CardTurns for cards 11-18
                                        if card_id in self.card_turns:
                                            self.market_card_turns[market][slot] = self.card_turns[card_id]
                                        # Remove from hand slot
                                        self.hand_cards[self.dragged_card_index] = None
                                        # Mark pending draw for empty slot
                                        self.pending_draws += 1
                                        dropped = True
                                        break
                            # Moving from market to market
                            elif self.dragged_card_source == "market":
                                src_market = self.dragged_card_market
                                src_slot = self.dragged_card_market_slot
                                # If dropping back onto the same placeholder, do nothing (just cancel drag)
                                if market == src_market and slot == src_slot:
                                    dropped = True
                                    break
                                # Only allow drop to FIRST free placeholder of other markets
                                if market == src_market:
                                    continue
                                first_free = None
                                for s in range(3):
                                    if self.market_cards[market].get(s) is None:
                                        first_free = s
                                        break
                                if first_free is None or slot != first_free:
                                    continue
                                card_id = self.market_cards[src_market].get(src_slot)
                                if card_id is not None:
                                    self.market_cards[market][slot] = card_id
                                    self.market_cards[src_market][src_slot] = None
                                    # Move origin info along with the card
                                    origin_slot = self.market_card_origins[src_market].pop(src_slot, None)
                                    if origin_slot is not None:
                                        self.market_card_origins[market][slot] = origin_slot
                                    # Переносим флаг заблокированности вместе с картой
                                    locked_flag = self.market_cards_locked[src_market].pop(src_slot, False)
                                    self.market_cards_locked[market][slot] = locked_flag
                                    # Move CardTurns along with the card
                                    turns = self.market_card_turns[src_market].pop(src_slot, None)
                                    if turns is not None:
                                        self.market_card_turns[market][slot] = turns
                                    dropped = True
                                    break
                    # Try to drop card on hand placeholder (return or move to another hand slot)
                    if not dropped:
                        for ph_info in self.bottom_placeholders:
                            if ph_info['rect'].collidepoint(event.pos):
                                slot = ph_info['slot']
                                # From hand to another hand slot (reposition)
                                if self.dragged_card_source == "hand" and self.dragged_card_index is not None:
                                    # Only drop if target slot is empty
                                    if self.hand_cards[slot] is None:
                                        card_id = self.hand_cards[self.dragged_card_index]
                                        if card_id is not None:
                                            self.hand_cards[slot] = card_id
                                            self.hand_cards[self.dragged_card_index] = None
                                            dropped = True
                                            break
                                # From market back to hand
                                elif self.dragged_card_source == "market":
                                    # Only allow drop to the ORIGINAL hand slot of this card
                                    src_market = self.dragged_card_market
                                    src_slot = self.dragged_card_market_slot
                                    origin_slot = self.market_card_origins[src_market].get(src_slot)
                                    if origin_slot is not None and slot == origin_slot and self.hand_cards[slot] is None:
                                        card_id = self.market_cards[src_market].get(src_slot)
                                        if card_id is not None:
                                            self.hand_cards[slot] = card_id
                                            self.market_cards[src_market][src_slot] = None
                                            # Clear origin mapping
                                            self.market_card_origins[src_market].pop(src_slot, None)
                                            # Слот на рынке освобождается и больше не заблокирован
                                            self.market_cards_locked[src_market].pop(src_slot, None)
                                            # Clear CardTurns when card returns to hand
                                            self.market_card_turns[src_market].pop(src_slot, None)
                                            if self.pending_draws > 0:
                                                self.pending_draws -= 1
                                            dropped = True
                                            break
                    # Reset drag state (even if not dropped, card returns to source)
                    self.dragged_card_index = None
                    self.dragged_card_source = None
                    self.dragged_card_market = None
                    self.dragged_card_market_slot = None
                    self.drag_offset = (0, 0)
        
        return None
    
    def _check_win_lose(self):
        """Check win/lose conditions and trigger WinLose screen if needed"""
        # Don't check if already in win/lose state
        if self.win_lose_state is not None:
            return
        
        # CRITICAL: If Day == LastTurn, game MUST end (either win or lose)
        if self.Day == self.LastTurn:
            if self.Money >= self.Goal:
                # WIN: Money >= Goal on LastTurn
                self.win_lose_state = "win"
                if self.is_final_boss:
                    self.reward_window_text = self.reward_final_boss_text
                if self.win_lose_image:
                    winlose_height = self.win_lose_image.get_height()
                    self.win_lose_y = float(-winlose_height)
                print(f"WIN on LastTurn: Money={self.Money}, Goal={self.Goal}, Day={self.Day}, LastTurn={self.LastTurn}")
                # Add reward card to deck
                self._add_reward_card_to_deck()
            else:
                # LOSE: Money < Goal on LastTurn
                self.win_lose_state = "lose"
                # Reset earned cards for this level when player loses
                self._reset_earned_cards_for_level()
                if self.win_lose_image:
                    winlose_height = self.win_lose_image.get_height()
                    self.win_lose_y = float(-winlose_height)
                print(f"LOSE on LastTurn: Money={self.Money}, Goal={self.Goal}, Day={self.Day}, LastTurn={self.LastTurn}")
            return
        
        # Check win condition for other days (can win early)
        if self.Money >= self.Goal:
            self.win_lose_state = "win"
            if self.is_final_boss:
                self.reward_window_text = self.reward_final_boss_text
            if self.win_lose_image:
                winlose_height = self.win_lose_image.get_height()
                self.win_lose_y = float(-winlose_height)
            print(f"WIN (early): Money={self.Money}, Goal={self.Goal}, Day={self.Day}, LastTurn={self.LastTurn}")
            # Add reward card to deck
            self._add_reward_card_to_deck()
            return
    
    def _add_reward_card_to_deck(self):
        """Add reward card to global earned cards list after winning a round, or apply boss reward for boss fights"""
        global earned_reward_cards
        
        # Check if this is a boss fight - if so, apply boss reward instead of regular card reward
        if self.is_boss_fight and self.boss_index is not None:
            boss_number = get_boss_number_from_index(self.level_number, self.boss_index)
            if boss_number:
                boss_rewards = load_boss_rewards()
                reward_string = boss_rewards.get(boss_number)
                if reward_string:
                    apply_boss_reward(reward_string, self)
                    print(f"Applied boss reward for boss {boss_number} (level {self.level_number}, index {self.boss_index}): {reward_string}")
                else:
                    print(f"No boss reward found for boss {boss_number} (level {self.level_number}, index {self.boss_index})")
            
            # IMPORTANT: After boss victory, reset earned cards for this level - deck returns to initial state
            # Only boss reward (like Dobor) is preserved, not the cards earned in rounds
            if self.level_number in earned_reward_cards:
                earned_reward_cards[self.level_number] = []
                print(f"Reset earned cards for level {self.level_number} after boss victory - deck returns to initial state")
            
            return  # Boss rewards are applied, no card reward
        
        # Regular round reward (card)
        # Use provided round_num if available, otherwise fallback to difficulty-based logic
        if self.round_num is not None:
            round_num = self.round_num
        else:
            # Fallback: "e" = round 1, "m" = round 2, "h" = round 3
            round_num = 1 if self.difficulty == "e" else (2 if self.difficulty == "m" else 3)
        button = self.difficulty.upper()  # "E", "M", or "H"
        
        # Look up reward data
        reward_key = (self.level_number, round_num, button)
        reward_data = self.rewards.get(reward_key)
        
        if reward_data:
            reward1_list = reward_data.get('reward1', [])
            reward2 = reward_data.get('reward2')  # Can be list or None
            
            # Check if Reward2 is a list
            reward2_list = reward2 if isinstance(reward2, list) else ([reward2] if reward2 is not None else [])
            
            if reward1_list:
                # Randomly select one card from Reward1
                reward_card_number1 = random.choice(reward1_list)
                if reward_card_number1 == 0:
                    reward_card_number1 = 100
                
                # Initialize list for this level if it doesn't exist
                if self.level_number not in earned_reward_cards:
                    earned_reward_cards[self.level_number] = []
                
                # Add reward card from Reward1 to earned cards for this level
                earned_reward_cards[self.level_number].append(reward_card_number1)
                # Store last earned card for WinLose window display
                self.last_earned_cards.append(reward_card_number1)
                
                # Add reward card from Reward2 if present (randomly select one card if it's a list)
                if reward2_list:
                    reward_card_number2 = random.choice(reward2_list)
                    if reward_card_number2 == 0:
                        reward_card_number2 = 100
                    earned_reward_cards[self.level_number].append(reward_card_number2)
                    self.last_earned_cards.append(reward_card_number2)
                    print(f"Earned reward cards {reward_card_number1} (from Reward1) and {reward_card_number2} (from Reward2) for level {self.level_number}, round {round_num}, button {button}")
                else:
                    print(f"Earned reward card {reward_card_number1} (randomly selected from {reward1_list}) for level {self.level_number}, round {round_num}, button {button}")
                
                print(f"Earned cards for level {self.level_number}: {earned_reward_cards[self.level_number]}")
            else:
                print(f"No reward cards in Reward1 for level {self.level_number}, round {round_num}, button {button}")
        else:
            print(f"No reward data found for level {self.level_number}, round {round_num}, button {button}")
    
    def _reset_earned_cards_for_level(self):
        """Reset earned reward cards for current level when player loses"""
        global earned_reward_cards, global_dobor
        if self.level_number in earned_reward_cards:
            earned_reward_cards[self.level_number] = []
            print(f"Reset earned cards for level {self.level_number} due to defeat")
        # Reset Dobor to default value (1) when player loses
        global_dobor = 1
        self.Dobor = 1
        print(f"Reset Dobor to 1 due to defeat")
    
    def update_win_lose_animation(self):
        """Update WinLose screen slide animation"""
        if self.win_lose_state is None or not self.win_lose_image:
            return

        # dt-based slide from top (smooth regardless of FPS)
        now = pygame.time.get_ticks()
        dt = (now - getattr(self, "_winlose_last_tick", now)) / 1000.0
        self._winlose_last_tick = now
        dt = _clamp_dt_seconds(dt)

        max_delta = float(getattr(self, "win_lose_speed_pps", 0.0)) * dt
        self.win_lose_y = move_towards(float(self.win_lose_y), float(self.win_lose_target_y), max_delta)

    def update_stock_prices(self):
        """Calculate price changes based on probability distributions after EndTurn.
        Returns list of {'market': 0-2, 'type': 'unchanged'|'rise'|'fall', 'price_change': int} 
        Prices are NOT updated here - they will be updated when animation starts."""
        animation_queue = []
        
        # Stock A: 15% no change, 85% price increases
        rand_a = random.random() * 100  # 0-100
        if rand_a <= 15:
            # Price stays the same - add to animation queue
            animation_queue.append({'market': 0, 'type': 'unchanged', 'price_change': 0})
        else:  # 85% - price increases
            animation_queue.append({'market': 0, 'type': 'rise', 'price_change': self.StepA})
        
        # Stock B: 10% price decreases, 20% no change, 70% price increases
        rand_b = random.random() * 100  # 0-100
        if rand_b <= 10:
            # Price decreases
            animation_queue.append({'market': 1, 'type': 'fall', 'price_change': -self.StepB})
        elif rand_b <= 30:  # 10-30 = 20%
            # Price stays the same - add to animation queue
            animation_queue.append({'market': 1, 'type': 'unchanged', 'price_change': 0})
        else:  # 30-100 = 70% - price increases
            animation_queue.append({'market': 1, 'type': 'rise', 'price_change': self.StepB})
        
        # Stock C: 30% price decreases, 20% no change, 50% price increases
        rand_c = random.random() * 100  # 0-100
        if rand_c <= 30:
            # Price decreases
            animation_queue.append({'market': 2, 'type': 'fall', 'price_change': -self.StepC})
        elif rand_c <= 50:  # 30-50 = 20%
            # Price stays the same - add to animation queue
            animation_queue.append({'market': 2, 'type': 'unchanged', 'price_change': 0})
        else:  # 50-100 = 50% - price increases
            animation_queue.append({'market': 2, 'type': 'rise', 'price_change': self.StepC})
        
        return animation_queue

    def update_arrow_animation(self):
        if not self.arrow_entries or not self.arrow_anim_frames:
            return
        now = pygame.time.get_ticks()
        for entry in self.arrow_entries:
            if not entry["animating"]:
                continue
            if now - entry["last"] >= self.arrow_anim_interval:
                entry["last"] = now
                entry["idx"] += 1
                if entry["idx"] >= len(self.arrow_anim_sequence):
                    entry["animating"] = False
                    entry["idx"] = 0

    def _finish_price_animations_and_advance_day(self):
        """Finalize price animations, card processing, and day progression."""
        self.current_price_animation = None
        self._process_cards_11_14()
        self._check_win_lose()

        if self.win_lose_state is None:
            if self.Day < self.LastTurn:
                self.Day += 1
                self._check_win_lose()
            else:
                print(f"ERROR: Day==LastTurn but game didn't end! Forcing end.")
                if self.Money >= self.Goal:
                    self.win_lose_state = "win"
                else:
                    self.win_lose_state = "lose"
                    # Reset earned cards for this level when player loses
                    self._reset_earned_cards_for_level()
                if self.win_lose_image:
                    winlose_height = self.win_lose_image.get_height()
                    self.win_lose_y = float(-winlose_height)

        self._draw_pending_cards()

    def update_price_animation(self):
        """Update price animation - plays sequentially for each market"""
        if not self.current_price_animation:
            # Check if there are more animations in queue
            if self.price_animation_queue:
                next_anim = self.price_animation_queue.pop(0)
                # Apply price change when animation starts
                self._apply_price_change(next_anim['market'], next_anim['price_change'])
                self.current_price_animation = {
                    'market': next_anim['market'],
                    'type': next_anim['type'],
                    'frame_idx': 0,
                    'last_update': pygame.time.get_ticks()
                }
                # Play sound for new animation
                if self.typewriter_sound:
                    self.typewriter_sound.play()
            return
        
        # Get the correct frames based on animation type
        if self.current_price_animation['type'] == 'unchanged':
            frames = self.price_unchanged_frames
        elif self.current_price_animation['type'] == 'rise':
            frames = self.price_rise_frames
        elif self.current_price_animation['type'] == 'fall':
            frames = self.price_fall_frames
        else:
            frames = []
        
        if not frames:
            # No frames available, skip to next animation
            if self.price_animation_queue:
                next_anim = self.price_animation_queue.pop(0)
                # Apply price change when animation starts
                self._apply_price_change(next_anim['market'], next_anim['price_change'])
                self.current_price_animation = {
                    'market': next_anim['market'],
                    'type': next_anim['type'],
                    'frame_idx': 0,
                    'last_update': pygame.time.get_ticks()
                }
                if self.typewriter_sound:
                    self.typewriter_sound.play()
            else:
                self._finish_price_animations_and_advance_day()
            return
        
        now = pygame.time.get_ticks()
        if now - self.current_price_animation['last_update'] >= self.price_animation_interval:
            self.current_price_animation['last_update'] = now
            self.current_price_animation['frame_idx'] += 1
            
            # Check if animation completed
            if self.current_price_animation['frame_idx'] >= len(frames):
                # Animation completed, move to next in queue
                if self.price_animation_queue:
                    next_anim = self.price_animation_queue.pop(0)
                    # Apply price change when animation starts
                    self._apply_price_change(next_anim['market'], next_anim['price_change'])
                    self.current_price_animation = {
                        'market': next_anim['market'],
                        'type': next_anim['type'],
                        'frame_idx': 0,
                        'last_update': now
                    }
                    # Play sound for next animation
                    if self.typewriter_sound:
                        self.typewriter_sound.play()
                else:
                    self._finish_price_animations_and_advance_day()
    
    def _process_cards_11_14(self):
        """Queue cards 11-18 for sequential processing after all price animations finish."""
        # Build queue of cards to process in order: market 0, 1, 2, and for each market slots 0, 1, 2
        self.cards_11_14_queue = []
        for market in (0, 1, 2):
            for slot in (0, 1, 2):
                card_id = self.market_cards[market].get(slot)
                if card_id is None:
                    continue
                # Only process cards 11-18
                if card_id not in (11, 12, 13, 14, 15, 16, 17, 18):
                    continue
                # Check CardTurns - only process if > 0
                turns_remaining = self.market_card_turns[market].get(slot)
                if turns_remaining is not None and turns_remaining > 0:
                    self.cards_11_14_queue.append((market, slot))
        
        # Start processing first card if queue is not empty
        if self.cards_11_14_queue:
            self.current_card_processing = self.cards_11_14_queue.pop(0)
            self.card_processing_start_time = pygame.time.get_ticks()
    
    def update_cards_11_14_processing(self):
        """Update sequential processing of cards 11-18. Process one card at a time with delay."""
        if self.current_card_processing is None:
            # Check if there are more cards in queue
            if self.cards_11_14_queue:
                self.current_card_processing = self.cards_11_14_queue.pop(0)
                self.card_processing_start_time = pygame.time.get_ticks()
            return
        
        now = pygame.time.get_ticks()
        if now - self.card_processing_start_time < self.card_processing_delay:
            # Still waiting for delay
            return
        
        # Process current card
        market, slot = self.current_card_processing
        card_id = self.market_cards[market].get(slot)
        
        if card_id is not None:
            # Check CardTurns again (in case it changed)
            turns_remaining = self.market_card_turns[market].get(slot)
            if turns_remaining is not None and turns_remaining > 0:
                # Apply CardAction to price
                card_action = self.card_actions.get(card_id, 0)
                if card_action != 0:
                    # Cards 17 and 18 multiply price by CardAction, others add/subtract
                    if card_id in (17, 18):
                        if market == 0:  # Stock A
                            self.Aprice = max(2, int(self.Aprice * card_action))
                        elif market == 1:  # Stock B
                            self.BPrice = max(2, int(self.BPrice * card_action))
                        elif market == 2:  # Stock C
                            self.CPrice = max(2, int(self.CPrice * card_action))
                    else:
                        if market == 0:  # Stock A
                            self.Aprice = max(2, self.Aprice + card_action)
                        elif market == 1:  # Stock B
                            self.BPrice = max(2, self.BPrice + card_action)
                        elif market == 2:  # Stock C
                            self.CPrice = max(2, self.CPrice + card_action)
                
                # Start jump animation for the card
                self.card_jump_animations[market][slot] = {
                    'offset_y': 0.0,
                    'velocity': -15.0,  # Initial upward velocity
                    'start_time': pygame.time.get_ticks()
                }
                
                # Decrement CardTurns
                self.market_card_turns[market][slot] = turns_remaining - 1
        
        # Move to next card
        self.current_card_processing = None
        if self.cards_11_14_queue:
            self.current_card_processing = self.cards_11_14_queue.pop(0)
            self.card_processing_start_time = pygame.time.get_ticks()
    
    def update_card_jump_animations(self):
        """Update jump animations for cards 11-18. Simple physics: velocity decreases due to gravity."""
        gravity = 0.8
        now = pygame.time.get_ticks()
        
        for market in (0, 1, 2):
            slots_to_remove = []
            for slot, anim in list(self.card_jump_animations[market].items()):
                # Update velocity (apply gravity)
                anim['velocity'] += gravity
                # Update position
                anim['offset_y'] += anim['velocity']
                
                # If card has landed (offset_y >= 0 and velocity > 0), remove animation
                if anim['offset_y'] >= 0 and anim['velocity'] > 0:
                    slots_to_remove.append(slot)
                # Clamp offset_y to prevent going too far down
                if anim['offset_y'] > 0:
                    anim['offset_y'] = 0
            
            # Remove finished animations
            for slot in slots_to_remove:
                self.card_jump_animations[market].pop(slot, None)
    
    def _apply_price_change(self, market, price_change):
        """Apply price change to the specified market. Ensures price doesn't drop below 2."""
        if market == 0:  # Stock A
            new_price = self.Aprice + price_change
            self.Aprice = max(2, new_price)  # Minimum price is 2
        elif market == 1:  # Stock B
            new_price = self.BPrice + price_change
            self.BPrice = max(2, new_price)  # Minimum price is 2
        elif market == 2:  # Stock C
            new_price = self.CPrice + price_change
            self.CPrice = max(2, new_price)  # Minimum price is 2

    def _lock_market_cards(self):
        """Помечает все текущие карты на рынке как сыгранные и заблокированные до конца игры."""
        for market in (0, 1, 2):
            for slot, card_id in list(self.market_cards[market].items()):
                if card_id is not None:
                    self.market_cards_locked[market][slot] = True

    def _draw_pending_cards(self):
        """Prepare hand compaction animation and subsequent draw after end-turn animations.

        1) Планируем плавное смещение несыгранных карт влево (без мгновенной перемотки).
        2) После завершения анимации добираем Dobor карт в ближайшие свободные слоты.
        """
        # Сбросим старую анимацию, если по какой‑то причине она ещё есть
        self.hand_compact_anim = []
        self.hand_compact_target_hand = None
        self.hand_compact_draw_count = 0

        # Нечего делать, если нет добора, колода пуста или в руке нет слотов
        if self.hand <= 0:
            self.pending_draws = 0
            return

        # 1) Подготовка данных о текущем расположении слотов руки
        if not self.bottom_frame:
            # Без нижней рамки корректно анимировать не получится — просто применяем мгновенно
            existing_cards = [card for card in self.hand_cards if card is not None][: self.hand]
            self.hand_cards = existing_cards + [None] * (self.hand - len(existing_cards))

            # Добор без анимации — всегда добраем, если есть свободные слоты и карты в колоде
            start_idx = len(existing_cards)
            slots_available = self.hand - start_idx
            if self.Dobor > 0 and self.deck and slots_available > 0:
                draw_limit = min(self.Dobor, len(self.deck), slots_available)
                for offset in range(draw_limit):
                    card_id = self.deck.pop(0)
                    if card_id == 0:
                        card_id = 100
                    self.hand_cards[start_idx + offset] = card_id
                self.pending_draws = 0
            return

        # Геометрия нижней рамки и плейсхолдеров (как в draw)
        bf_w = self.bottom_frame.get_width()
        bf_h = self.bottom_frame.get_height()
        bf_x = (SCREEN_WIDTH - bf_w) // 2 - 200
        bf_y = SCREEN_HEIGHT - bf_h - 150

        ph_w = 138
        ph_h = 240
        margin_x = 20
        available_width = bf_w - margin_x * 2
        if self.hand > 1:
            spacing = max(5, (available_width - ph_w * self.hand) // (self.hand - 1))
        else:
            spacing = 0
        total_width = ph_w * self.hand + spacing * (self.hand - 1)
        start_x = bf_x + (bf_w - total_width) // 2
        start_y = bf_y + (bf_h - ph_h) // 2

        # Координаты слотов руки
        slot_positions = []
        for i in range(self.hand):
            slot_x = start_x + i * (ph_w + spacing)
            slot_y = start_y
            slot_positions.append((slot_x, slot_y))

        # 2) Текущее содержимое и целевой порядок (уплотнение влево)
        existing = [(idx, card) for idx, card in enumerate(self.hand_cards) if card is not None]
        if not existing:
            # В руке вообще нет карт — просто добираем без анимации - всегда добраем, если есть карты в колоде
            if self.Dobor > 0 and len(self.deck) > 0 and self.hand > 0:
                draw_limit = min(self.Dobor, len(self.deck), self.hand)
                self.hand_cards = [None] * self.hand
                for i in range(draw_limit):
                    card_id = self.deck.pop(0)
                    if card_id == 0:
                        card_id = 100
                    self.hand_cards[i] = card_id
                self.pending_draws = 0
            return

        # Обрезаем по размеру руки
        existing = existing[: self.hand]
        # Целевая рука: те же карты, но слева без дыр
        target_hand = [card for (_, card) in existing]
        target_hand += [None] * (self.hand - len(target_hand))

        # 3) Планируем перемещения карт для анимации
        moves = []
        for new_index, (old_index, card_id) in enumerate(existing):
            if old_index == new_index:
                continue  # карта уже на своём месте, не анимируем
            from_pos = slot_positions[old_index]
            to_pos = slot_positions[new_index]
            moves.append(
                {
                    "card_id": card_id,
                    "from_index": old_index,
                    "to_index": new_index,
                    "from_pos": from_pos,
                    "to_pos": to_pos,
                    "progress": 0.0,
                }
            )

        # 4) Считаем, сколько карт нужно добрать после компактации - всегда добраем, если есть свободные слоты и карты в колоде
        free_slots_after = self.hand - len(existing)
        max_draw_by_slots = free_slots_after
        draw_limit = min(self.Dobor, len(self.deck), max_draw_by_slots) if free_slots_after > 0 and len(self.deck) > 0 else 0

        if not moves:
            # Ничего не двигается — применяем целевой порядок и запускаем анимацию добора
            self.hand_cards = target_hand
            if draw_limit > 0 and len(self.deck) > 0:
                start_idx = len(existing)
                # Запускаем анимацию добора вместо мгновенного добора
                if self.bottom_frame:
                    self.hand_draw_anim = []
                    for offset in range(draw_limit):
                        target_slot = start_idx + offset
                        target_x = slot_positions[target_slot][0]
                        target_y = slot_positions[target_slot][1]
                        # Стартовая позиция: снизу экрана, по центру целевого слота по X
                        from_x = target_x
                        from_y = SCREEN_HEIGHT + 100  # За экраном снизу
                        
                        card_id = self.deck.pop(0)  # Извлекаем карту из колоды
                        if card_id == 0:
                            card_id = 100
                        self.hand_draw_anim.append({
                            'card_id': card_id,
                            'target_slot': target_slot,
                            'target_pos': (target_x, target_y),
                            'from_pos': (from_x, from_y),
                            'progress': 0.0,
                        })
                    self.hand_draw_start_time = pygame.time.get_ticks()
                else:
                    # Без рамки — мгновенный добор
                    for offset in range(draw_limit):
                        card_id = self.deck.pop(0)
                        if card_id == 0:
                            card_id = 100
                        self.hand_cards[start_idx + offset] = card_id
            self.pending_draws = 0
            return

        # Есть движения — сохраняем состояние анимации, саму руку пока не меняем
        self.hand_compact_anim = moves
        self.hand_compact_target_hand = target_hand
        self.hand_compact_draw_count = draw_limit
        self.hand_compact_start_time = pygame.time.get_ticks()

    def update_hand_compact_animation(self):
        """Обновление анимации сдвига карт в руке после конца хода."""
        if not self.hand_compact_anim:
            return

        now = pygame.time.get_ticks()
        elapsed = now - self.hand_compact_start_time
        progress = min(1.0, max(0.0, elapsed / max(1, self.hand_compact_duration)))

        # Обновляем прогресс для всех движений
        for entry in self.hand_compact_anim:
            entry["progress"] = progress

        # Если анимация завершена, применяем итоговое состояние
        if progress >= 1.0:
            # 1) Применяем целевой порядок руки
            if self.hand_compact_target_hand is not None:
                self.hand_cards = self.hand_compact_target_hand

            # 2) Запускаем анимацию добора карт (вместо мгновенного добора)
            if (
                self.hand_compact_draw_count > 0
                and len(self.deck) > 0
                and any(card is None for card in self.hand_cards)
            ):
                # Ищем первый свободный слот
                first_free = next(
                    (i for i, card in enumerate(self.hand_cards) if card is None), None
                )
                if first_free is not None:
                    slots_available = self.hand - first_free
                    draw_count = min(
                        self.hand_compact_draw_count, slots_available, len(self.deck)
                    )
                    
                # Подготовка геометрии для анимации (как в draw, с тем же более плотным spacing и центрированием)
                    if self.bottom_frame:
                        bf_w = self.bottom_frame.get_width()
                        bf_h = self.bottom_frame.get_height()
                        bf_x = (SCREEN_WIDTH - bf_w) // 2 - 200
                        bf_y = SCREEN_HEIGHT - bf_h - 150
                        
                        ph_w = 138
                        ph_h = 240
                        base_spacing = (bf_w - ph_w * self.hand) / (self.hand + 1)
                        spacing = base_spacing * 0.7
                        total_width = ph_w * self.hand + spacing * (self.hand - 1)
                        start_x = bf_x + (bf_w - total_width) / 2
                        start_y = bf_y + (bf_h - ph_h) // 2
                        
                        # Создаём анимации для каждой новой карты
                        self.hand_draw_anim = []
                        for offset in range(draw_count):
                            target_slot = first_free + offset
                            target_x = start_x + target_slot * (ph_w + spacing)
                            target_y = start_y
                            # Стартовая позиция: снизу экрана, по центру целевого слота по X
                            from_x = target_x
                            from_y = SCREEN_HEIGHT + 100  # За экраном снизу
                            
                            card_id = self.deck.pop(0)  # Извлекаем карту из колоды
                            if card_id == 0:
                                card_id = 100
                            self.hand_draw_anim.append({
                                'card_id': card_id,
                                'target_slot': target_slot,
                                'target_pos': (target_x, target_y),
                                'from_pos': (from_x, from_y),
                                'progress': 0.0,
                            })
                        self.hand_draw_start_time = pygame.time.get_ticks()
                    else:
                        # Без рамки — мгновенный добор
                        for offset in range(draw_count):
                            card_id = self.deck.pop(0)
                            if card_id == 0:
                                card_id = 100
                            self.hand_cards[first_free + offset] = card_id

            # 3) Сбрасываем состояние анимации компактирования (добор запущен отдельно)
            self.pending_draws = 0
            self.hand_compact_anim = []
            self.hand_compact_target_hand = None
            self.hand_compact_draw_count = 0
    
    def update_hand_draw_animation(self):
        """Обновление анимации добора карт (карты прилетают снизу экрана)."""
        if not self.hand_draw_anim:
            return
        
        now = pygame.time.get_ticks()
        elapsed = now - self.hand_draw_start_time
        progress = min(1.0, max(0.0, elapsed / max(1, self.hand_draw_duration)))
        
        # Обновляем прогресс для всех анимаций добора
        for entry in self.hand_draw_anim:
            entry["progress"] = progress
        
        # Если анимация завершена, физически добавляем карты в руку
        if progress >= 1.0:
            for entry in self.hand_draw_anim:
                target_slot = entry['target_slot']
                if target_slot < len(self.hand_cards):
                    card_id = entry['card_id']
                    if card_id == 0:
                        card_id = 100
                    self.hand_cards[target_slot] = card_id
            
            # Сбрасываем состояние анимации добора
            self.hand_draw_anim = []
    
    def draw_card_action(self, card_id, card_x, card_y, card_size):
        """Draw CardAction value next to the + sign on a card.
        card_x, card_y: top-left position of the card
        card_size: tuple (width, height) of the card
        Assumes + sign is in the upper right area of the card.
        CardAction is displayed near the + sign and scales with card size."""
        if card_id is None:
            return
        if card_id not in self.card_actions:
            return
        
        action_value = self.card_actions[card_id]
        
        # Validate card_size
        if not card_size or len(card_size) < 2 or card_size[0] <= 0:
            return
        
        # Calculate scale factor based on card size
        # Market cards: (99, 171), Bottom cards: (142, 244)
        # Use width ratio for scaling
        base_market_width = 99
        scale_factor = card_size[0] / base_market_width
        
        # Calculate font size based on scale (base font_small is 36, reduced by 15%, then by 10%)
        base_font_size = 36
        base_font_size_reduced = int(base_font_size * 0.85 * 0.9)  # Reduce by 15%, then by 10% more
        scaled_font_size = int(base_font_size_reduced * scale_factor)
        
        # Ensure minimum font size (at least 1 pixel)
        if scaled_font_size < 1:
            scaled_font_size = 1

        # Prepare (and cache) font for CardAction, prefer Gadugib if available
        if not hasattr(self, "card_action_font_cache"):
            self.card_action_font_cache = {}
        if not hasattr(self, "card_action_font_base"):
            gadugib_path = "Gadugib.ttf"
            if os.path.exists(gadugib_path):
                self.card_action_font_base = gadugib_path
            else:
                self.card_action_font_base = self.font_path
        font_key = scaled_font_size
        scaled_font = self.card_action_font_cache.get(font_key)
        if scaled_font is None:
            try:
                scaled_font = pygame.font.Font(self.card_action_font_base, scaled_font_size)
                self.card_action_font_cache[font_key] = scaled_font
            except Exception as e:
                print(f"ERROR creating font for CardAction (size {scaled_font_size}): {e}")
                return
        
        # Ensure font is valid before using
        if scaled_font is None:
            return
        
        # Assume + sign is in upper right area, approximately at (card_width - 25, 10)
        # CardAction is displayed near the + sign
        # Scale the offset positions too
        plus_x = card_x + card_size[0] - 25 * scale_factor  # Approximate position of + sign (from right edge)
        plus_y = card_y + 10 * scale_factor  # Approximate position from top
        # Current offset: move 29px left and 14px down relative to the + sign (scaled)
        # Adjusted: moved 4px down from previous position
        action_x = plus_x - 29 * scale_factor
        action_y = plus_y + 14 * scale_factor
        
        # For cards 15 and 16, shift left by 11 pixels to compensate for minus sign
        if card_id in (15, 16):
            action_x -= 11 * scale_factor
        
        # Render CardAction text using scaled font with PAPER_COLOR
        try:
            action_text = scaled_font.render(str(action_value), True, PAPER_COLOR)
            if action_text:
                self.screen.blit(action_text, (action_x, action_y))
        except Exception as e:
            print(f"ERROR rendering CardAction text: {e}")
    
    def draw_card_turns(self, card_id, card_x, card_y, card_size, turns_remaining=None):
        """Draw CardTurns value at the bottom of a card after "Turns:" text.
        card_x, card_y: top-left position of the card
        card_size: tuple (width, height) of the card
        CardTurns is displayed at the bottom and scales with card size.
        Font size is 20% smaller than CardAction.
        turns_remaining: optional remaining turns value (for market cards), if None uses base value from card_turns."""
        if card_id is None:
            return
        if card_id not in self.card_turns:
            return
        
        # Use provided turns_remaining if available, otherwise use base value
        if turns_remaining is not None:
            turns_value = turns_remaining
        else:
            turns_value = self.card_turns[card_id]
        
        # Validate card_size
        if not card_size or len(card_size) < 2 or card_size[0] <= 0:
            return
        
        # Calculate scale factor based on card size
        # Market cards: (99, 171), Bottom cards: (142, 244)
        # Use width ratio for scaling
        base_market_width = 99
        scale_factor = card_size[0] / base_market_width
        
        # Calculate font size: 20% smaller than CardAction, then 10% more smaller, then 10% more
        base_font_size = 36
        card_action_font_size = int(base_font_size * 0.85 * 0.9 * scale_factor)  # CardAction size (reduced by 15% and 10%)
        turns_font_size = int(card_action_font_size * 0.648)  # 20% smaller, then 10% more, then 10% more (0.8 * 0.9 * 0.9 = 0.648)
        
        # Ensure minimum font size (at least 1 pixel)
        if turns_font_size < 1:
            turns_font_size = 1
        
        # Prepare (and cache) font for CardTurns, prefer Gadugib if available
        if not hasattr(self, "card_turns_font_cache"):
            self.card_turns_font_cache = {}
        if not hasattr(self, "card_turns_font_base"):
            gadugib_path = "Gadugib.ttf"
            if os.path.exists(gadugib_path):
                self.card_turns_font_base = gadugib_path
            else:
                self.card_turns_font_base = self.font_path
        font_key = turns_font_size
        scaled_font = self.card_turns_font_cache.get(font_key)
        if scaled_font is None:
            try:
                scaled_font = pygame.font.Font(self.card_turns_font_base, turns_font_size)
                self.card_turns_font_cache[font_key] = scaled_font
            except Exception as e:
                print(f"ERROR creating font for CardTurns (size {turns_font_size}): {e}")
                return
        
        # Ensure font is valid before using
        if scaled_font is None:
            return
        
        # Render CardTurns value only (word "Turns:" is already drawn on the card)
        # Position: at a distance from the bottom that scales with card height
        try:
            turns_text = scaled_font.render(str(turns_value), True, PAPER_COLOR)
            if turns_text:
                # Center horizontally, then shift right
                card_center_x = card_x + card_size[0] / 2
                turns_x = card_center_x + 10 * scale_factor  # 10px to the right of center

                # Vertical position: keep the SAME relative distance from the bottom of the card,
                # even when the card is scaled.
                # For a full-size hand card (height 244) the distance should be 75px.
                base_bottom_height = 244.0  # height of bottom (hand) card
                current_height = float(card_size[1])
                height_scale = current_height / base_bottom_height if base_bottom_height > 0 else 1.0
                offset_from_bottom = 75.0 * height_scale

                turns_y = card_y + card_size[1] - offset_from_bottom

                # Cards 17-18 use a slightly different base card art layout; align the number
                # with the "Turns:" label to match cards 11-16.
                # Empirically: 17/18 were ~7px too far right and ~4px too high (at bottom-card size).
                if card_id in (17, 18):
                    x_scale = float(card_size[0]) / 142.0 if card_size[0] else 1.0
                    y_scale = float(card_size[1]) / 244.0 if card_size[1] else 1.0
                    turns_x -= 7.0 * x_scale
                    turns_y += 2.0 * y_scale

                # Pygame blit prefers integer coordinates; keeps text crisp and consistent.
                self.screen.blit(turns_text, (int(turns_x), int(turns_y)))
        except Exception as e:
            print(f"ERROR rendering CardTurns text: {e}")
    
    def draw(self):
        # Clear market placeholders list at start of draw
        self.market_placeholders = []
        
        # Draw background
        if self.background:
            self.screen.blit(self.background, (0, 0))
        else:
            self.screen.fill(PAPER_COLOR)
        
        # Draw three top frames (for columns A, B, C)
        if self.frame:
            frame_width = self.frame.get_width()
            frame_height = self.frame.get_height()
            spacing = 10  # Space between frames
            
            # Calculate starting x position to center the three frames, then move left 200px
            total_width = (frame_width * 3) + (spacing * 2)
            start_x = (SCREEN_WIDTH - total_width) // 2 - 200  # Move left 200px
            
            # Calculate right edge of frame C (i=2)
            frame_c_x = start_x + 2 * (frame_width + spacing)
            frame_c_right = frame_c_x + frame_width
            
            # Draw Goal and Money positioned 40px to the right of frame C
            label_start_x = frame_c_right + 55  # 55px from right edge of frame C (40 + 15)
            margin_top = 80  # Lower position
            label_spacing = 15  # Spacing between Goal and Money
            value_spacing = 10  # Spacing between label and value
            min_right_margin = 20  # Minimum margin from right edge to prevent overflow
            
            # Draw Goal label and value
            goal_label = self.font_medium.render("Goal:", True, PAPER_COLOR)
            goal_value = self.font_medium.render(str(self.Goal), True, PAPER_COLOR)
            goal_label_x = label_start_x
            goal_label_y = margin_top
            goal_value_x = goal_label_x + goal_label.get_width() + value_spacing
            goal_value_y = margin_top
            # Ensure value doesn't go off screen
            if goal_value_x + goal_value.get_width() > SCREEN_WIDTH - min_right_margin:
                goal_value_x = SCREEN_WIDTH - min_right_margin - goal_value.get_width()
            self.screen.blit(goal_label, (goal_label_x, goal_label_y))
            self.screen.blit(goal_value, (goal_value_x, goal_value_y))
            
            # Draw Money label and value (below Goal)
            money_label = self.font_medium.render("Money:", True, PAPER_COLOR)
            money_value = self.font_medium.render(str(self.Money), True, PAPER_COLOR)
            money_label_x = label_start_x
            money_label_y = margin_top + goal_label.get_height() + label_spacing
            money_value_x = money_label_x + money_label.get_width() + value_spacing
            money_value_y = money_label_y
            # Ensure value doesn't go off screen
            if money_value_x + money_value.get_width() > SCREEN_WIDTH - min_right_margin:
                money_value_x = SCREEN_WIDTH - min_right_margin - money_value.get_width()
            self.screen.blit(money_label, (money_label_x, money_label_y))
            self.screen.blit(money_value, (money_value_x, money_value_y))
            
            # Draw three frames at the top, moved down 20px
            for i in range(3):
                frame_x = start_x + i * (frame_width + spacing)
                frame_y = 20 + 20  # Top margin + 20px down
                self.screen.blit(self.frame, (frame_x, frame_y))
                # Draw corresponding logo in top-left corner of the frame
                logo = None
                if i == 0:
                    logo = self.logo_a
                elif i == 1:
                    logo = self.logo_b
                elif i == 2:
                    logo = self.logo_c
                if logo:
                    # Move logo 10px right and 10px down
                    logo_x = frame_x + 25
                    logo_y = frame_y + 20
                    self.screen.blit(logo, (logo_x, logo_y))
                    
                    # ============================================================
                    # QP BLOCK - Quantity and Price Block
                    # ============================================================
                    # This block consists of 4 elements that must stay together:
                    # 1. Bundle of shares image (base position: bundle_x, bundle_y)
                    # 2. Quantity field (right of bundle, vertically centered)
                    # 3. Dollar image (10px right, 5px below bundle)
                    # 4. Price field (same X as quantity, vertically centered with Dollar)
                    # 
                    # IMPORTANT: To move the QP Block, only change bundle_x and bundle_y.
                    # All other positions are calculated relative to these coordinates.
                    # ============================================================
                    if self.bundle_image:
                        # Base position for QP Block - change these to move the entire block
                        # Use fixed logo height (128) to ensure all QP Blocks are at the same level
                        bundle_x = logo_x
                        bundle_y = logo_y + 128 + 5 + 30  # Fixed logo height (128) + 5px spacing + 30px down
                        self.screen.blit(self.bundle_image, (bundle_x, bundle_y))
                        
                        # Calculate text_x position (used for both quantity and price)
                        text_x = bundle_x + self.bundle_image.get_width() + 10  # 10px spacing from bundle image
                        
                        # Draw quantity text next to the bundle image (related data)
                        quantity = None
                        if i == 0:
                            quantity = self.Aquantity
                        elif i == 1:
                            quantity = self.Bquantity
                        elif i == 2:
                            quantity = self.Cquantity
                        
                        if quantity is not None:
                            # Position text to the right of the bundle image, vertically centered
                            quantity_text = self.font_small.render(str(quantity), True, PAPER_COLOR)
                            # Center text vertically with bundle image
                            text_y = bundle_y + (self.bundle_image.get_height() - quantity_text.get_height()) // 2
                            self.screen.blit(quantity_text, (text_x, text_y))
                        
                        # Draw Dollar image below the bundle image
                        if self.dollar_image:
                            dollar_x = bundle_x + 10  # 10px to the right
                            dollar_y = bundle_y + self.bundle_image.get_height() + 5  # 5px spacing below bundle image
                            self.screen.blit(self.dollar_image, (dollar_x, dollar_y))
                            
                            # Draw price text at the same level as Dollar image
                            price = None
                            if i == 0:
                                price = self.Aprice
                            elif i == 1:
                                price = self.BPrice
                            elif i == 2:
                                price = self.CPrice
                            
                            if price is not None:
                                price_text = self.font_small.render(str(price), True, PAPER_COLOR)
                                price_text_x = text_x  # Same x position as quantity field
                                # Center text vertically with Dollar image
                                price_text_y = dollar_y + (self.dollar_image.get_height() - price_text.get_height()) // 2
                                self.screen.blit(price_text, (price_text_x, price_text_y))

                # Draw arrows inside each frame (stacked vertically), size 60x60, start 25px from top
                if self.arrow_up and self.arrow_down and self.arrow_mid_up and self.arrow_mid_down:
                    arrow_size = 60
                    spacing_outer = 8  # spacing between 1-2 and 3-4
                    spacing_middle = 4  # reduced spacing between middle arrows (2-3)
                    # Order: top outer up, middle Arrow1 up, middle Arrow1 down, bottom outer down
                    arrows = [self.arrow_up, self.arrow_mid_up, self.arrow_mid_down, self.arrow_down]
                    total_height = (
                        len(arrows) * arrow_size
                        + spacing_outer * 2
                        + spacing_middle
                    )
                    arrow_x = frame_x + frame_width - arrow_size - 20  # inset from right edge
                    start_y = frame_y + 25  # place top arrow 25px below top of frame
                    # collect hitboxes for clickable outer arrows (two per frame)
                    for idx, arrow_img in enumerate(arrows):
                        if idx == 0:
                            ay = start_y
                        elif idx == 1:
                            ay = start_y + arrow_size + spacing_outer
                        elif idx == 2:
                            ay = start_y + arrow_size * 2 + spacing_outer + spacing_middle
                        else:  # idx == 3
                            ay = start_y + arrow_size * 3 + spacing_outer * 2 + spacing_middle
                        # Choose animated frame for outer arrows if animating
                        # Determine image (animated only for outer arrows per entry state)
                        img_to_draw = arrow_img
                        if idx == 0 and self.arrow_anim_frames:
                            rect = pygame.Rect(arrow_x, ay, arrow_size, arrow_size)
                            entry = next((e for e in self.arrow_entries if e["rect"].topleft == rect.topleft), None)
                            if not entry:
                                entry = {"rect": rect, "animating": False, "idx": 0, "last": 0, "frames": self.arrow_anim_frames, "arrow_type": 0, "frame_index": i}
                                self.arrow_entries.append(entry)
                            if entry["animating"]:
                                frame_idx = self.arrow_anim_sequence[entry["idx"]]
                                img_to_draw = entry["frames"][frame_idx] if entry["frames"] else arrow_img
                            self.screen.blit(img_to_draw, rect.topleft)
                        elif idx == 1 and self.arrow_mid_up_frames:
                            # Middle up arrow with animation
                            rect = pygame.Rect(arrow_x, ay, arrow_size, arrow_size)
                            entry = next((e for e in self.arrow_entries if e["rect"].topleft == rect.topleft), None)
                            if not entry:
                                entry = {"rect": rect, "animating": False, "idx": 0, "last": 0, "frames": self.arrow_mid_up_frames, "arrow_type": 1, "frame_index": i}
                                self.arrow_entries.append(entry)
                            if entry["animating"]:
                                frame_idx = self.arrow_anim_sequence[entry["idx"]]
                                img_to_draw = entry["frames"][frame_idx] if entry["frames"] else arrow_img
                            else:
                                img_to_draw = arrow_img
                            self.screen.blit(img_to_draw, rect.topleft)
                        elif idx == 2 and self.arrow_mid_down_frames:
                            # Middle down arrow with animation
                            rect = pygame.Rect(arrow_x, ay, arrow_size, arrow_size)
                            entry = next((e for e in self.arrow_entries if e["rect"].topleft == rect.topleft), None)
                            if not entry:
                                entry = {"rect": rect, "animating": False, "idx": 0, "last": 0, "frames": self.arrow_mid_down_frames, "arrow_type": 2, "frame_index": i}
                                self.arrow_entries.append(entry)
                            if entry["animating"]:
                                frame_idx = self.arrow_anim_sequence[entry["idx"]]
                                img_to_draw = entry["frames"][frame_idx] if entry["frames"] else arrow_img
                            else:
                                img_to_draw = arrow_img
                            self.screen.blit(img_to_draw, rect.topleft)
                        elif idx == 3 and self.arrow_down_frames:
                            rect = pygame.Rect(arrow_x, ay, arrow_size, arrow_size)
                            entry = next((e for e in self.arrow_entries if e["rect"].topleft == rect.topleft), None)
                            if not entry:
                                entry = {"rect": rect, "animating": False, "idx": 0, "last": 0, "frames": self.arrow_down_frames, "arrow_type": 3, "frame_index": i}
                                self.arrow_entries.append(entry)
                            if entry["animating"]:
                                frame_idx = self.arrow_anim_sequence[entry["idx"]]
                                img_to_draw = entry["frames"][frame_idx] if entry["frames"] else arrow_img
                            self.screen.blit(img_to_draw, rect.topleft)
                        else:
                            self.screen.blit(img_to_draw, (arrow_x, ay))
                
                # Draw three placeholders at the bottom of each market frame (A, B, C)
                if self.placeholder_market:
                    ph_w = 96   # Market placeholder width (увеличено на 20% от 80)
                    ph_h = 168  # Market placeholder height (увеличено на 20% от 140)
                    num_placeholders = 3
                    # Calculate equal spacing: margins from edges = spacing between placeholders
                    # Total gaps = num_placeholders + 1 (2 margins + 2 spaces between 3 placeholders)
                    spacing = (frame_width - ph_w * num_placeholders) / (num_placeholders + 1)
                    ph_start_x = frame_x + spacing  # Start from equal margin
                    ph_start_y = frame_y + frame_height - ph_h - 30  # 30px from bottom of frame (moved up 20px total)
                    
                    # Clear market placeholders list and repopulate
                    for ph_idx in range(num_placeholders):
                        ph_x = ph_start_x + ph_idx * (ph_w + spacing)
                        # Move left and right placeholders 7px closer to the center placeholder
                        if ph_idx == 0:
                            ph_x += 7   # left placeholder moves right
                        elif ph_idx == 2:
                            ph_x -= 7   # right placeholder moves left
                        ph_y = ph_start_y
                        ph_rect = pygame.Rect(ph_x, ph_y, ph_w, ph_h)
                        self.market_placeholders.append({
                            'market': i,
                            'slot': ph_idx,
                            'rect': ph_rect
                        })
                        self.screen.blit(self.placeholder_market, (ph_x, ph_y))
                        
                        # Draw card on market placeholder if one is placed there
                        if (
                            ph_idx in self.market_cards[i]
                            and self.market_cards[i][ph_idx] is not None
                            and not (
                                self.dragged_card_source == "market"
                                and self.dragged_card_market == i
                                and self.dragged_card_market_slot == ph_idx
                            )
                        ):
                            card_id = self.market_cards[i][ph_idx]
                            if card_id in self.card_images_market and self.card_images_market[card_id]:
                                # Use pre-scaled market card (no scaling on every frame)
                                # Center card on placeholder
                                card_x = ph_x - 1  # Center horizontally
                                card_y = ph_y - 1  # Center vertically
                                # Apply jump animation offset if card is jumping
                                jump_anim = self.card_jump_animations[i].get(ph_idx)
                                if jump_anim:
                                    card_y += int(jump_anim['offset_y'])
                                self.screen.blit(self.card_images_market[card_id], (card_x, card_y))
                                # Draw CardAction if this card has one
                                self.draw_card_action(card_id, card_x, card_y, self.card_size_market)
                                # Draw CardTurns if this card has one - use remaining turns from market_card_turns
                                remaining_turns = self.market_card_turns[i].get(ph_idx)
                                self.draw_card_turns(card_id, card_x, card_y, self.card_size_market, turns_remaining=remaining_turns)
                        # Highlight available market placeholder for dropping a card
                        highlight = False
                        # When dragging from hand: only FIRST free slot in each market is valid
                        if self.dragged_card_source == "hand":
                            # find first free slot for this market
                            first_free = None
                            for s in range(num_placeholders):
                                if self.market_cards[i].get(s) is None:
                                    first_free = s
                                    break
                            if first_free is not None and ph_idx == first_free:
                                highlight = True
                        # When dragging from market:
                        elif self.dragged_card_source == "market":
                            src_market = self.dragged_card_market
                            src_slot = self.dragged_card_market_slot
                            # 1) highlight the placeholder we dragged from (it becomes logically free)
                            if i == src_market and ph_idx == src_slot:
                                highlight = True
                            else:
                                # 2) for other markets, highlight only their FIRST free placeholder
                                if i != src_market:
                                    first_free = None
                                    for s in range(num_placeholders):
                                        if self.market_cards[i].get(s) is None:
                                            first_free = s
                                            break
                                    if first_free is not None and ph_idx == first_free:
                                        highlight = True
                        if highlight:
                            pygame.draw.rect(self.screen, GOLD, ph_rect, 4)
                
                # Draw price animation in center of frame if currently animating this market
                if (self.current_price_animation and 
                    self.current_price_animation['market'] == i):
                    anim_frame_idx = self.current_price_animation['frame_idx']
                    anim_type = self.current_price_animation.get('type', 'unchanged')
                    
                    # Select frames based on animation type
                    if anim_type == 'unchanged' and self.price_unchanged_frames:
                        frames = self.price_unchanged_frames
                    elif anim_type == 'rise' and self.price_rise_frames:
                        frames = self.price_rise_frames
                    elif anim_type == 'fall' and self.price_fall_frames:
                        frames = self.price_fall_frames
                    else:
                        frames = []
                    
                    if frames and anim_frame_idx < len(frames):
                        anim_img = frames[anim_frame_idx]
                        # Center animation in frame (84x72) and move up by 20 pixels
                        anim_x = frame_x + (frame_width - self.animation_width) // 2
                        anim_y = frame_y + (frame_height - self.animation_height) // 2 - 20
                        self.screen.blit(anim_img, (anim_x, anim_y))

        # Draw bottom frame (strategy cards area)
        if self.bottom_frame:
            bf_w = self.bottom_frame.get_width()
            bf_h = self.bottom_frame.get_height()
            # Position symmetrically with the three upper frames (same left offset of 200px)
            bf_x = (SCREEN_WIDTH - bf_w) // 2 - 200
            # Position it above bottom margin similar to screenshot, moved up 50px
            bf_y = SCREEN_HEIGHT - bf_h - 150
            self.screen.blit(self.bottom_frame, (bf_x, bf_y))

            # Draw hand placeholders evenly inside bottom frame
            if self.hand > 0:
                self.bottom_placeholders = []
                ph_w = 138   # Bottom placeholder width (40% larger than 96)
                ph_h = 240  # Bottom placeholder height (40% larger than 168)
                # Equal spacing pattern, но чуть плотнее (меньше промежутков), при этом группа по центру рамки
                base_spacing = (bf_w - ph_w * self.hand) / (self.hand + 1)
                spacing = base_spacing * 0.7
                total_width = ph_w * self.hand + spacing * (self.hand - 1)
                start_x = bf_x + (bf_w - total_width) / 2
                start_y = bf_y + (bf_h - ph_h) // 2

                for i in range(self.hand):
                    slot_x = start_x + i * (ph_w + spacing)
                    slot_y = start_y
                    self.bottom_placeholders.append({
                        'slot': i,
                        'rect': pygame.Rect(slot_x, slot_y, ph_w, ph_h)
                    })
                    # Draw placeholder
                    if self.placeholder_bottom:
                        self.screen.blit(self.placeholder_bottom, (slot_x, slot_y))
                    else:
                        pygame.draw.rect(self.screen, WHITE, (slot_x, slot_y, ph_w, ph_h))
                        pygame.draw.rect(self.screen, BLACK, (slot_x, slot_y, ph_w, ph_h), 2)
                    
                    # Draw card on placeholder if available and not being dragged
                    if i < len(self.hand_cards) and i != self.dragged_card_index:
                        card_id = self.hand_cards[i]
                        # Если для этой карты есть анимация сдвига, не рисуем её в стандартной позиции
                        moving_from_this_slot = False
                        if self.hand_compact_anim:
                            for move in self.hand_compact_anim:
                                if move["from_index"] == i and move["card_id"] == card_id:
                                    moving_from_this_slot = True
                                    break
                        # Если для этого слота есть анимация добора, не рисуем карту в стандартной позиции
                        drawing_to_this_slot = False
                        if self.hand_draw_anim:
                            for draw_entry in self.hand_draw_anim:
                                if draw_entry["target_slot"] == i:
                                    drawing_to_this_slot = True
                                    break
                        if (
                            not moving_from_this_slot
                            and not drawing_to_this_slot
                            and card_id is not None
                            and card_id in self.card_images_bottom
                            and self.card_images_bottom[card_id]
                        ):
                            # Center card on placeholder (card is 4px larger)
                            card_x = slot_x - 2  # Center horizontally
                            card_y = slot_y - 2  # Center vertically
                            self.screen.blit(self.card_images_bottom[card_id], (card_x, card_y))
                            # Draw CardAction if this card has one
                            self.draw_card_action(card_id, card_x, card_y, self.card_size_bottom)
                            # Draw CardTurns if this card has one
                            self.draw_card_turns(card_id, card_x, card_y, self.card_size_bottom)
                    # Highlight available hand placeholder when dragging from market:
                    # only the ORIGINAL hand slot of this card
                    if self.dragged_card_source == "market":
                        src_market = self.dragged_card_market
                        src_slot = self.dragged_card_market_slot
                        origin_slot = self.market_card_origins[src_market].get(src_slot)
                        if origin_slot is not None and i == origin_slot and self.hand_cards[i] is None:
                            ph_rect = pygame.Rect(slot_x, slot_y, ph_w, ph_h)
                            pygame.draw.rect(self.screen, GOLD, ph_rect, 4)
        
        # Draw dragged card on top of everything
        if self.dragged_card_source == "hand" and self.dragged_card_index is not None and self.dragged_card_index < len(self.hand_cards):
            card_id = self.hand_cards[self.dragged_card_index]
            if card_id in self.card_images_bottom and self.card_images_bottom[card_id]:
                # Draw card at mouse position with offset
                card_x = self.dragged_card_pos[0] - self.drag_offset[0]
                card_y = self.dragged_card_pos[1] - self.drag_offset[1]
                self.screen.blit(self.card_images_bottom[card_id], (card_x, card_y))
                # Draw CardAction if this card has one
                self.draw_card_action(card_id, card_x, card_y, self.card_size_bottom)
                # Draw CardTurns if this card has one
                self.draw_card_turns(card_id, card_x, card_y, self.card_size_bottom)
        # Draw dragged card from market on top
        if self.dragged_card_source == "market" and self.dragged_card_market is not None:
            card_id = self.market_cards[self.dragged_card_market].get(self.dragged_card_market_slot)
            if card_id is not None and card_id in self.card_images_market and self.card_images_market[card_id]:
                card_x = self.dragged_card_pos[0] - self.drag_offset[0]
                card_y = self.dragged_card_pos[1] - self.drag_offset[1]
                self.screen.blit(self.card_images_market[card_id], (card_x, card_y))
                # Draw CardAction if this card has one
                self.draw_card_action(card_id, card_x, card_y, self.card_size_market)
                # Draw CardTurns if this card has one - use remaining turns from market_card_turns
                remaining_turns = self.market_card_turns[self.dragged_card_market].get(self.dragged_card_market_slot)
                self.draw_card_turns(card_id, card_x, card_y, self.card_size_market, turns_remaining=remaining_turns)

        # Draw hand compaction animations on top (когда карты плавно сдвигаются влево)
        if self.hand_compact_anim:
            for move in self.hand_compact_anim:
                card_id = move["card_id"]
                if (
                    card_id is None
                    or card_id not in self.card_images_bottom
                    or not self.card_images_bottom[card_id]
                ):
                    continue
                (from_x, from_y) = move["from_pos"]
                (to_x, to_y) = move["to_pos"]
                t = move.get("progress", 0.0)
                t = max(0.0, min(1.0, t))
                card_x = from_x + (to_x - from_x) * t - 2
                card_y = from_y + (to_y - from_y) * t - 2
                self.screen.blit(self.card_images_bottom[card_id], (card_x, card_y))
                # Draw CardAction if this card has one
                self.draw_card_action(card_id, card_x, card_y, self.card_size_bottom)
                # Draw CardTurns if this card has one
                self.draw_card_turns(card_id, card_x, card_y, self.card_size_bottom)
        
        # Draw hand draw animations on top (когда карты прилетают снизу экрана)
        if self.hand_draw_anim:
            for draw_entry in self.hand_draw_anim:
                card_id = draw_entry["card_id"]
                if (
                    card_id is None
                    or card_id not in self.card_images_bottom
                    or not self.card_images_bottom[card_id]
                ):
                    continue
                (from_x, from_y) = draw_entry["from_pos"]
                (to_x, to_y) = draw_entry["target_pos"]
                t = draw_entry.get("progress", 0.0)
                t = max(0.0, min(1.0, t))
                card_x = from_x + (to_x - from_x) * t - 2
                card_y = from_y + (to_y - from_y) * t - 2
                self.screen.blit(self.card_images_bottom[card_id], (card_x, card_y))
                # Draw CardAction if this card has one
                self.draw_card_action(card_id, card_x, card_y, self.card_size_bottom)
                # Draw CardTurns if this card has one
                self.draw_card_turns(card_id, card_x, card_y, self.card_size_bottom)
        
        # Draw Day counter and End Turn button in bottom-right corner
        if self.end_button and self.end_button_rect:
            # Button position is already set in __init__, just draw it
            self.screen.blit(self.end_button, self.end_button_rect)
            
            # Draw Day counter to the left of the button
            day_text = self.font_medium.render(f"Day: {self.Day} /{self.LastTurn}", True, PAPER_COLOR)
            day_text_x = self.end_button_rect.x - day_text.get_width() - 20  # 20px spacing from button
            day_text_y = self.end_button_rect.y + (self.end_button_rect.height - day_text.get_height()) // 2  # Vertically centered with button
            self.screen.blit(day_text, (day_text_x, day_text_y))
        
        # Draw WinLose screen if win/lose state is active
        if self.win_lose_state is not None and self.win_lose_image:
            win_lose_y_draw = int(round(self.win_lose_y))
            # Draw WinLose window at centered position
            self.screen.blit(self.win_lose_image, (self.win_lose_x, win_lose_y_draw))
            
            # Draw appropriate Ok button based on win/lose state
            ok_button = None
            if self.win_lose_state == "win" and self.ok1_button:
                ok_button = self.ok1_button
            elif self.win_lose_state == "lose" and self.ok2_button:
                ok_button = self.ok2_button
            
            if ok_button:
                # Calculate button position relative to WinLose window
                winlose_width = self.win_lose_image.get_width()
                winlose_height = self.win_lose_image.get_height()
                ok_margin_right = 30
                ok_margin_bottom = 30
                ok_x = self.win_lose_x + winlose_width - self.ok_button_base_size[0] - ok_margin_right
                ok_y = win_lose_y_draw + winlose_height - self.ok_button_base_size[1] - ok_margin_bottom
                self.ok_button_rect = pygame.Rect(int(ok_x), int(ok_y), self.ok_button_base_size[0], self.ok_button_base_size[1])
                self.screen.blit(ok_button, (int(ok_x), int(ok_y)))
            
            # Draw text and cards on WinLose window
            winlose_width = self.win_lose_image.get_width()
            winlose_height = self.win_lose_image.get_height()
            
            if self.win_lose_state == "win":
                # Draw reward text - split into multiple lines if needed
                text_y = win_lose_y_draw + 75  # Top padding (40 + 35)
                max_text_width = winlose_width - 40  # Leave 20px margin on each side
                
                # Split text into lines if it's too long
                lines = wrap_text(self.reward_window_text, self.font_small, max_text_width)
                
                # Draw text lines
                line_height = self.font_small.get_height() + 5
                for i, line in enumerate(lines):
                    text_surface = self.font_small.render(line, True, PAPER_COLOR)
                    text_x = self.win_lose_x + (winlose_width - text_surface.get_width()) // 2
                    self.screen.blit(text_surface, (text_x, text_y + i * line_height))
                
                # Draw reward cards below text
                if self.last_earned_cards:
                    text_bottom_y = text_y + len(lines) * line_height
                    card_start_y = text_bottom_y + 5  # 5px spacing (20 - 15)
                    card_width_winlose = 100  # Increased card size
                    card_spacing = 10  # Spacing between cards
                    total_cards_width = len(self.last_earned_cards) * card_width_winlose + (len(self.last_earned_cards) - 1) * card_spacing
                    card_start_x = self.win_lose_x + (winlose_width - total_cards_width) // 2  # Center cards
                    
                    for i, card_number in enumerate(self.last_earned_cards):
                        card_image = self._load_winlose_card(card_number)
                        if card_image:
                            card_x = card_start_x + i * (card_width_winlose + card_spacing)
                            self.screen.blit(card_image, (card_x, card_start_y))
            elif self.win_lose_state == "lose":
                # Draw lose text
                text_y = win_lose_y_draw + 85  # Top padding (50 + 35)
                text_surface = self.font_small.render(self.lose_window_text, True, PAPER_COLOR)
                text_x = self.win_lose_x + (winlose_width - text_surface.get_width()) // 2  # Center horizontally
                self.screen.blit(text_surface, (text_x, text_y))
            
            if not ok_button:
                # Debug: why button is not shown
                if self.win_lose_state == "lose":
                    print(f"DEBUG: Ok2 button not shown. ok2_button exists: {self.ok2_button is not None}, win_lose_state: {self.win_lose_state}")
        
        pygame.display.flip()
    
    def run(self):
        while True:
            result = self.handle_input()
            
            if result == "quit":
                pygame.quit()
                sys.exit()
            
            if result == "back":
                return "back"
            
            if result == "round_select":
                return "round_select"
            
            if result == "level_select":
                return "level_select"
            
            # Update dragged card position every frame for maximum smoothness
            # This ensures position is updated even if MOUSEMOTION events are missed
            if self.dragged_card_source is not None:
                self.dragged_card_pos = pygame.mouse.get_pos()
            
            # Update arrow animation timing
            self.update_arrow_animation()
            
            # Update price animation timing
            self.update_price_animation()

            # Update card jump animations
            self.update_card_jump_animations()
            
            # Update sequential processing of cards 11-18
            self.update_cards_11_14_processing()

            # Update hand compaction animation after end turn
            self.update_hand_compact_animation()
            
            # Update hand draw animation (cards flying in from bottom)
            self.update_hand_draw_animation()
            
            # Update win/lose screen animation
            self.update_win_lose_animation()

            self.draw()
            self.clock.tick(FPS)


class BossPage:
    def __init__(self, screen, font_path, level_number, defeated_count=0, last_defeated_rect=None, saved_lines=None, defeated_bosses=None):
        self.screen = screen
        self.clock = pygame.time.Clock()
        self.level_number = level_number
        self.defeated_count = defeated_count
        self.last_defeated_rect = last_defeated_rect
        self.saved_lines = list(saved_lines) if saved_lines else []
        self.defeated_bosses = list(defeated_bosses) if defeated_bosses else []
        self.clicked_boss_filename = None
        self.boss_image_cache = {}
        self.clicked_boss_rect = None
        
        # Load Back3.png from UI folder (same as level selection screen)
        back3_path = os.path.join("UI", "Back3.png")
        if os.path.exists(back3_path):
            self.background = pygame.image.load(back3_path).convert()
            self.background = pygame.transform.smoothscale(self.background, (SCREEN_WIDTH, SCREEN_HEIGHT)).convert()
        else:
            print("WARNING: Back3.png not found:", back3_path)
            self.background = None
        
        # Load Koordinates.png from RoundPage folder
        koordinates_path = os.path.join("RoundPage", "Koordinates.png")
        if os.path.exists(koordinates_path):
            self.koordinates = pygame.image.load(koordinates_path).convert_alpha()
            self.koordinates = pygame.transform.smoothscale(self.koordinates, (SCREEN_WIDTH, SCREEN_HEIGHT)).convert_alpha()
        else:
            print("WARNING: Koordinates.png not found:", koordinates_path)
            self.koordinates = None
        
        # Load bosses for current round index based on defeated_count
        round_index = self.defeated_count if self.defeated_count >= 0 else 0
        bosses_for_round = LEVEL_BOSS_ROUNDS.get(self.level_number, [[]])
        if round_index >= len(bosses_for_round):
            round_index = len(bosses_for_round) - 1 if bosses_for_round else 0
        self.current_boss_filenames = bosses_for_round[round_index] if bosses_for_round else []
        
        # Boss collections
        self.bosses = []  # Default boss images (non-animated)
        self.boss_rects = []
        self.boss_animation_frames = []  # Animation frames for each boss
        self.boss_base_names = []  # Base names for finding animation folders
        
        # Animation sequence: 0,1,2,3,2,1,0,4,5,6,5,4,0 and loop
        self.animation_sequence = [0, 1, 2, 3, 2, 1, 0, 4, 5, 6, 5, 4]
        self.animation_frame_duration = 100  # milliseconds per frame
        self.boss_hover_states = {}  # Track which boss is hovered and animation state
        
        # Load PopUp.png
        popup_path = os.path.join("Bosses", "PopUp.png")
        if os.path.exists(popup_path):
            popup_original = pygame.image.load(popup_path).convert_alpha()
            # Scale to 250x375 pixels
            self.popup_image = pygame.transform.smoothscale(popup_original, (250, 375)).convert_alpha()
        else:
            print(f"WARNING: PopUp.png not found: {popup_path}")
            self.popup_image = None
        
        # PopUp animation state
        self.popup_y = -200.0  # Start above screen (hidden) - float for smooth motion
        self.popup_x = 0
        self.popup_target_y = -200.0  # Target Y position
        self.popup_speed_pps = 1400.0  # pixels per second
        self._popup_last_tick = pygame.time.get_ticks()
        self.current_hovered_boss_index = None  # Track which boss is hovered for PopUp
        self.popup_boss_index = None  # Track which boss text to show (persists until PopUp hides)
        
        # Load font for PopUp text
        self.popup_font = pygame.font.Font(font_path, 24)
        
        # Map level and boss indices to text keys in Lang.csv
        # Format: {(level_number, boss_index): "LangKey"}
        self.boss_text_keys = {
            (1, 0): "Boss1Text",  # Boss 1 (Watt) for level 1
            (2, 0): "Boss2Text",  # Boss 2 (Adam Smith) for level 2
            (2, 1): "Boss3Text"   # Boss 3 (Robert Fulton) for level 2
            # Add more bosses here as needed: (level, boss_index): "BossXText", etc.
        }
        
        # Store boss texts
        self.boss_texts = {}
        for (level_num, boss_idx), text_key in self.boss_text_keys.items():
            if level_num == self.level_number:
                self.boss_texts[boss_idx] = get_text(text_key, text_key)
        
        # Load Pen sound
        pen_sound_path = os.path.join("Sounds", "Pen.mp3")
        if os.path.exists(pen_sound_path):
            self.pen_sound = pygame.mixer.Sound(pen_sound_path)
        else:
            print(f"WARNING: Pen.mp3 not found at {pen_sound_path}")
            self.pen_sound = None
        
        # Line drawing state
        self.line_color = (110, 90, 70)
        self.line_width = 10
        self.current_line = None  # (start_x, start_y, end_x, end_y) when hovering
        # saved_lines already copied in __init__
        self.last_hovered_boss = None  # Track to play sound only once per hover
        
        if self.current_boss_filenames:
            for boss_filename in self.current_boss_filenames:
                boss_path = os.path.join("Bosses", boss_filename)
                if os.path.exists(boss_path):
                    boss_image = pygame.image.load(boss_path).convert_alpha()
                    # Scale to 100x100
                    boss_image = pygame.transform.smoothscale(boss_image, (100, 100)).convert_alpha()
                    self.bosses.append(boss_image)
                    
                    # Extract base name (e.g., "1_Watt.png" -> "1_Watt")
                    base_name = os.path.splitext(boss_filename)[0]
                    self.boss_base_names.append(base_name)
                    
                    # Load animation frames from boss folder
                    boss_folder = os.path.join("Bosses", base_name)
                    animation_frames = []
                    if os.path.exists(boss_folder) and os.path.isdir(boss_folder):
                        # Load frames 0-6
                        for frame_num in range(7):
                            frame_filename = f"{base_name}{frame_num}.png"
                            frame_path = os.path.join(boss_folder, frame_filename)
                            if os.path.exists(frame_path):
                                frame_image = pygame.image.load(frame_path).convert_alpha()
                                frame_image = pygame.transform.smoothscale(frame_image, (100, 100)).convert_alpha()
                                animation_frames.append(frame_image)
                            else:
                                print(f"WARNING: Animation frame not found: {frame_path}")
                    else:
                        print(f"WARNING: Boss animation folder not found: {boss_folder}")
                    
                    self.boss_animation_frames.append(animation_frames)
                else:
                    print(f"WARNING: Boss file not found: {boss_path}")
                    self.bosses.append(None)
                    self.boss_base_names.append(None)
                    self.boss_animation_frames.append([])
        
        # Load defeated bosses passed in state (keep their positions)
        if saved_lines and isinstance(saved_lines, dict) and saved_lines.get("defeated_bosses"):
            # Legacy guard - not used now
            self.defeated_bosses = list(saved_lines.get("defeated_bosses"))
        elif hasattr(self, "saved_defeated_bosses"):
            self.defeated_bosses = list(self.saved_defeated_bosses)
        
        # Calculate boss positions
        # Use Smith/Fulton vertical spacing as a reference for all levels
        self.boss_vertical_spacing = 150
        start_x = 350
        start_y = SCREEN_HEIGHT - 400
        
        # If this is a subsequent boss round and we have last defeated rect, place relative to it
        if self.defeated_count > 0 and self.last_defeated_rect:
            anchor_cx, anchor_cy = self.last_defeated_rect.centerx, self.last_defeated_rect.centery
            positions = []
            if len(self.bosses) >= 1:
                positions.append((anchor_cx + 200, anchor_cy - self.boss_vertical_spacing))
            if len(self.bosses) >= 2:
                prev_cx, prev_cy = positions[0]
                positions.append((prev_cx, prev_cy - self.boss_vertical_spacing))
            
            for i, boss_image in enumerate(self.bosses):
                cx, cy = positions[i]
                self.boss_rects.append(pygame.Rect(cx - 50, cy - 50, 100, 100))
            
            # Lines start from last defeated boss center
            self.fixed_line_start_x = anchor_cx
            self.fixed_line_start_y = anchor_cy
        else:
            for i, boss_image in enumerate(self.bosses):
                boss_x = start_x
                boss_y = start_y - (i * self.boss_vertical_spacing)
                self.boss_rects.append(pygame.Rect(boss_x, boss_y, 100, 100))

            if len(self.boss_rects) > 0:
                first_boss_rect = self.boss_rects[0]
                self.fixed_line_start_x = first_boss_rect.centerx - 165
                self.fixed_line_start_y = first_boss_rect.centery + 132
            else:
                self.fixed_line_start_x = 350 + 50 - 165
                self.fixed_line_start_y = SCREEN_HEIGHT - 400 + 50 + 132
    
    def handle_input(self):
        mouse_pos = pygame.mouse.get_pos()
        
        # Check which boss is being hovered
        hovered_boss = None
        for i, boss_rect in enumerate(self.boss_rects):
            if boss_rect.collidepoint(mouse_pos):
                hovered_boss = i
                break
        
        # Update PopUp position and line based on hover
        if hovered_boss is not None:
            # Set target position for PopUp
            boss_rect = self.boss_rects[hovered_boss]
            self.popup_target_y = float(boss_rect.y - 250)  # Y coordinate of the boss
            self.popup_x = boss_rect.x + 100  # X = boss.x + 70
            self.current_hovered_boss_index = hovered_boss
            self.popup_boss_index = hovered_boss  # Save boss index for text display
            
            # Calculate line coordinates
            # Start: fixed point (same for all bosses) or last defeated boss center if provided
            line_start_x = self.fixed_line_start_x
            line_start_y = self.fixed_line_start_y
            # End: boss center coordinates (depends on selected boss)
            line_end_x = boss_rect.centerx
            line_end_y = boss_rect.centery
            self.current_line = (line_start_x, line_start_y, line_end_x, line_end_y)
            
            # Play sound only once when starting to hover
            if self.last_hovered_boss != hovered_boss:
                if self.pen_sound:
                    self.pen_sound.play()
                self.last_hovered_boss = hovered_boss
        else:
            # Move PopUp back above screen when not hovering
            self.popup_target_y = -350.0
            self.current_hovered_boss_index = None
            # Don't clear popup_boss_index here - let it persist until PopUp is hidden
            self.current_line = None  # Clear line when not hovering
            self.last_hovered_boss = None
        
        # Update hover states
        for i in range(len(self.boss_rects)):
            if i == hovered_boss:
                if i not in self.boss_hover_states:
                    # Start animation for this boss
                    self.boss_hover_states[i] = {
                        'sequence_index': 0,
                        'last_frame_time': pygame.time.get_ticks()
                    }
            else:
                # Stop animation if not hovered
                if i in self.boss_hover_states:
                    del self.boss_hover_states[i]
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"
            
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return "back"
            
            # Handle boss click
            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # Left click
                    for i, boss_rect in enumerate(self.boss_rects):
                        if boss_rect.collidepoint(mouse_pos):
                            # Save line coordinates when clicking
                            if self.current_line:
                                self.saved_lines.append(self.current_line)
                            # Remember clicked boss rect
                            self.clicked_boss_rect = boss_rect.copy()
                            # Remember clicked boss filename
                            if i < len(self.current_boss_filenames):
                                self.clicked_boss_filename = self.current_boss_filenames[i]
                            # Return boss selection (level_number, boss_index)
                            return f"boss_{self.level_number}_{i}"
        
        return None
    
    def draw(self):
        # Background
        if self.background:
            self.screen.blit(self.background, (0, 0))
        else:
            self.screen.fill(BLACK)
        
        # Draw Koordinates.png overlay (above background, below other objects)
        if self.koordinates:
            self.screen.blit(self.koordinates, (0, 0))
        
        # Update PopUp position with dt-based smooth animation (stable across FPS)
        now = pygame.time.get_ticks()
        dt = (now - getattr(self, "_popup_last_tick", now)) / 1000.0
        self._popup_last_tick = now
        dt = _clamp_dt_seconds(dt)
        max_delta = float(getattr(self, "popup_speed_pps", 0.0)) * dt
        self.popup_y = move_towards(float(self.popup_y), float(self.popup_target_y), max_delta)
        
        # Draw saved lines (if bosses were clicked)
        for line in self.saved_lines:
            if line:
                start_x, start_y, end_x, end_y = line
            pygame.draw.line(self.screen, self.line_color, (start_x, start_y), (end_x, end_y), self.line_width)
        
        # Draw current line (when hovering over boss) - UNDER the boss
        if self.current_line:
            start_x, start_y, end_x, end_y = self.current_line
            pygame.draw.line(self.screen, self.line_color, (start_x, start_y), (end_x, end_y), self.line_width)
        
        # Draw defeated bosses (persist on screen)
        for defeated in self.defeated_bosses:
            filename = defeated.get("filename")
            rect = defeated.get("rect")
            if not filename or not rect:
                continue
            if filename in self.boss_image_cache:
                img = self.boss_image_cache[filename]
            else:
                path = os.path.join("Bosses", filename)
                img = None
                if os.path.exists(path):
                    img = pygame.image.load(path).convert_alpha()
                    img = pygame.transform.smoothscale(img, (100, 100)).convert_alpha()
                self.boss_image_cache[filename] = img
            if img:
                self.screen.blit(img, rect.topleft)
        
        # Update animations and draw bosses
        current_time = pygame.time.get_ticks()
        
        for i, (boss_image, boss_rect) in enumerate(zip(self.bosses, self.boss_rects)):
            # Check if this boss is being hovered and has animation frames
            if i in self.boss_hover_states and len(self.boss_animation_frames[i]) > 0:
                # Update animation
                hover_state = self.boss_hover_states[i]
                time_since_last_frame = current_time - hover_state['last_frame_time']
                
                if time_since_last_frame >= self.animation_frame_duration:
                    # Move to next frame in sequence
                    hover_state['sequence_index'] = (hover_state['sequence_index'] + 1) % len(self.animation_sequence)
                    hover_state['last_frame_time'] = current_time
                
                # Get current frame number from sequence
                frame_index = self.animation_sequence[hover_state['sequence_index']]
                
                # Draw animated frame if available
                if frame_index < len(self.boss_animation_frames[i]):
                    self.screen.blit(self.boss_animation_frames[i][frame_index], boss_rect.topleft)
                else:
                    # Fallback to default image if frame not available
                    self.screen.blit(boss_image, boss_rect.topleft)
            else:
                # Draw default boss image when not hovered
                self.screen.blit(boss_image, boss_rect.topleft)
        
        # Draw PopUp if it's visible (not completely above screen)
        if self.popup_image and self.popup_y > -self.popup_image.get_height():
            popup_y_draw = int(round(self.popup_y))
            self.screen.blit(self.popup_image, (self.popup_x, popup_y_draw))
            
            # Draw text on PopUp if a boss text is available (persists until PopUp hides)
            if self.popup_boss_index is not None and self.popup_boss_index in self.boss_texts:
                text = self.boss_texts[self.popup_boss_index]
                
                # Split text into multiple lines to fit in PopUp (250px wide)
                max_width = 200  # Leave more padding (250 - 50px total padding) to prevent text overflow
                words = text.split()
                lines = []
                current_line = []
                current_width = 0
                
                for word in words:
                    word_surface = self.popup_font.render(word + " ", True, PAPER_COLOR)
                    word_width = word_surface.get_width()
                    
                    if current_width + word_width <= max_width:
                        current_line.append(word)
                        current_width += word_width
                    else:
                        if current_line:
                            lines.append(" ".join(current_line))
                        current_line = [word]
                        current_width = word_width
                
                if current_line:
                    lines.append(" ".join(current_line))
                
                # Draw text lines on PopUp
                text_start_x = self.popup_x + 15  # Left padding
                text_start_y = popup_y_draw + 120  # Top padding
                line_height = self.popup_font.get_height() + 5  # 5px spacing between lines
                
                for i, line in enumerate(lines):
                    text_surface = self.popup_font.render(line, True, PAPER_COLOR)
                    self.screen.blit(text_surface, (text_start_x, text_start_y + i * line_height))
        else:
            # PopUp is completely hidden, clear the boss index for text
            if self.popup_boss_index is not None:
                self.popup_boss_index = None
        
        pygame.display.flip()
    
    def run(self):
        while True:
            result = self.handle_input()
            
            if result == "quit":
                pygame.quit()
                sys.exit()
            
            if result == "back":
                return "back"
            
            if result and result.startswith("boss_"):
                return result
            
            self.draw()
            self.clock.tick(FPS)


class RoundPage:
    def __init__(self, screen, font_path, level_number, boss_index, boss_filename=None, test_mode=False):
        self.screen = screen
        self.clock = pygame.time.Clock()
        self.level_number = level_number
        self.boss_index = boss_index
        self.boss_filename = boss_filename
        self.test_mode = test_mode
        self.font_path = font_path  # Save font path for dynamic font creation
        
        # Load Back3.png from UI folder (same as level selection screen)
        back3_path = os.path.join("UI", "Back3.png")
        if os.path.exists(back3_path):
            self.background = pygame.image.load(back3_path).convert()
            self.background = pygame.transform.smoothscale(self.background, (SCREEN_WIDTH, SCREEN_HEIGHT)).convert()
        else:
            print("WARNING: Back3.png not found:", back3_path)
            self.background = None
        
        # Load Koordinates.png from RoundPage folder
        koordinates_path = os.path.join("RoundPage", "Koordinates.png")
        if os.path.exists(koordinates_path):
            self.koordinates = pygame.image.load(koordinates_path).convert_alpha()
            self.koordinates = pygame.transform.smoothscale(self.koordinates, (SCREEN_WIDTH, SCREEN_HEIGHT)).convert_alpha()
        else:
            print("WARNING: Koordinates.png not found:", koordinates_path)
            self.koordinates = None
        
        # Load buttons and scale down by 5x
        # E = bottom, M = middle, H = upper
        button_e_path = os.path.join("RoundPage", "LevelButtonE.png")
        button_m_path = os.path.join("RoundPage", "LevelButtonM.png")
        button_h_path = os.path.join("RoundPage", "LevelButtonH.png")
        
        if os.path.exists(button_e_path):
            button_e_original = pygame.image.load(button_e_path).convert_alpha()
            # Scale down by 5x (divide by 5)
            new_width = button_e_original.get_width() // 5
            new_height = button_e_original.get_height() // 5
            self.button_e = pygame.transform.smoothscale(button_e_original, (new_width, new_height)).convert_alpha()
        else:
            print("WARNING: LevelButtonE not found:", button_e_path)
            self.button_e = None
        
        if os.path.exists(button_m_path):
            button_m_original = pygame.image.load(button_m_path).convert_alpha()
            # Scale down by 5x (divide by 5)
            new_width = button_m_original.get_width() // 5
            new_height = button_m_original.get_height() // 5
            self.button_m = pygame.transform.smoothscale(button_m_original, (new_width, new_height)).convert_alpha()
        else:
            print("WARNING: LevelButtonM not found:", button_m_path)
            self.button_m = None
        
        if os.path.exists(button_h_path):
            button_h_original = pygame.image.load(button_h_path).convert_alpha()
            # Scale down by 5x (divide by 5)
            new_width = button_h_original.get_width() // 5
            new_height = button_h_original.get_height() // 5
            self.button_h = pygame.transform.smoothscale(button_h_original, (new_width, new_height)).convert_alpha()
        else:
            print("WARNING: LevelButtonH not found:", button_h_path)
            self.button_h = None
        
        # Load round configuration (round count + per-difficulty goals) from RoundsData.csv
        self.rounds_config = self._load_rounds_data()
        level_cfg = self.rounds_config.get(self.level_number, {})
        
        # Determine boss selection for level 2
        self.boss_selection = 0  # Default to first boss
        if self.level_number == 2:
            self.boss_selection = get_boss_selection_from_filename(self.level_number, self.boss_filename)
        
        # How many rounds must be completed before the boss unlocks
        rounds_cfg_value = level_cfg.get("Rounds")
        self.rounds_required = rounds_cfg_value if rounds_cfg_value and rounds_cfg_value > 0 else 1
        
        # Track completed rounds: integers starting at 1
        self.completed_rounds = set()
        # Store selected button per round: {round_num: {"key": "e/m/h", "rect": Rect}}
        self.round_selections = {}
        
        # Current goal (will be set when a button is clicked)
        self.Goal = None
        
        # Track last selected round number (1-based order)
        self.last_selected_round = None
        
        # Per-button goals (None means the button should be hidden)
        # For level 2, goals will be set dynamically based on round number
        # For other levels, use RoundsData.csv
        if self.level_number == 2:
            # For level 2, initialize goals from GoalsLevel2.csv for round 1
            # This ensures buttons are visible from the start
            e_goal = get_level2_goal(1, "e", self.boss_selection, False)
            m_goal = get_level2_goal(1, "m", self.boss_selection, False)
            # Fallback to default values if goals are not found
            if e_goal is None:
                e_goal = 50  # Default fallback
            if m_goal is None:
                m_goal = 70  # Default fallback
            self.button_goals = {
                "e": e_goal,
                "m": m_goal,
                "h": None
            }
        else:
            self.button_goals = {
                "e": level_cfg.get("E"),
                "m": level_cfg.get("M"),
                "h": level_cfg.get("H")
            }
        
        self.bosses_required = level_cfg.get("Bosses") or 1
        
        # Hide buttons that are not configured for this level
        # For level 2, E and M buttons are always available (loaded from GoalsLevel2.csv)
        if self.level_number != 2:
            if self.button_goals["e"] is None:
                self.button_e = None
            if self.button_goals["m"] is None:
                self.button_m = None
        if self.button_goals["h"] is None:
            self.button_h = None
        
        # Calculate button positions based on which buttons are available
        self.button_e_rect = None
        self.button_m_rect = None
        self.button_h_rect = None
        # Base rects (round 1 layout) used for all levels; later rounds shift from these
        self.button_base_rects = {"e": None, "m": None, "h": None}
        button_x = 350
        base_y = SCREEN_HEIGHT - 400
        spacing = 36  # Increased by 20% (was 30)
        current_y = base_y

        for key in ["e", "m", "h"]:  # Fixed bottom-to-top order
            img = None
            if key == "e":
                img = self.button_e if self.button_goals.get("e") is not None else None
            elif key == "m":
                img = self.button_m if self.button_goals.get("m") is not None else None
            elif key == "h":
                img = self.button_h if self.button_goals.get("h") is not None else None

            if not img:
                continue

            w, h = img.get_width(), img.get_height()
            rect = pygame.Rect(button_x, current_y, w, h)
            self.button_base_rects[key] = rect
            current_y -= (h + spacing)
        
        # Initialize current rects for the first active round
        self._refresh_button_rects()
        
        # Load PopUp2.png for RoundPage (larger window)
        popup_path = os.path.join("Bosses", "PopUp2.png")
        if not os.path.exists(popup_path):
            popup_path = os.path.join("Bosses", "PopUp2.jpg")
        if os.path.exists(popup_path):
            popup_original = pygame.image.load(popup_path).convert_alpha()
            # Get original dimensions to maintain aspect ratio
            original_width = popup_original.get_width()
            original_height = popup_original.get_height()
            # Scale down by 2x and then reduce by 20% (reduce to 40% of original size)
            scaled_width = int((original_width // 2) * 0.8)
            scaled_height = int((original_height // 2) * 0.8)
            self.popup_image = pygame.transform.smoothscale(popup_original, (scaled_width, scaled_height)).convert_alpha()
            # Store popup width for positioning calculations
            self.popup_width = scaled_width
        else:
            print(f"WARNING: PopUp2.png/PopUp2.jpg not found: {popup_path}")
            self.popup_image = None
            self.popup_width = 250  # Fallback to old width
        
        # PopUp animation state
        self.popup_y = -400.0  # Start above screen (hidden) - float for smooth motion
        self.popup_x = 0
        self.popup_target_y = -400.0  # Target Y position
        self.popup_speed_pps = 1400.0  # pixels per second
        self._popup_last_tick = pygame.time.get_ticks()
        self.popup_button = None  # Track which button text to show (persists until PopUp hides)
        
        # Load font for PopUp text
        self.popup_font = pygame.font.Font(font_path, 24)
        
        # Load PopUpRound text from Lang.csv
        self.popup_round_text = get_text("PopUpRound", "PopUpRound")
        # Load PopUpReward text from Lang.csv
        self.popup_reward_text = get_text("PopUpReward", "PopUpReward")
        
        # Map level and boss indices to reward text keys in Lang.csv for boss PopUp display on RoundPage
        # Format: {(level_number, boss_index): "LangKey"}
        # On RoundPage, we show BossReward (reward description), not BossText (full description)
        self.boss_reward_keys = {
            (1, 0): "Boss1Reward",  # Boss 1 (Watt) for level 1
            (2, 0): "Boss2Reward",  # Boss 2 (Adam Smith) for level 2
            (2, 1): "Boss3Reward"   # Boss 3 (Robert Fulton) for level 2
            # Add more bosses here as needed: (level, boss_index): "BossXReward", etc.
        }
        
        # Store boss reward text for current level
        # For level 2, use boss_selection (determined from filename); for level 1, use boss_index
        self.boss_text = None
        boss_idx_for_text = self.boss_selection if self.level_number == 2 else self.boss_index
        if (self.level_number, boss_idx_for_text) in self.boss_reward_keys:
            text_key = self.boss_reward_keys[(self.level_number, boss_idx_for_text)]
            self.boss_text = get_text(text_key, text_key)
        
        # Load rewards from Rewards.csv
        # Format: {(level, round, button): {'reward1': [list of card_numbers or single int], 'reward2': card_number or None}}
        self.rewards = {}
        rewards_file = "Rewards.csv"
        if os.path.exists(rewards_file):
            try:
                with open(rewards_file, 'r', encoding='utf-8-sig') as f:
                    reader = csv.DictReader(f, delimiter=';')
                    for row in reader:
                        level = int(row.get('Level', 0))
                        round_num = int(row.get('Round', 0))
                        button_val = row.get('Button') or ''
                        button = button_val.strip().upper() if button_val else ''
                        reward1_val = row.get('Reward1') or ''
                        reward1_str = reward1_val.strip() if reward1_val else ''
                        reward2_val = row.get('Reward2') or ''
                        reward2_str = reward2_val.strip() if reward2_val else ''
                        reward_text_val = row.get('Text') or ''
                        reward_text = reward_text_val.strip() if reward_text_val else ''
                        
                        if level > 0 and round_num > 0 and button and reward1_str:
                            # Parse Reward1 - can be single card or multiple cards separated by comma
                            reward1_list = []
                            for card_str in reward1_str.split(','):
                                card_str = card_str.strip()
                                if card_str:
                                    try:
                                        card_num = int(card_str)
                                        if card_num == 0:
                                            card_num = 100
                                        reward1_list.append(card_num)
                                    except ValueError:
                                        pass
                            
                            if reward1_list:
                                # Parse Reward2 - can be single card, multiple cards separated by comma, or None
                                reward2_list = []
                                if reward2_str and reward2_str.strip():
                                    for card_str in reward2_str.split(','):
                                        card_str = card_str.strip()
                                        if card_str:
                                            try:
                                                card_num = int(card_str)
                                                if card_num == 0:
                                                    card_num = 100
                                                if card_num >= 0:  # Allow 0 as valid card
                                                    reward2_list.append(card_num)
                                            except ValueError:
                                                pass
                                
                                reward_entry = {
                                    'reward1': reward1_list,
                                    'reward2': reward2_list if reward2_list else None,
                                    'text': reward_text if reward_text else None
                                }
                                self.rewards[(level, round_num, button)] = reward_entry
            except Exception as e:
                print(f"ERROR loading rewards file: {e}")
                import traceback
                traceback.print_exc()
        
        # Load RandomDropGain.png image for random rewards
        random_drop_path = os.path.join("RoundPage", "RandomDropGain.png")
        if os.path.exists(random_drop_path):
            random_drop_original = pygame.image.load(random_drop_path).convert_alpha()
            # Scale to match PopUp card size (100x172)
            target_width = 100
            market_card_ratio = 99 / 171.0
            target_height = int(target_width / market_card_ratio)
            self.random_drop_image = pygame.transform.smoothscale(random_drop_original, (target_width, target_height)).convert_alpha()
        else:
            print(f"WARNING: RandomDropGain.png not found: {random_drop_path}")
            self.random_drop_image = None
        
        # Cache for loaded reward card images
        self.reward_card_images = {}
        
        # Card base mapping: which base image to use for each card
        # Cards 11, 12, 13, 14 use Card_11.png as base
        # Cards 15, 16 use Card_15.png as base
        # Cards 17, 18 use Card_17.png as base
        self.card_base_mapping = {}
        for card_id in (1, 2, 3, 4, 100):
            self.card_base_mapping[card_id] = card_id  # Original cards use their own images
        self.card_base_mapping[11] = 11
        self.card_base_mapping[12] = 11
        self.card_base_mapping[13] = 11
        self.card_base_mapping[14] = 11
        self.card_base_mapping[15] = 15
        self.card_base_mapping[16] = 15
        self.card_base_mapping[17] = 17
        self.card_base_mapping[18] = 17
        
        # Card actions and turns for dynamic cards
        self.card_actions = {
            11: 2, 12: 2, 13: 4, 14: 4,
            15: -2, 16: -2, 17: 2, 18: 2
        }
        self.card_turns = {
            11: 1, 13: 1, 12: 2, 14: 2,
            15: 1, 16: 2, 17: 1, 18: 2
        }
        
        # Load Pen sound
        pen_sound_path = os.path.join("Sounds", "Pen.mp3")
        if os.path.exists(pen_sound_path):
            self.pen_sound = pygame.mixer.Sound(pen_sound_path)
        else:
            print(f"WARNING: Pen.mp3 not found at {pen_sound_path}")
            self.pen_sound = None
        
        # Line drawing state
        self.line_color = (100, 82, 64)  # Color as specified
        self.line_width = 10
        self.current_line = None  # (start_x, start_y, end_x, end_y) when hovering button
        self.boss_current_line = None  # (start_x, start_y, end_x, end_y) when hovering boss
        self.saved_lines = []  # list of (start_x, start_y, end_x, end_y) when clicked
        self.last_hovered_button = None  # Track to play sound only once per hover
        
        self.hovered_button = None  # Track which button is hovered
        
        # Track last selected round
        self.last_selected_round = None  # 1 for E, 2 for M, 3 for H
        
        # Load boss icon if all rounds are completed
        self.boss_icon = None
        self.boss_icon_rect = None
        self.boss_animation_frames = []  # Animation frames for boss
        self.boss_hover_state = None  # Track boss hover and animation state
        self.animation_sequence = [0, 1, 2, 3, 2, 1, 0, 4, 5, 6, 5, 4]  # Same as BossPage
        self.animation_frame_duration = 100  # milliseconds per frame
        
        # Boss goals: {boss_key: goal_value}
        # For level 2, goals will be loaded dynamically from GoalsLevel2.csv
        self.boss_goals = {
            (1, 0): 60,  # Boss 1_Watt (level 1, boss index 0) Goal = 60
        }
        
        # For level 2, boss goals are determined dynamically based on boss_selection
        # They will be set when the boss is clicked
        
        self._load_boss_icon_if_needed()
    
    def _get_round_offset(self, round_num):
        """Calculate positional offset for a given round (round 1 has zero offset)."""
        if not round_num or round_num <= 1:
            return 0, 0
        # Each subsequent round shifts +150 on X and -80 on Y
        shift = round_num - 1
        return 150 * shift, -80 * shift
    
    def _refresh_button_goals(self):
        """Update button goals based on current round for level 2."""
        if self.level_number != 2:
            return
        
        current_round = self.get_current_active_round()
        if current_round is None:
            return
        
        # Update goals from GoalsLevel2.csv
        e_goal = get_level2_goal(current_round, "e", self.boss_selection, False)
        m_goal = get_level2_goal(current_round, "m", self.boss_selection, False)
        
        self.button_goals["e"] = e_goal
        self.button_goals["m"] = m_goal
    
    def _refresh_button_rects(self):
        """Recompute button rects based on the current active round with offsets."""
        current_round = self.get_current_active_round()
        if current_round is None:
            # All rounds completed; keep last round's offset for consistency
            current_round = self.rounds_required
        offset_x, offset_y = self._get_round_offset(current_round)
        
        def shift_rect(base_rect):
            if base_rect is None:
                return None
            return base_rect.move(offset_x, offset_y)
        
        self.button_e_rect = shift_rect(self.button_base_rects.get("e"))
        self.button_m_rect = shift_rect(self.button_base_rects.get("m"))
        self.button_h_rect = shift_rect(self.button_base_rects.get("h"))
    
    def _get_prev_selection_rect(self):
        """Return rect of the last completed round selection (if any)."""
        if not self.round_selections:
            return None
        prev_round = max(self.round_selections.keys())
        sel = self.round_selections.get(prev_round)
        if sel:
            return sel.get("rect")
        return None
    
    def _load_rounds_data(self):
        """Load per-level round counts and button goals from RoundsData.csv."""
        rounds_data = {}
        rounds_file = "RoundsData.csv"
        if not os.path.exists(rounds_file):
            print(f"WARNING: RoundsData.csv not found: {rounds_file}")
            return rounds_data
        
        try:
            with open(rounds_file, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f, delimiter=";")
                for row in reader:
                    try:
                        level = int(row.get("Level", 0))
                    except (TypeError, ValueError):
                        continue
                    if level <= 0:
                        continue
                    
                    def _parse_value(key):
                        raw = (row.get(key, "") or "").strip()
                        if raw == "":
                            return None
                        try:
                            value = int(raw)
                            # Treat non-positive numbers as absent so the button stays hidden
                            return value if value > 0 else None
                        except (TypeError, ValueError):
                            return None
                    
                    rounds_data[level] = {
                        "E": _parse_value("E"),
                        "M": _parse_value("M"),
                        "H": _parse_value("H"),
                        "Rounds": _parse_value("Rounds"),
                        "Bosses": _parse_value("Bosses"),
                    }
        except Exception as e:
            print(f"ERROR loading RoundsData.csv: {e}")
        return rounds_data
    
    def _load_reward_card(self, card_number):
        """Load and cache a reward card image. For cards 11-18, uses base card and draws CardAction/CardTurns."""
        # Safety net: legacy configs may still reference card 0
        if card_number == 0:
            card_number = 100
        if card_number in self.reward_card_images:
            return self.reward_card_images[card_number]
        
        # Target size for PopUp - use same aspect ratio as market cards (99x171)
        # Market card ratio: 99/171 ≈ 0.579
        target_width = 100
        # Calculate height to maintain same aspect ratio as market cards
        market_card_ratio = 99 / 171.0  # Use market card aspect ratio
        target_height = int(target_width / market_card_ratio)
        
        # Check if this card uses a base card (cards 11-18)
        base_card_id = self.card_base_mapping.get(card_number, card_number)
        card_path = os.path.join("Cards", f"Card_{base_card_id}.png")
        
        if not os.path.exists(card_path):
            print(f"WARNING: Reward card base not found: {card_path}")
            self.reward_card_images[card_number] = None
            return None
        
        # Load base card image
        card_image = pygame.image.load(card_path).convert_alpha()
        
        # First scale to final PopUp size
        card_surface = pygame.transform.smoothscale(card_image, (target_width, target_height)).convert_alpha()
        
        # If this card has CardAction or CardTurns, draw them on the scaled card
        if card_number in self.card_actions or card_number in self.card_turns:
            # Draw CardAction if this card has one
            if card_number in self.card_actions:
                action_value = self.card_actions[card_number]
                self._draw_card_action_on_surface(card_surface, action_value, card_number, target_width, target_height)
            
            # Draw CardTurns if this card has one
            if card_number in self.card_turns:
                turns_value = self.card_turns[card_number]
                self._draw_card_turns_on_surface(card_surface, turns_value, card_number, target_width, target_height)
            
            self.reward_card_images[card_number] = card_surface
            return card_surface
        else:
            # Regular card, already scaled
            self.reward_card_images[card_number] = card_surface
            return card_surface
    
    def _draw_card_action_on_surface(self, surface, action_value, card_id, card_width, card_height):
        """Draw CardAction value on a card surface"""
        # Calculate font size based on card size (scaled from GameplayPage logic)
        base_market_width = 99
        scale_factor = card_width / base_market_width
        base_font_size = 36
        scaled_font_size = int(base_font_size * 0.85 * 0.9 * scale_factor)
        if scaled_font_size < 1:
            scaled_font_size = 1
        
        # Load font (prefer Gadugib)
        gadugib_path = "Gadugib.ttf"
        if os.path.exists(gadugib_path):
            font_path_use = gadugib_path
        else:
            font_path_use = self.font_path
        
        try:
            font = pygame.font.Font(font_path_use, scaled_font_size)
            action_text = font.render(str(action_value), True, PAPER_COLOR)
            
            # Position near + sign (upper right area)
            plus_x = card_width - 25 * scale_factor
            plus_y = 10 * scale_factor
            action_x = plus_x - 29 * scale_factor
            action_y = plus_y + 14 * scale_factor
            
            # For cards 15 and 16, shift left for minus sign
            if card_id in (15, 16):
                action_x -= 11 * scale_factor
            
            surface.blit(action_text, (int(action_x), int(action_y)))
        except Exception as e:
            print(f"ERROR drawing CardAction on reward card: {e}")
    
    def _draw_card_turns_on_surface(self, surface, turns_value, card_id, card_width, card_height):
        """Draw CardTurns value on a card surface"""
        # Calculate font size (20% smaller than CardAction)
        base_market_width = 99
        scale_factor = card_width / base_market_width
        base_font_size = 36
        card_action_font_size = int(base_font_size * 0.85 * 0.9 * scale_factor)
        turns_font_size = int(card_action_font_size * 0.648)
        if turns_font_size < 1:
            turns_font_size = 1
        
        # Load font (prefer Gadugib)
        gadugib_path = "Gadugib.ttf"
        if os.path.exists(gadugib_path):
            font_path_use = gadugib_path
        else:
            font_path_use = self.font_path
        
        try:
            font = pygame.font.Font(font_path_use, turns_font_size)
            turns_text = font.render(str(turns_value), True, PAPER_COLOR)
            
            # Position at bottom center
            base_bottom_height = 244.0
            height_scale = card_height / base_bottom_height if base_bottom_height > 0 else 1.0
            offset_from_bottom = 75.0 * height_scale
            
            card_center_x = card_width / 2
            turns_x = card_center_x + 10 * scale_factor
            turns_y = card_height - offset_from_bottom
            
            # Adjust for cards 17-18 - use market card sizes as base (same as GameplayPage uses card_size)
            if card_id in (17, 18):
                # For PopUp cards, use market card sizes (99x171) as base, not bottom card sizes
                base_market_width = 99.0
                base_market_height = 171.0
                x_scale = card_width / base_market_width if card_width else 1.0
                y_scale = card_height / base_market_height if card_height else 1.0
                turns_x -= 7.0 * x_scale
                turns_y += 2.0 * y_scale
            
            surface.blit(turns_text, (int(turns_x), int(turns_y)))
        except Exception as e:
            print(f"ERROR drawing CardTurns on reward card: {e}")
    
    def _load_boss_icon_if_needed(self):
        """Load boss icon if all required rounds are completed"""
        # Ensure button rects reflect the latest round offset before positioning boss
        self._refresh_button_rects()
        level_rounds = self.rounds_required
        if level_rounds <= 0:
            return
        
        # Check if all rounds are completed
        completed_count = len(self.completed_rounds)
        
        # If all rounds completed, load boss icon
        if completed_count >= level_rounds:
            # Determine which boss icon to load based on level and boss
            boss_filename = None
            # Prefer explicit filename from caller (supports additional bosses)
            if self.boss_filename:
                boss_filename = self.boss_filename
            else:
                if self.level_number == 1 and self.boss_index == 0:
                    boss_filename = "1_Watt.png"
                elif self.level_number == 2 and self.boss_index == 0:
                    boss_filename = "2_AdamSmith.png"
                elif self.level_number == 2 and self.boss_index == 1:
                    boss_filename = "3_RobertFulton.png"
            
            if boss_filename:
                boss_path = os.path.join("Bosses", boss_filename)
                if os.path.exists(boss_path):
                    boss_image = pygame.image.load(boss_path).convert_alpha()
                    # Scale to 100x100 (same as on BossPage)
                    self.boss_icon = pygame.transform.smoothscale(boss_image, (100, 100)).convert_alpha()
                    
                    # Position boss relative to last selected round icon: +200 X, -70 Y
                    anchor_rect = self._get_prev_selection_rect() or self.button_e_rect or self.button_m_rect or self.button_h_rect
                    if anchor_rect:
                        boss_x = anchor_rect.centerx + 200
                        boss_y = anchor_rect.centery - 70
                        self.boss_icon_rect = pygame.Rect(boss_x - 50, boss_y - 50, 100, 100)
                    
                    # Load animation frames from boss folder
                    base_name = os.path.splitext(boss_filename)[0]  # "1_Watt" or "2_AdamSmith"
                    boss_folder = os.path.join("Bosses", base_name)
                    animation_frames = []
                    if os.path.exists(boss_folder) and os.path.isdir(boss_folder):
                        # Load frames 0-6
                        for frame_num in range(7):
                            frame_filename = f"{base_name}{frame_num}.png"
                            frame_path = os.path.join(boss_folder, frame_filename)
                            if os.path.exists(frame_path):
                                frame_image = pygame.image.load(frame_path).convert_alpha()
                                frame_image = pygame.transform.smoothscale(frame_image, (100, 100)).convert_alpha()
                                animation_frames.append(frame_image)
                            else:
                                print(f"WARNING: Animation frame not found: {frame_path}")
                    else:
                        print(f"WARNING: Boss animation folder not found: {boss_folder}")
                    
                    self.boss_animation_frames = animation_frames
    
    def mark_round_completed(self, round_num):
        """Mark a round as completed"""
        if round_num is None:
            round_num = self.get_current_active_round()
        if round_num is not None and round_num <= self.rounds_required:
            self.completed_rounds.add(round_num)
        # Reload boss icon if needed
        self._load_boss_icon_if_needed()
    
    def is_round_active(self, round_num):
        """Check if a round is active (not completed yet)"""
        if round_num > self.rounds_required:
            return False
        return round_num not in self.completed_rounds
    
    def get_current_active_round(self):
        """Get the current active round number (first uncompleted round)"""
        for round_num in range(1, self.rounds_required + 1):
            if self.is_round_active(round_num):
                return round_num
        return None  # All rounds completed, boss is active
    
    def handle_input(self):
        # Update button positions for the current active round
        self._refresh_button_rects()
        # Update button goals for level 2 based on current round
        self._refresh_button_goals()
        mouse_pos = pygame.mouse.get_pos()
        
        # Get current active round
        current_active_round = self.get_current_active_round()
        all_rounds_completed = (current_active_round is None)
        
        # Check which button is hovered (using original rect for hover detection)
        self.hovered_button = None
        hovered_boss = False
        can_play_round = current_active_round is not None
        
        # Only check buttons if they are active (not completed)
        if can_play_round and self.button_e_rect and self.button_goals.get("e") is not None and self.button_e_rect.collidepoint(mouse_pos):
                self.hovered_button = "e"
        elif can_play_round and self.button_m_rect and self.button_goals.get("m") is not None and self.button_m_rect.collidepoint(mouse_pos):
                self.hovered_button = "m"
        elif can_play_round and self.button_h_rect and self.button_goals.get("h") is not None and self.button_h_rect.collidepoint(mouse_pos):
                self.hovered_button = "h"
        elif self.boss_icon_rect and self.boss_icon_rect.collidepoint(mouse_pos):
            if all_rounds_completed:  # Boss is only active when all rounds are completed
                hovered_boss = True
        
        # Update PopUp position and line based on hover
        if hovered_boss:
            # Boss is hovered
            base_button_rect = self.button_e_rect or self.button_m_rect or self.button_h_rect
            prev_rect = self._get_prev_selection_rect()
            line_start_rect = prev_rect or base_button_rect
            if self.boss_icon_rect and line_start_rect:
                # Set target position for PopUp (same as for buttons)
                self.popup_target_y = float(self.boss_icon_rect.y - 250)
                self.popup_x = self.boss_icon_rect.x + 100
                self.popup_button = "boss"  # Mark as boss hover
                
                # Calculate line coordinates from button E center to boss center
                line_start_x = line_start_rect.centerx
                line_start_y = line_start_rect.centery
                line_end_x = self.boss_icon_rect.centerx
                line_end_y = self.boss_icon_rect.centery
                self.boss_current_line = (line_start_x, line_start_y, line_end_x, line_end_y)
                
                # Start animation if not already started
                if self.boss_hover_state is None:
                    self.boss_hover_state = {
                        'sequence_index': 0,
                        'last_frame_time': pygame.time.get_ticks()
                    }
                    
                    # Play sound when starting to hover boss
                    if self.pen_sound:
                        self.pen_sound.play()
        elif self.hovered_button is not None:
            # Determine which button rect to use
            button_rect = None
            if self.hovered_button == "e" and self.button_e_rect:
                button_rect = self.button_e_rect
            elif self.hovered_button == "m" and self.button_m_rect:
                button_rect = self.button_m_rect
            elif self.hovered_button == "h" and self.button_h_rect:
                button_rect = self.button_h_rect
            
            if button_rect:
                # Set target position for PopUp
                self.popup_target_y = float(button_rect.y - 250)
                self.popup_x = button_rect.x + 100
                self.popup_button = self.hovered_button  # Save button for text display
                
                # Calculate line coordinates
                # Start from previous round selection if exists; otherwise default start
                prev_rect = self._get_prev_selection_rect()
                if prev_rect:
                    line_start_x = prev_rect.centerx
                    line_start_y = prev_rect.centery
                else:
                    line_start_x = 235
                    line_start_y = SCREEN_HEIGHT - 218
                # End: button center coordinates
                line_end_x = button_rect.centerx
                line_end_y = button_rect.centery
                self.current_line = (line_start_x, line_start_y, line_end_x, line_end_y)
                
                # Play sound only once when starting to hover
                if self.last_hovered_button != self.hovered_button:
                    if self.pen_sound:
                        self.pen_sound.play()
                    self.last_hovered_button = self.hovered_button
        else:
            # Move PopUp back above screen when not hovering
            self.popup_target_y = -400.0
            # Don't clear popup_button here - let it persist until PopUp is hidden
            self.current_line = None  # Clear line when not hovering button
            self.boss_current_line = None  # Clear line when not hovering boss
            self.last_hovered_button = None
            # Stop boss animation when not hovered
            if self.boss_hover_state is not None:
                self.boss_hover_state = None
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"
            
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return "back"
            
            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # Left click
                    # Only allow clicks on active buttons
                    if can_play_round and self.button_e_rect and self.button_e_rect.collidepoint(mouse_pos) and self.button_goals.get("e") is not None:
                        print("LevelButtonE (bottom) clicked")
                        # Save line coordinates when clicking
                        if self.current_line:
                            self.saved_lines.append(self.current_line)
                        # Set goal for this round
                        if self.test_mode:
                            self.Goal = 2  # Always 2 in test mode
                        else:
                            goal_value = self.button_goals.get("e")
                            if goal_value is not None:
                                self.Goal = goal_value
                        self.last_selected_round = current_active_round  # Track selected round
                        # Remember selection rect for history (preserve past icons)
                        self.round_selections[current_active_round] = {
                            "key": "e",
                            "rect": self.button_e_rect.copy() if self.button_e_rect else None
                        }
                        return "button_e"
                    if can_play_round and self.button_m_rect and self.button_m_rect.collidepoint(mouse_pos) and self.button_goals.get("m") is not None:
                        print("LevelButtonM (middle) clicked")
                        # Save line coordinates when clicking
                        if self.current_line:
                            self.saved_lines.append(self.current_line)
                        # Set goal for this round
                        if self.test_mode:
                            self.Goal = 2  # Always 2 in test mode
                        else:
                            goal_value = self.button_goals.get("m")
                            if goal_value is not None:
                                self.Goal = goal_value
                        self.last_selected_round = current_active_round  # Track selected round
                        # Remember selection rect for history (preserve past icons)
                        self.round_selections[current_active_round] = {
                            "key": "m",
                            "rect": self.button_m_rect.copy() if self.button_m_rect else None
                        }
                        return "button_m"
                    if can_play_round and self.button_h_rect and self.button_h_rect.collidepoint(mouse_pos) and self.button_goals.get("h") is not None:
                        print("LevelButtonH (upper) clicked")
                        # Save line coordinates when clicking
                        if self.current_line:
                            self.saved_lines.append(self.current_line)
                        # Set goal for this round
                        if self.test_mode:
                            self.Goal = 2  # Always 2 in test mode
                        else:
                            goal_value = self.button_goals.get("h")
                            if goal_value is not None:
                                self.Goal = goal_value
                        self.last_selected_round = current_active_round  # Track selected round
                        # Remember selection rect for history (preserve past icons)
                        self.round_selections[current_active_round] = {
                            "key": "h",
                            "rect": self.button_h_rect.copy() if self.button_h_rect else None
                        }
                        return "button_h"
                    # Handle boss click (only if all rounds completed)
                    current_active_round = self.get_current_active_round()
                    all_rounds_completed = (current_active_round is None)
                    if self.boss_icon_rect and self.boss_icon_rect.collidepoint(mouse_pos) and all_rounds_completed:
                        print("Boss clicked")
                        # Set goal for boss
                        if self.test_mode:
                            self.Goal = 2  # Always 2 in test mode
                        else:
                            if self.level_number == 2:
                                # Get boss goal from GoalsLevel2.csv
                                e_boss_goal = get_level2_goal(None, "e", self.boss_selection, True)
                                m_boss_goal = get_level2_goal(None, "m", self.boss_selection, True)
                                # Use E goal for boss (or M if E is not available)
                                boss_goal = e_boss_goal if e_boss_goal is not None else m_boss_goal
                                self.Goal = boss_goal if boss_goal is not None else 70
                            else:
                                boss_key = (self.level_number, self.boss_index)
                                if boss_key in self.boss_goals:
                                    self.Goal = self.boss_goals[boss_key]
                                else:
                                    self.Goal = 70  # Default fallback
                        return "boss_clicked"
        
        return None
    
    def draw(self):
        # Background
        if self.background:
            self.screen.blit(self.background, (0, 0))
        else:
            self.screen.fill(BLACK)
        
        # Draw Koordinates.png overlay (above background, below other objects)
        if self.koordinates:
            self.screen.blit(self.koordinates, (0, 0))
        
        # Update button positions for the current active round (draw loop)
        self._refresh_button_rects()
        # Update button goals for level 2 based on current round
        self._refresh_button_goals()
        
        # Draw previously selected round icons (kept at their historical positions)
        if self.round_selections:
            for round_num in sorted(self.round_selections.keys()):
                sel = self.round_selections[round_num]
                key = sel.get("key")
                rect = sel.get("rect")
                if not rect:
                    continue
                img = None
                if key == "e":
                    img = self.button_e
                elif key == "m":
                    img = self.button_m
                elif key == "h":
                    img = self.button_h
                if img:
                    self.screen.blit(img, rect.topleft)
        
        # Update PopUp position with dt-based smooth animation (stable across FPS)
        now = pygame.time.get_ticks()
        dt = (now - getattr(self, "_popup_last_tick", now)) / 1000.0
        self._popup_last_tick = now
        dt = _clamp_dt_seconds(dt)
        max_delta = float(getattr(self, "popup_speed_pps", 0.0)) * dt
        self.popup_y = move_towards(float(self.popup_y), float(self.popup_target_y), max_delta)
        
        # Determine if rounds are completed to hide current buttons when boss is active
        current_active_round = self.get_current_active_round()
        all_rounds_completed = (current_active_round is None)
        
        # Draw saved lines (from previous selected rounds) under icons
        for line in self.saved_lines:
            if line:
                start_x, start_y, end_x, end_y = line
            pygame.draw.line(self.screen, self.line_color, (start_x, start_y), (end_x, end_y), self.line_width)
        
        # Draw current line (when hovering over button) - UNDER the buttons
        if self.current_line:
            start_x, start_y, end_x, end_y = self.current_line
            pygame.draw.line(self.screen, self.line_color, (start_x, start_y), (end_x, end_y), self.line_width)
        
        # Draw boss line (when hovering over boss) - UNDER the buttons and boss
        if self.boss_current_line:
            start_x, start_y, end_x, end_y = self.boss_current_line
            pygame.draw.line(self.screen, self.line_color, (start_x, start_y), (end_x, end_y), self.line_width)
        
        # Draw previously selected round icons (kept at their historical positions) above lines
        if self.round_selections:
            for round_num in sorted(self.round_selections.keys()):
                sel = self.round_selections[round_num]
                key = sel.get("key")
                rect = sel.get("rect")
                if not rect:
                    continue
                img = None
                if key == "e":
                    img = self.button_e
                elif key == "m":
                    img = self.button_m
                elif key == "h":
                    img = self.button_h
                if img:
                    self.screen.blit(img, rect.topleft)
        
        # Draw buttons (from bottom to top: E, M, H) only if rounds remain
        if not all_rounds_completed:
            if self.button_e and self.button_e_rect:
                self.screen.blit(self.button_e, self.button_e_rect.topleft)
            
            if self.button_m and self.button_m_rect:
                self.screen.blit(self.button_m, self.button_m_rect.topleft)
            
            if self.button_h and self.button_h_rect:
                self.screen.blit(self.button_h, self.button_h_rect.topleft)
        
        # Draw boss icon if all rounds are completed (with animation if hovered)
        if self.boss_icon and self.boss_icon_rect:
            # Update boss animation if hovered
            if self.boss_hover_state is not None and len(self.boss_animation_frames) > 0:
                current_time = pygame.time.get_ticks()
                hover_state = self.boss_hover_state
                time_since_last_frame = current_time - hover_state['last_frame_time']
                
                if time_since_last_frame >= self.animation_frame_duration:
                    # Move to next frame in sequence
                    hover_state['sequence_index'] = (hover_state['sequence_index'] + 1) % len(self.animation_sequence)
                    hover_state['last_frame_time'] = current_time
                
                # Get current frame number from sequence
                frame_index = self.animation_sequence[hover_state['sequence_index']]
                
                # Draw animated frame if available
                if frame_index < len(self.boss_animation_frames):
                    self.screen.blit(self.boss_animation_frames[frame_index], self.boss_icon_rect.topleft)
                else:
                    # Fallback to default image if frame not available
                    self.screen.blit(self.boss_icon, self.boss_icon_rect.topleft)
            else:
                # Draw default boss image when not hovered
                self.screen.blit(self.boss_icon, self.boss_icon_rect.topleft)
        
        # Draw PopUp if it's visible (not completely above screen)
        if self.popup_image and self.popup_y > -self.popup_image.get_height():
            popup_y_draw = int(round(self.popup_y))
            self.screen.blit(self.popup_image, (self.popup_x, popup_y_draw))
            
            # Draw text on PopUp if a button or boss is hovered
            if self.popup_button is not None:
                if self.popup_button == "boss":
                    # Boss is hovered - show boss text instead of goal
                    if self.boss_text:
                        # Show boss text (e.g., Boss2Text)
                        full_text = self.boss_text
                    else:
                        # Fallback: show goal if boss text is not available
                        if self.level_number == 2:
                            # Get boss goal from GoalsLevel2.csv
                            e_boss_goal = get_level2_goal(None, "e", self.boss_selection, True)
                            m_boss_goal = get_level2_goal(None, "m", self.boss_selection, True)
                            goal_value = e_boss_goal if e_boss_goal is not None else (m_boss_goal if m_boss_goal is not None else 0)
                        else:
                            boss_key = (self.level_number, self.boss_index)
                            goal_value = self.boss_goals.get(boss_key, 0)
                        # Build text: PopUpRound text + goal + "$"
                        full_text = f"{self.popup_round_text} {goal_value}$"
                else:
                    # Button is hovered
                    # Get goal value - for level 2, use current round; for others use button_goals
                    if self.level_number == 2:
                        current_round = self.get_current_active_round()
                        if current_round is not None:
                            goal_value = get_level2_goal(current_round, self.popup_button, self.boss_selection, False) or 0
                        else:
                            goal_value = self.button_goals.get(self.popup_button, 0) or 0
                    else:
                        goal_value = self.button_goals.get(self.popup_button, 0) or 0
                    
                    # Build text: PopUpRound text + goal + "$"
                    full_text = f"{self.popup_round_text} {goal_value}$"
                
                # Split text into multiple lines to fit in PopUp
                popup_text_width = self.popup_width - 60  # Leave more padding (30px on each side) to prevent text overflow
                lines = wrap_text(full_text, self.popup_font, popup_text_width)
                
                # Draw text lines on PopUp on Round Page
                text_start_x = self.popup_x + 30  # Left padding + 30px right
                text_start_y = popup_y_draw + 115  # Top padding + 5px down
                line_height = self.popup_font.get_height() + 5  # 5px spacing between lines
                
                for i, line in enumerate(lines):
                    text_surface = self.popup_font.render(line, True, PAPER_COLOR)
                    self.screen.blit(text_surface, (text_start_x, text_start_y + i * line_height))
                
                # Draw reward text below goal text (only for buttons E and M, not for boss)
                if self.popup_button != "boss" and self.popup_button in ["e", "m"]:
                    # Determine round number - use current active round
                    round_num = self.get_current_active_round()
                    if round_num is None:
                        # Fallback: for level 2 use rounds_required, for others use button-based logic
                        if self.level_number == 2:
                            round_num = self.rounds_required if hasattr(self, 'rounds_required') else 1
                        else:
                            round_num = 1 if self.popup_button == "e" else 2
                    reward_key = (self.level_number, round_num, self.popup_button.upper())
                    reward_data = self.rewards.get(reward_key)
                    
                    reward_text_y = text_start_y + len(lines) * line_height
                    reward_text_surface = self.popup_font.render(self.popup_reward_text, True, PAPER_COLOR)
                    self.screen.blit(reward_text_surface, (text_start_x, reward_text_y))
                    
                    # Draw additional text from Rewards.csv Text column if present
                    if reward_data:
                        additional_text = reward_data.get('text')
                        if additional_text:
                            additional_text_key = additional_text.strip()
                            additional_text_value = get_text(additional_text_key, additional_text_key)
                            # Wrap additional text to fit in PopUp width
                            additional_text_lines = wrap_text(additional_text_value, self.popup_font, popup_text_width)
                            reward_text_y += line_height
                            for i, line in enumerate(additional_text_lines):
                                additional_text_surface = self.popup_font.render(line, True, PAPER_COLOR)
                                self.screen.blit(additional_text_surface, (text_start_x, reward_text_y + i * line_height))
                
                # Draw reward card below reward text for buttons E and M (not for boss)
                if self.popup_button != "boss" and self.popup_button in ["e", "m"]:
                    # Determine round number - use current active round
                    round_num = self.get_current_active_round()
                    if round_num is None:
                        # Fallback: for level 2 use rounds_required, for others use button-based logic
                        if self.level_number == 2:
                            round_num = self.rounds_required if hasattr(self, 'rounds_required') else 1
                        else:
                            round_num = 1 if self.popup_button == "e" else 2
                    reward_key = (self.level_number, round_num, self.popup_button.upper())
                    reward_data = self.rewards.get(reward_key)
                    
                    if reward_data:
                        reward1_list = reward_data.get('reward1', [])
                        reward2 = reward_data.get('reward2')  # Can be list or None
                        
                        # Check if Reward2 is a list (multiple cards)
                        reward2_list = reward2 if isinstance(reward2, list) else ([reward2] if reward2 is not None else [])
                        
                        if reward1_list:
                            # Check if Reward1 has multiple cards (random reward) and any card is in range 10-19
                            has_random_reward1 = len(reward1_list) > 1 and any(10 <= card <= 19 for card in reward1_list)
                            # Check if Reward2 has multiple cards (random reward) and any card is in range 10-19
                            has_random_reward2 = len(reward2_list) > 1 and any(10 <= card <= 19 for card in reward2_list)
                            
                            # Calculate position: below the reward text (accounting for additional text if present)
                            reward_text_y = text_start_y + len(lines) * line_height
                            # Check if there's additional text and calculate how many lines it takes
                            additional_text_lines_count = 0
                            if reward_data.get('text'):
                                additional_text_key = reward_data.get('text').strip()
                                additional_text_value = get_text(additional_text_key, additional_text_key)
                                additional_text_lines_list = wrap_text(additional_text_value, self.popup_font, popup_text_width)
                                additional_text_lines_count = len(additional_text_lines_list)
                            card_spacing = 5  # Spacing between reward text and card
                            card_y = reward_text_y + line_height + (additional_text_lines_count * line_height) + card_spacing
                            
                            if has_random_reward1 and self.random_drop_image:
                                # Show RandomDropGain.png for Reward1
                                card_width = int(self.random_drop_image.get_width() * 0.75)
                                card_height = int(self.random_drop_image.get_height() * 0.75)
                                scaled_random1 = pygame.transform.smoothscale(self.random_drop_image, (card_width, card_height)).convert_alpha()
                                
                                # Build optional Reward2 surface (random icon OR actual card),
                                # so E can show 2 rewards even when Reward2 is a single card.
                                reward2_surface = None
                                reward2_width = 0
                                reward2_height = 0
                                if reward2 is not None:
                                    if has_random_reward2 and self.random_drop_image:
                                        reward2_surface = pygame.transform.smoothscale(self.random_drop_image, (card_width, card_height)).convert_alpha()
                                        reward2_width, reward2_height = card_width, card_height
                                    else:
                                        reward2_card = reward2_list[0] if reward2_list else None
                                        if reward2_card is not None:
                                            reward2_image = self._load_reward_card(reward2_card)
                                            if reward2_image:
                                                reward2_width = int(reward2_image.get_width() * 0.75)
                                                reward2_height = int(reward2_image.get_height() * 0.75)
                                                reward2_surface = pygame.transform.smoothscale(
                                                    reward2_image, (reward2_width, reward2_height)
                                                ).convert_alpha()
                                
                                # Calculate total width for cards with spacing
                                card_spacing_between = 10  # Spacing between cards
                                total_cards_width = card_width
                                if reward2_surface is not None:
                                    total_cards_width += card_spacing_between + reward2_width
                                
                                # Center both cards together
                                cards_start_x = self.popup_x + (self.popup_width - total_cards_width) // 2
                                
                                # Draw RandomDropGain.png first (on the left) - Reward1
                                self.screen.blit(scaled_random1, (cards_start_x, card_y))
                                cards_start_x += card_width + card_spacing_between
                                
                                # Draw Reward2 (on the right) if present
                                if reward2_surface is not None:
                                    self.screen.blit(reward2_surface, (cards_start_x, card_y))
                            else:
                                # Show first card from Reward1 (or single card) with Reward2 side by side if present
                                first_card = reward1_list[0] if reward1_list else None
                                if first_card:
                                    reward_card_image = self._load_reward_card(first_card)
                                    if reward_card_image:
                                        # Reduce card size by 25% to fit better (changed from 0.9 to 0.75)
                                        card_width = int(reward_card_image.get_width() * 0.75)
                                        card_height = int(reward_card_image.get_height() * 0.75)
                                        scaled_card = pygame.transform.smoothscale(reward_card_image, (card_width, card_height)).convert_alpha()
                                        
                                        # Calculate total width for both cards with spacing
                                        card_spacing_between = 10  # Spacing between cards
                                        total_cards_width = card_width
                                        if reward2 is not None:
                                            # Get card number from list if reward2 is a list, otherwise use reward2 directly
                                            reward2_card = reward2[0] if isinstance(reward2, list) and len(reward2) > 0 else reward2
                                            reward2_image = self._load_reward_card(reward2_card)
                                            if reward2_image:
                                                reward2_width = int(reward2_image.get_width() * 0.75)
                                                total_cards_width += card_spacing_between + reward2_width
                                        
                                        # Center both cards together
                                        cards_start_x = self.popup_x + (self.popup_width - total_cards_width) // 2
                                        
                                        # Draw Reward1 card first (on the left)
                                        self.screen.blit(scaled_card, (cards_start_x, card_y))
                                        cards_start_x += card_width + card_spacing_between
                                        
                                        # Draw Reward2 card next (on the right) if present
                                        # Check if Reward2 is a list or single card
                                        if reward2 is not None:
                                            # If Reward2 is a list, show first card or RandomDropGain if multiple
                                            if isinstance(reward2, list) and len(reward2) > 0:
                                                has_random_reward2 = len(reward2) > 1 and any(10 <= card <= 19 for card in reward2)
                                                if has_random_reward2 and self.random_drop_image:
                                                    reward2_width = int(self.random_drop_image.get_width() * 0.75)
                                                    reward2_height = int(self.random_drop_image.get_height() * 0.75)
                                                    scaled_reward2 = pygame.transform.smoothscale(self.random_drop_image, (reward2_width, reward2_height)).convert_alpha()
                                                    reward2_x = cards_start_x
                                                    reward2_y = card_y
                                                    self.screen.blit(scaled_reward2, (reward2_x, reward2_y))
                                                else:
                                                    reward2_card = reward2[0]
                                                    reward2_image = self._load_reward_card(reward2_card)
                                                    if reward2_image:
                                                        reward2_width = int(reward2_image.get_width() * 0.75)
                                                        reward2_height = int(reward2_image.get_height() * 0.75)
                                                        scaled_reward2 = pygame.transform.smoothscale(reward2_image, (reward2_width, reward2_height)).convert_alpha()
                                                        reward2_x = cards_start_x
                                                        reward2_y = card_y
                                                        self.screen.blit(scaled_reward2, (reward2_x, reward2_y))
                                            else:
                                                # Single card
                                                reward2_image = self._load_reward_card(reward2)
                                                if reward2_image:
                                                    reward2_width = int(reward2_image.get_width() * 0.75)
                                                    reward2_height = int(reward2_image.get_height() * 0.75)
                                                    scaled_reward2 = pygame.transform.smoothscale(reward2_image, (reward2_width, reward2_height)).convert_alpha()
                                                    reward2_x = cards_start_x
                                                    reward2_y = card_y
                                                    self.screen.blit(scaled_reward2, (reward2_x, reward2_y))
        else:
            # PopUp is completely hidden, clear the button for text
            if self.popup_button is not None:
                self.popup_button = None
        
        pygame.display.flip()
    
    def run(self):
        # Reset popup position when returning to round page
        self.popup_y = -400.0
        self.popup_target_y = -400.0
        self.popup_button = None
        self._popup_last_tick = pygame.time.get_ticks()
        
        while True:
            result = self.handle_input()
            
            if result == "quit":
                pygame.quit()
                sys.exit()
            
            if result == "back":
                return "back"
            
            if result in ("button_e", "button_m", "button_h"):
                # Button clicked, navigate to gameplay page
                return result
            
            if result == "boss_clicked":
                # Boss clicked, navigate to gameplay page with boss goal
                return "boss_clicked"
            
            self.draw()
            self.clock.tick(FPS)


def load_background():
    """Load background image"""
    bg_path = os.path.join("UI", "Background.png")
    if os.path.exists(bg_path):
        background = pygame.image.load(bg_path).convert()
        background = pygame.transform.smoothscale(background, (SCREEN_WIDTH, SCREEN_HEIGHT)).convert()
        return background
    else:
        print("WARNING: Background not found:", bg_path)
        return None


def load_font():
    """Load font from project folder"""
    font_paths = [
        "egyptiennemncyr_condensedbold.ttf",
        "Egyptienne MN CYR.ttf",
        "EgyptienneMN-CYR.ttf",
        "egyptiennemn-cyr.ttf",
        os.path.join("UI", "egyptiennemncyr_condensedbold.ttf"),
        os.path.join("UI", "Egyptienne MN CYR.ttf"),
        os.path.join("UI", "EgyptienneMN-CYR.ttf"),
    ]
    
    for path in font_paths:
        if os.path.exists(path):
            return path
    
    print("ERROR: Font file not found in project folder. Tried:", font_paths)
    sys.exit()


if __name__ == "__main__":
    # Initialize screen
    display_flags = pygame.HWSURFACE | pygame.DOUBLEBUF
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), display_flags)
    pygame.display.set_caption("Bressoles")
    
    # Load shared resources
    background = load_background()
    font_path = load_font()
    
    # Load language (default: RU/RUS)
    load_language(CURRENT_LANGUAGE)
    
    # Main game loop
    while True:
        # Start page
        start_page = StartPage(screen, background, font_path, Lang)
        result = start_page.run()
        
        # Track test mode flag
        test_mode = False
        
        if result == "start":
            rounds_config = load_rounds_config()
            # LevelPage loop
            while True:
                level_page = GameScreen(screen, background, font_path, test_mode=False)  # LevelPage
                level_result = level_page.run()
                
                if level_result == "back":
                    break  # Return to start page
                elif level_result and level_result.startswith("level_"):
                    # Level selected, go to BossPage
                    try:
                        level_num = int(level_result.split("_")[1])
                        bosses_required = get_bosses_required(level_num, rounds_config)
                        bp_state = boss_progress.setdefault(level_num, {"defeated": 0, "last_rect": None, "lines": [], "defeated_bosses": []})
                        # If level already completed earlier, reset its boss state for a fresh replay
                        if bp_state["defeated"] >= bosses_required:
                            bp_state.update({"defeated": 0, "last_rect": None, "lines": [], "defeated_bosses": []})
                        # Boss selection loop to support multiple boss rounds
                        while True:
                            boss_page = BossPage(
                                screen,
                                font_path,
                                level_num,
                                defeated_count=bp_state["defeated"],
                                last_defeated_rect=bp_state["last_rect"],
                                saved_lines=bp_state["lines"],
                                defeated_bosses=bp_state["defeated_bosses"],
                            )
                            boss_result = boss_page.run()

                            if boss_result == "back":
                                break  # Return to level page loop
                            elif boss_result == "quit":
                                level_result = "quit"
                                break
                            elif boss_result and boss_result.startswith("boss_"):
                                # Boss selected, go to RoundPage
                                parts = boss_result.split("_")
                                boss_level = int(parts[1])
                                boss_index = int(parts[2])

                                boss_filename = None
                                if hasattr(boss_page, "current_boss_filenames") and boss_index < len(boss_page.current_boss_filenames):
                                    boss_filename = boss_page.current_boss_filenames[boss_index]

                                round_page = RoundPage(
                                    screen,
                                    font_path,
                                    boss_level,
                                    boss_index,
                                    boss_filename=boss_filename,
                                    test_mode=False,
                                )
                                round_result = round_page.run()
                                gameplay_result = None

                                # Round buttons (E/M/H)
                                while round_result in ("button_e", "button_m", "button_h"):
                                    difficulty = round_result.replace("button_", "")
                                    goal = round_page.Goal if getattr(round_page, "Goal", None) is not None else None
                                    round_num = round_page.get_current_active_round()
                                    print(f"Passing goal to GameplayPage: {goal}, round_num: {round_num}")  # Debug

                                    gameplay_page = GameplayPage(
                                        screen,
                                        font_path,
                                        difficulty,
                                        goal=goal,
                                        level_number=boss_level,
                                        boss_index=boss_index,
                                        round_num=round_num,
                                    )
                                    gameplay_result = gameplay_page.run()

                                    if gameplay_result == "back":
                                        round_result = round_page.run()
                                    elif gameplay_result == "round_select":
                                        if round_page.last_selected_round is not None:
                                            round_page.mark_round_completed(round_page.last_selected_round)
                                        round_result = round_page.run()
                                    elif gameplay_result == "level_select":
                                        break
                                    elif gameplay_result == "game_over":
                                        print("Game Over!")
                                        round_result = round_page.run()
                                    else:
                                        round_result = round_page.run()

                                if gameplay_result == "level_select":
                                    break
                                elif round_result == "back":
                                    continue  # back to boss loop
                                elif round_result == "quit":
                                    level_result = "quit"
                                    break
                                elif round_result == "boss_clicked":
                                    goal = round_page.Goal if getattr(round_page, "Goal", None) is not None else None
                                    print(f"Passing boss goal to GameplayPage: {goal}")  # Debug

                                    gameplay_page = GameplayPage(
                                        screen,
                                        font_path,
                                        "e",
                                        goal=goal,
                                        level_number=boss_level,
                                        is_boss_fight=True,
                                        boss_index=boss_index,
                                    )
                                    gameplay_result = gameplay_page.run()

                                    if gameplay_result == "back":
                                        round_result = round_page.run()
                                    elif gameplay_result == "round_select":
                                        bp_state["defeated"] += 1
                                        bp_state["last_rect"] = getattr(boss_page, "clicked_boss_rect", None)
                                        bp_state["lines"] = getattr(boss_page, "saved_lines", [])[:]

                                        clicked_filename = getattr(boss_page, "clicked_boss_filename", None)
                                        clicked_rect = getattr(boss_page, "clicked_boss_rect", None)
                                        if clicked_filename and clicked_rect:
                                            bp_state["defeated_bosses"].append(
                                                {
                                                    "filename": clicked_filename,
                                                    "rect": clicked_rect.copy(),
                                                }
                                            )

                                        if bp_state["defeated"] >= bosses_required:
                                            if boss_level == 1:
                                                level_1_boss_defeated = True
                                                print("Level 1 boss defeated! Unlocking level 2")
                                            level_result = "level_select"
                                            break

                                        # More bosses remain; continue boss loop with updated state
                                        continue
                                    elif gameplay_result == "level_select":
                                        # On defeat always exit to level selection (fresh start)
                                        break
                                    elif gameplay_result == "game_over":
                                        print("Game Over!")
                                        round_result = round_page.run()
                                    else:
                                        round_result = round_page.run()

                                    if round_result == "quit":
                                        level_result = "quit"
                                        break

                                    # Return to boss loop after boss fight flow
                                    continue
                                else:
                                    # Unexpected result from RoundPage - return to boss loop
                                    continue
                            else:
                                # Unexpected result - return to level page
                                break

                        if level_result == "quit":
                            break
                    except Exception as e:
                        print(f"ERROR in navigation: {e}")
                        import traceback
                        traceback.print_exc()
                        continue  # Return to level page on error
        elif result == "test_mode":
            rounds_config = load_rounds_config()
            # Test mode: show all 12 levels and always set Goal=2
            test_mode = True
            # LevelPage loop in test mode
            while True:
                level_page = GameScreen(screen, background, font_path, test_mode=True)  # LevelPage with test mode
                level_result = level_page.run()
                
                if level_result == "back":
                    break  # Return to start page
                elif level_result and level_result.startswith("level_"):
                    # Level selected, go to BossPage
                    try:
                        level_num = int(level_result.split("_")[1])
                        bosses_required = get_bosses_required(level_num, rounds_config)
                        bp_state = boss_progress.setdefault(level_num, {"defeated": 0, "last_rect": None, "lines": [], "defeated_bosses": []})
                        # Reset boss state on replay in test mode too
                        if bp_state["defeated"] >= bosses_required:
                            bp_state.update({"defeated": 0, "last_rect": None, "lines": [], "defeated_bosses": []})
                        # Boss selection loop (test mode) to support multiple boss rounds
                        while True:
                            boss_page = BossPage(
                                screen,
                                font_path,
                                level_num,
                                defeated_count=bp_state["defeated"],
                                last_defeated_rect=bp_state["last_rect"],
                                saved_lines=bp_state["lines"],
                                defeated_bosses=bp_state["defeated_bosses"],
                            )
                            boss_result = boss_page.run()

                            if boss_result == "back":
                                break  # Return to level page loop
                            elif boss_result == "quit":
                                level_result = "quit"
                                break
                            elif boss_result and boss_result.startswith("boss_"):
                                parts = boss_result.split("_")
                                boss_level = int(parts[1])
                                boss_index = int(parts[2])

                                boss_filename = None
                                if hasattr(boss_page, "current_boss_filenames") and boss_index < len(boss_page.current_boss_filenames):
                                    boss_filename = boss_page.current_boss_filenames[boss_index]

                                round_page = RoundPage(
                                    screen,
                                    font_path,
                                    boss_level,
                                    boss_index,
                                    boss_filename=boss_filename,
                                    test_mode=True,
                                )
                                round_result = round_page.run()
                                gameplay_result = None

                                while round_result in ("button_e", "button_m", "button_h"):
                                    difficulty = round_result.replace("button_", "")
                                    goal = round_page.Goal if getattr(round_page, "Goal", None) is not None else 2
                                    round_num = round_page.get_current_active_round()
                                    print(f"Passing goal to GameplayPage (test mode): {goal}, round_num: {round_num}")  # Debug

                                    gameplay_page = GameplayPage(
                                        screen,
                                        font_path,
                                        difficulty,
                                        goal=goal,
                                        level_number=boss_level,
                                        boss_index=boss_index,
                                        round_num=round_num,
                                    )
                                    gameplay_result = gameplay_page.run()

                                    if gameplay_result == "back":
                                        round_result = round_page.run()
                                    elif gameplay_result == "round_select":
                                        if round_page.last_selected_round is not None:
                                            round_page.mark_round_completed(round_page.last_selected_round)
                                        round_result = round_page.run()
                                    elif gameplay_result == "level_select":
                                        break
                                    elif gameplay_result == "game_over":
                                        print("Game Over!")
                                        round_result = round_page.run()
                                    else:
                                        round_result = round_page.run()

                                if gameplay_result == "level_select":
                                    break
                                elif round_result == "back":
                                    continue
                                elif round_result == "quit":
                                    level_result = "quit"
                                    break
                                elif round_result == "boss_clicked":
                                    goal = 2  # Always 2 in test mode for boss
                                    print(f"Passing boss goal to GameplayPage (test mode): {goal}")  # Debug

                                    gameplay_page = GameplayPage(
                                        screen,
                                        font_path,
                                        "e",
                                        goal=goal,
                                        level_number=boss_level,
                                        is_boss_fight=True,
                                        boss_index=boss_index,
                                    )
                                    gameplay_result = gameplay_page.run()

                                    if gameplay_result == "back":
                                        round_result = round_page.run()
                                    elif gameplay_result == "round_select":
                                        bp_state["defeated"] += 1
                                        bp_state["last_rect"] = getattr(boss_page, "clicked_boss_rect", None)
                                        bp_state["lines"] = getattr(boss_page, "saved_lines", [])[:]

                                        clicked_filename = getattr(boss_page, "clicked_boss_filename", None)
                                        clicked_rect = getattr(boss_page, "clicked_boss_rect", None)
                                        if clicked_filename and clicked_rect:
                                            bp_state["defeated_bosses"].append(
                                                {
                                                    "filename": clicked_filename,
                                                    "rect": clicked_rect.copy(),
                                                }
                                            )

                                        if bp_state["defeated"] >= bosses_required:
                                            level_result = "level_select"
                                            break

                                        continue
                                    elif gameplay_result == "level_select":
                                        # On defeat always exit to level selection (fresh start)
                                        break
                                    elif gameplay_result == "game_over":
                                        print("Game Over!")
                                        round_result = round_page.run()
                                    else:
                                        round_result = round_page.run()

                                    if round_result == "quit":
                                        level_result = "quit"
                                        break

                                    continue
                                else:
                                    continue
                            else:
                                break

                        if level_result == "quit":
                            break
                    except Exception as e:
                        print(f"ERROR in navigation: {e}")
                        import traceback
                        traceback.print_exc()
                        continue  # Return to level page on error
        elif result == "quit":
            break
    
    pygame.quit()
    sys.exit()