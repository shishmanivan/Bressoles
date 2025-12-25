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

# Language system
Lang = {}  # Dictionary to store language strings
CURRENT_LANGUAGE = "RU"  # Default language (RUS in user's terms, but file uses RU)


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
            self.background = pygame.transform.scale(self.background, (SCREEN_WIDTH, SCREEN_HEIGHT)).convert()
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
            self.lang.get("MenuQuit", "Quit")
        ]
        self.selected_index = 0
        
        # Menu positions - adjusted for right side empty slots (centered in slots)
        # These positions are set to align with empty menu slots on the right side of StartPage.jpg
        # Shifted 150 pixels left (70 + 80) to align with decorative elements on dividing lines
        self.menu_positions = [
            (SCREEN_WIDTH - 400, 350),  # Start Game
            (SCREEN_WIDTH - 400, 450),  # Options
            (SCREEN_WIDTH - 400, 550),  # Quit
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

            self.draw()
            self.clock.tick(FPS)


class GameScreen:
    def __init__(self, screen, background, font_path):
        self.screen = screen
        self.clock = pygame.time.Clock()
        
        # Load Back3.png from UI folder
        back3_path = os.path.join("UI", "Back3.png")
        if os.path.exists(back3_path):
            self.background = pygame.image.load(back3_path).convert()
            self.background = pygame.transform.scale(self.background, (SCREEN_WIDTH, SCREEN_HEIGHT)).convert()
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
            self.levelcard_image = pygame.transform.scale(original_image, (new_width, new_height)).convert_alpha()
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
            self.startarrow_image = pygame.transform.scale(original_arrow, (new_width, new_height)).convert_alpha()
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
    
    def handle_input(self):
        mouse_pos = pygame.mouse.get_pos()
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"
            
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return "back"
            
            # Handle StartArrow click
            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # Left click
                    if self.arrow_rect and self.arrow_rect.collidepoint(mouse_pos):
                        # Navigate to boss page for level 1
                        return "level_1"
        
        return None
    
    def draw(self):
        # Background
        if self.background:
            self.screen.blit(self.background, (0, 0))
        else:
            self.screen.fill(BLACK)
        
        # Draw single level card in top left corner
        if self.levelcard_image:
            self.screen.blit(self.levelcard_image, self.card_position)
            
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
            words = desc_text.split()
            lines = []
            current_line = []
            current_width = 0
            
            for word in words:
                word_surface = self.font_card_desc.render(word + " ", True, PAPER_COLOR)
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
    def __init__(self, screen, font_path, difficulty="e"):
        self.screen = screen
        self.clock = pygame.time.Clock()
        self.difficulty = difficulty  # "e", "m", or "h"
        
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
            self.background = pygame.transform.scale(bg_image, (SCREEN_WIDTH, SCREEN_HEIGHT)).convert()
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
            self.frame = pygame.transform.scale(frame_original, (frame_width, frame_height)).convert_alpha()
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
            base_img = pygame.transform.scale(base_img, (60, 60)).convert_alpha()
            self.arrow_anim_frames.append(base_img)
            self.arrow_up = base_img
        else:
            print("WARNING: Arrow image not found:", arrow_path)
            self.arrow_up = None
        for extra_path in [arrow_path_1, arrow_path_2]:
            if os.path.exists(extra_path):
                img = pygame.image.load(extra_path).convert_alpha()
                img = pygame.transform.scale(img, (60, 60)).convert_alpha()
                self.arrow_anim_frames.append(img)
        while len(self.arrow_anim_frames) < 3 and self.arrow_anim_frames:
            self.arrow_anim_frames.append(self.arrow_anim_frames[-1])

        # Outer down arrows (ArrowAllDown)
        self.arrow_down_frames = []
        if os.path.exists(arrow_down_path):
            base_img = pygame.image.load(arrow_down_path).convert_alpha()
            base_img = pygame.transform.scale(base_img, (60, 60)).convert_alpha()
            self.arrow_down_frames.append(base_img)
            self.arrow_down = base_img
        else:
            print("WARNING: Arrow image not found:", arrow_down_path)
            self.arrow_down = None
        for extra_path in [arrow_down_path_1, arrow_down_path_2]:
            if os.path.exists(extra_path):
                img = pygame.image.load(extra_path).convert_alpha()
                img = pygame.transform.scale(img, (60, 60)).convert_alpha()
                self.arrow_down_frames.append(img)
        while len(self.arrow_down_frames) < 3 and self.arrow_down_frames:
            self.arrow_down_frames.append(self.arrow_down_frames[-1])

        # Middle arrows - load animation frames for middle up arrow
        arrow_mid_path_2 = os.path.join("GameplayPage", "ArrowMiddle", "Arrow2.png")
        arrow_mid_path_3 = os.path.join("GameplayPage", "ArrowMiddle", "Arrow3.png")
        
        self.arrow_mid_up_frames = []
        if os.path.exists(arrow_mid_path):
            arrow_mid_img = pygame.image.load(arrow_mid_path).convert_alpha()
            arrow_mid_img = pygame.transform.scale(arrow_mid_img, (60, 60)).convert_alpha()
            self.arrow_mid_up_frames.append(arrow_mid_img)
            self.arrow_mid_up = arrow_mid_img
        else:
            print("WARNING: Middle Arrow image not found:", arrow_mid_path)
            self.arrow_mid_up = None
        
        # Load additional animation frames for middle up arrow
        for extra_path in [arrow_mid_path_2, arrow_mid_path_3]:
            if os.path.exists(extra_path):
                img = pygame.image.load(extra_path).convert_alpha()
                img = pygame.transform.scale(img, (60, 60)).convert_alpha()
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
            arrow_mid_down_base = pygame.transform.scale(arrow_mid_down_base, (60, 60)).convert_alpha()
            self.arrow_mid_down_frames.append(arrow_mid_down_base)
            self.arrow_mid_down = arrow_mid_down_base
        else:
            print("WARNING: Middle Down Arrow image not found:", arrow_mid_down_path_1)
            self.arrow_mid_down = None
        
        # Load additional animation frames for middle down arrow
        for extra_path in [arrow_mid_down_path_2, arrow_mid_down_path_3]:
            if os.path.exists(extra_path):
                img = pygame.image.load(extra_path).convert_alpha()
                img = pygame.transform.scale(img, (60, 60)).convert_alpha()
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
            self.bottom_frame = pygame.transform.scale(bottom_original, (target_width, target_height)).convert_alpha()
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
                    frame_img = pygame.transform.scale(frame_img, (self.animation_width, self.animation_height)).convert_alpha()
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
                    frame_img = pygame.transform.scale(frame_img, (self.animation_width, self.animation_height)).convert_alpha()
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
                    frame_img = pygame.transform.scale(frame_img, (self.animation_width, self.animation_height)).convert_alpha()
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
            return pygame.transform.scale(img, new_size).convert_alpha()

        self.logo_a = scale_logo(self.logo_a)
        self.logo_b = scale_logo(self.logo_b)
        self.logo_c = scale_logo(self.logo_c)

        # Load bundle of shares image
        bundle_path = os.path.join("GameplayPage", "A bundle of shares.png")
        if os.path.exists(bundle_path):
            bundle_original = pygame.image.load(bundle_path).convert_alpha()
            # Scale bundle image to 50% of original size
            w, h = bundle_original.get_width(), bundle_original.get_height()
            new_size = (int(w * 0.5), int(h * 0.5))
            self.bundle_image = pygame.transform.scale(bundle_original, new_size).convert_alpha()
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
            self.dollar_image = pygame.transform.scale(dollar_original, new_size).convert_alpha()
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
        self.Goal = 0  # Will be set from previous screen
        self.Money = 0  # Starts at 0
        self.Day = 1  # Current day/turn (starts at 1)
        self.MaxDays = 8  # Maximum number of days/turns

        # Load End Turn button
        end_button_path = os.path.join("GameplayPage", "EndButton.png")
        if os.path.exists(end_button_path):
            end_button_original = pygame.image.load(end_button_path).convert_alpha()
            # Scale button appropriately - adjust size as needed
            button_scale = 0.3  # Adjust this value to match screenshot size
            w, h = end_button_original.get_width(), end_button_original.get_height()
            new_size = (int(w * button_scale), int(h * button_scale))
            self.end_button = pygame.transform.scale(end_button_original, new_size).convert_alpha()
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
        self.Dobor = 1  # how many cards to draw after each turn by default
        placeholder_path = os.path.join("GameplayPage", "Placeholder.png")
        self.placeholder = pygame.image.load(placeholder_path).convert_alpha() if os.path.exists(placeholder_path) else None
        if self.placeholder:
            # Scale placeholder for bottom area: 138x240 (40% larger than 96x168: 30% + 10%)
            self.placeholder_bottom = pygame.transform.scale(self.placeholder, (138, 240)).convert_alpha()
            # Scale placeholder for market area: also 96x168 (увеличены на 20%)
            self.placeholder_market = pygame.transform.scale(self.placeholder, (96, 168)).convert_alpha()
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
        for card_id in range(5):
            card_base_mapping[card_id] = card_id  # Original cards use their own images
        card_base_mapping[11] = 11
        card_base_mapping[12] = 11
        card_base_mapping[13] = 11
        card_base_mapping[14] = 11
        card_base_mapping[15] = 15
        card_base_mapping[16] = 15
        card_base_mapping[17] = 17
        card_base_mapping[18] = 17
        
        # Load all card images (original 0-4, plus new cards 11-14, 15-16, 17-18)
        all_card_ids = list(range(5)) + [11, 12, 13, 14, 15, 16, 17, 18]
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
                    self.card_images_bottom[card_id] = pygame.transform.scale(card_img, self.card_size_bottom).convert_alpha()
                    # Pre-scale card for market area (smaller) - this prevents scaling on every frame
                    self.card_images_market[card_id] = pygame.transform.scale(card_img, self.card_size_market).convert_alpha()
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
        
        # Initialize deck: Card 0 (2x), Card 1 (2x), Card 2 (1x), Card 3 (2x), Card 4 (1x), Cards 11-14 (1x each), Cards 15-16 (1x each), Cards 17-18 (1x each)
        self.deck = [0, 0, 1, 1, 2, 3, 3, 4, 11, 12, 13, 14, 15, 16, 17, 18]
        # Shuffle deck
        random.shuffle(self.deck)
        
        # Deal cards to hand (first 7 cards from deck, 8th stays in deck) - keep fixed slots length
        initial_hand = self.deck[:self.hand] if len(self.deck) >= self.hand else self.deck.copy()
        self.hand_cards = [None] * self.hand
        for idx, card_id in enumerate(initial_hand):
            if idx < self.hand:
                self.hand_cards[idx] = card_id
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
    
    def handle_input(self):
        mouse_pos = pygame.mouse.get_pos()
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"
            
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
                                elif frame_idx == 1:  # Market B
                                    if self.Bquantity > 0:
                                        self.Money += self.BPrice
                                        self.Bquantity -= 1
                                elif frame_idx == 2:  # Market C
                                    if self.Cquantity > 0:
                                        self.Money += self.CPrice
                                        self.Cquantity -= 1
                            
                            # Bottom arrow (arrow_type == 3) - Sell all shares from THIS market only
                            elif entry.get("arrow_type") == 3:
                                # Determine which market and sell only its shares
                                if frame_idx == 0:  # Market A
                                    total_money = self.Aquantity * self.Aprice
                                    self.Money += total_money
                                    self.Aquantity = 0
                                elif frame_idx == 1:  # Market B
                                    total_money = self.Bquantity * self.BPrice
                                    self.Money += total_money
                                    self.Bquantity = 0
                                elif frame_idx == 2:  # Market C
                                    total_money = self.Cquantity * self.CPrice
                                    self.Money += total_money
                                    self.Cquantity = 0
                            
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
                            if self.Day < self.MaxDays:
                                self.Day += 1
                            else:
                                # Game over or reset days
                                self.Day = 1
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
                # All animations completed, process cards 11-18
                self.current_price_animation = None
                self._process_cards_11_14()
                if self.Day < self.MaxDays:
                    self.Day += 1
                else:
                    self.Day = 1
                # Draw cards that were delayed until animations finished
                self._draw_pending_cards()
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
                    # All animations completed, process cards 11-18
                    self.current_price_animation = None
                    self._process_cards_11_14()
                    if self.Day < self.MaxDays:
                        self.Day += 1
                    else:
                        # Game over or reset days
                        self.Day = 1
                    # Draw cards that were delayed until animations finished
                    self._draw_pending_cards()
    
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
            # Добор без анимации
            if self.Dobor > 0 and len(self.deck) > 0 and self.pending_draws > 0:
                draw_limit = min(self.Dobor, self.pending_draws, len(self.deck))
                start_idx = len(existing_cards)
                slots_available = self.hand - start_idx
                draw_count = min(draw_limit, slots_available)
                for offset in range(draw_count):
                    self.hand_cards[start_idx + offset] = self.deck.pop(0)
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
            # В руке вообще нет карт — просто добираем без анимации
            if self.Dobor > 0 and len(self.deck) > 0 and self.pending_draws > 0:
                draw_limit = min(self.Dobor, self.pending_draws, len(self.deck), self.hand)
                self.hand_cards = [None] * self.hand
                for i in range(draw_limit):
                    self.hand_cards[i] = self.deck.pop(0)
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

        # 4) Считаем, сколько карт нужно добрать после компактации
        free_slots_after = self.hand - len(existing)
        max_draw_by_slots = free_slots_after
        draw_limit = min(self.Dobor, self.pending_draws, len(self.deck), max_draw_by_slots)

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
                        self.hand_cards[start_idx + offset] = self.deck.pop(0)
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
                            self.hand_cards[first_free + offset] = self.deck.pop(0)

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
                    self.hand_cards[target_slot] = entry['card_id']
            
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
            day_text = self.font_medium.render(f"Day: {self.Day} /{self.MaxDays}", True, PAPER_COLOR)
            day_text_x = self.end_button_rect.x - day_text.get_width() - 20  # 20px spacing from button
            day_text_y = self.end_button_rect.y + (self.end_button_rect.height - day_text.get_height()) // 2  # Vertically centered with button
            self.screen.blit(day_text, (day_text_x, day_text_y))
        
        pygame.display.flip()
    
    def run(self):
        while True:
            result = self.handle_input()
            
            if result == "quit":
                pygame.quit()
                sys.exit()
            
            if result == "back":
                return "back"
            
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

            self.draw()
            self.clock.tick(FPS)


class BossPage:
    def __init__(self, screen, font_path, level_number):
        self.screen = screen
        self.clock = pygame.time.Clock()
        self.level_number = level_number
        
        # Load Back3.png from UI folder (same as level selection screen)
        back3_path = os.path.join("UI", "Back3.png")
        if os.path.exists(back3_path):
            self.background = pygame.image.load(back3_path).convert()
            self.background = pygame.transform.scale(self.background, (SCREEN_WIDTH, SCREEN_HEIGHT)).convert()
        else:
            print("WARNING: Back3.png not found:", back3_path)
            self.background = None
        
        # Load Koordinates.png from RoundPage folder
        koordinates_path = os.path.join("RoundPage", "Koordinates.png")
        if os.path.exists(koordinates_path):
            self.koordinates = pygame.image.load(koordinates_path).convert_alpha()
            self.koordinates = pygame.transform.scale(self.koordinates, (SCREEN_WIDTH, SCREEN_HEIGHT)).convert_alpha()
        else:
            print("WARNING: Koordinates.png not found:", koordinates_path)
            self.koordinates = None
        
        # Define bosses for each level
        # Format: {level_number: [list of boss filenames]}
        self.level_bosses = {
            1: ["1_Watt.png"]
            # Add more levels and their bosses here as needed
        }
        
        # Load bosses for current level
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
            self.popup_image = pygame.transform.scale(popup_original, (250, 375)).convert_alpha()
        else:
            print(f"WARNING: PopUp.png not found: {popup_path}")
            self.popup_image = None
        
        # PopUp animation state
        self.popup_y = -200  # Start above screen (hidden)
        self.popup_x = 0
        self.popup_target_y = -200  # Target Y position
        self.popup_speed = 25  # Pixels per frame for smooth movement
        self.current_hovered_boss_index = None  # Track which boss is hovered for PopUp
        self.popup_boss_index = None  # Track which boss text to show (persists until PopUp hides)
        
        # Load font for PopUp text
        self.popup_font = pygame.font.Font(font_path, 24)
        
        # Map boss indices to text keys in Lang.csv
        # Format: {boss_index: "LangKey"}
        self.boss_text_keys = {
            0: "Boss1Text"  # Boss 1 (Watt)
            # Add more bosses here as needed: 1: "Boss2Text", etc.
        }
        
        # Store boss texts
        self.boss_texts = {}
        for boss_index, text_key in self.boss_text_keys.items():
            self.boss_texts[boss_index] = get_text(text_key, text_key)
        
        if self.level_number in self.level_bosses:
            for boss_filename in self.level_bosses[self.level_number]:
                boss_path = os.path.join("Bosses", boss_filename)
                if os.path.exists(boss_path):
                    boss_image = pygame.image.load(boss_path).convert_alpha()
                    # Scale to 100x100
                    boss_image = pygame.transform.scale(boss_image, (100, 100)).convert_alpha()
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
                                frame_image = pygame.transform.scale(frame_image, (100, 100)).convert_alpha()
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
        
        # Calculate First boss positions in bottom left part of screen
        boss_spacing = 60  # Spacing between bosses
        start_x = 350  # Left margin
        start_y = SCREEN_HEIGHT - 400  # Bottom margin (100px from bottom)
        
        for i, boss_image in enumerate(self.bosses):
            boss_x = start_x
            boss_y = start_y - (i * boss_spacing)  # Stack bosses vertically
            self.boss_rects.append(pygame.Rect(boss_x, boss_y, 100, 100))
    
    def handle_input(self):
        mouse_pos = pygame.mouse.get_pos()
        
        # Check which boss is being hovered
        hovered_boss = None
        for i, boss_rect in enumerate(self.boss_rects):
            if boss_rect.collidepoint(mouse_pos):
                hovered_boss = i
                break
        
        # Update PopUp position based on hover
        if hovered_boss is not None:
            # Set target position for PopUp
            boss_rect = self.boss_rects[hovered_boss]
            self.popup_target_y = boss_rect.y-250  # Y coordinate of the boss
            self.popup_x = boss_rect.x + 100  # X = boss.x + 70
            self.current_hovered_boss_index = hovered_boss
            self.popup_boss_index = hovered_boss  # Save boss index for text display
        else:
            # Move PopUp back above screen when not hovering
            self.popup_target_y = -350
            self.current_hovered_boss_index = None
            # Don't clear popup_boss_index here - let it persist until PopUp is hidden
        
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
        
        # Update PopUp position with smooth animation
        if abs(self.popup_y - self.popup_target_y) > 1:
            # Smooth movement towards target
            if self.popup_y < self.popup_target_y:
                self.popup_y = min(self.popup_y + self.popup_speed, self.popup_target_y)
            else:
                self.popup_y = max(self.popup_y - self.popup_speed, self.popup_target_y)
        else:
            self.popup_y = self.popup_target_y
        
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
            self.screen.blit(self.popup_image, (self.popup_x, self.popup_y))
            
            # Draw text on PopUp if a boss text is available (persists until PopUp hides)
            if self.popup_boss_index is not None and self.popup_boss_index in self.boss_texts:
                text = self.boss_texts[self.popup_boss_index]
                
                # Split text into multiple lines to fit in PopUp (250px wide)
                max_width = 220  # Leave some padding (250 - 30px total padding)
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
                text_start_y = self.popup_y + 120  # Top padding
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
    def __init__(self, screen, font_path, level_number, boss_index):
        self.screen = screen
        self.clock = pygame.time.Clock()
        self.level_number = level_number
        self.boss_index = boss_index
        
        # Load Back3.png from UI folder (same as level selection screen)
        back3_path = os.path.join("UI", "Back3.png")
        if os.path.exists(back3_path):
            self.background = pygame.image.load(back3_path).convert()
            self.background = pygame.transform.scale(self.background, (SCREEN_WIDTH, SCREEN_HEIGHT)).convert()
        else:
            print("WARNING: Back3.png not found:", back3_path)
            self.background = None
        
        # Load Koordinates.png from RoundPage folder
        koordinates_path = os.path.join("RoundPage", "Koordinates.png")
        if os.path.exists(koordinates_path):
            self.koordinates = pygame.image.load(koordinates_path).convert_alpha()
            self.koordinates = pygame.transform.scale(self.koordinates, (SCREEN_WIDTH, SCREEN_HEIGHT)).convert_alpha()
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
            self.button_e = pygame.transform.scale(button_e_original, (new_width, new_height)).convert_alpha()
        else:
            print("WARNING: LevelButtonE not found:", button_e_path)
            self.button_e = None
        
        if os.path.exists(button_m_path):
            button_m_original = pygame.image.load(button_m_path).convert_alpha()
            # Scale down by 5x (divide by 5)
            new_width = button_m_original.get_width() // 5
            new_height = button_m_original.get_height() // 5
            self.button_m = pygame.transform.scale(button_m_original, (new_width, new_height)).convert_alpha()
        else:
            print("WARNING: LevelButtonM not found:", button_m_path)
            self.button_m = None
        
        if os.path.exists(button_h_path):
            button_h_original = pygame.image.load(button_h_path).convert_alpha()
            # Scale down by 5x (divide by 5)
            new_width = button_h_original.get_width() // 5
            new_height = button_h_original.get_height() // 5
            self.button_h = pygame.transform.scale(button_h_original, (new_width, new_height)).convert_alpha()
        else:
            print("WARNING: LevelButtonH not found:", button_h_path)
            self.button_h = None
        
        # Calculate button positions
        if self.button_e:
            button_e_height = self.button_e.get_height()
            button_e_width = self.button_e.get_width()
            button_e_x = 130  # 130px from left
            button_e_y = SCREEN_HEIGHT - button_e_height - 120  # 120px up from bottom
            self.button_e_rect = pygame.Rect(button_e_x, button_e_y, button_e_width, button_e_height)
        else:
            self.button_e_rect = None
            button_e_y = SCREEN_HEIGHT - 120
            button_e_x = 130
        
        if self.button_m:
            button_m_height = self.button_m.get_height()
            button_m_width = self.button_m.get_width()
            button_m_y = button_e_y - 30 - button_m_height
            button_m_x = button_e_x  # Same x position as LevelButtonE
            self.button_m_rect = pygame.Rect(button_m_x, button_m_y, button_m_width, button_m_height)
        else:
            self.button_m_rect = None
            button_m_y = button_e_y - 30  # Fallback position
        
        if self.button_h:
            button_h_height = self.button_h.get_height()
            button_h_width = self.button_h.get_width()
            button_h_y = button_m_y - 30 - button_h_height
            button_h_x = button_e_x  # Same x position as LevelButtonE
            self.button_h_rect = pygame.Rect(button_h_x, button_h_y, button_h_width, button_h_height)
        else:
            self.button_h_rect = None
        
        self.hovered_button = None  # Track which button is hovered
    
    def handle_input(self):
        mouse_pos = pygame.mouse.get_pos()
        
        # Check which button is hovered (using original rect for hover detection)
        self.hovered_button = None
        if self.button_e_rect and self.button_e_rect.collidepoint(mouse_pos):
            self.hovered_button = "e"
        elif self.button_m_rect and self.button_m_rect.collidepoint(mouse_pos):
            self.hovered_button = "m"
        elif self.button_h_rect and self.button_h_rect.collidepoint(mouse_pos):
            self.hovered_button = "h"
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"
            
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return "back"
            
            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # Left click
                    if self.button_e_rect and self.button_e_rect.collidepoint(mouse_pos):
                        print("LevelButtonE (bottom) clicked")
                        return "button_e"
                    if self.button_m_rect and self.button_m_rect.collidepoint(mouse_pos):
                        print("LevelButtonM (middle) clicked")
                        return "button_m"
                    if self.button_h_rect and self.button_h_rect.collidepoint(mouse_pos):
                        print("LevelButtonH (upper) clicked")
                        return "button_h"
        
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
        
        # Draw buttons (from bottom to top: E, M, H)
        if self.button_e and self.button_e_rect:
            self.screen.blit(self.button_e, self.button_e_rect.topleft)
        
        if self.button_m and self.button_m_rect:
            self.screen.blit(self.button_m, self.button_m_rect.topleft)
        
        if self.button_h and self.button_h_rect:
            self.screen.blit(self.button_h, self.button_h_rect.topleft)
        
        pygame.display.flip()
    
    def run(self):
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
            
            self.draw()
            self.clock.tick(FPS)


def load_background():
    """Load background image"""
    bg_path = os.path.join("UI", "Background.png")
    if os.path.exists(bg_path):
        background = pygame.image.load(bg_path).convert()
        background = pygame.transform.scale(background, (SCREEN_WIDTH, SCREEN_HEIGHT)).convert()
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
        
        if result == "start":
            # LevelPage loop
            while True:
                level_page = GameScreen(screen, background, font_path)  # LevelPage
                level_result = level_page.run()
                
                if level_result == "back":
                    break  # Return to start page
                elif level_result and level_result.startswith("level_"):
                    # Level selected, go to BossPage
                    try:
                        level_num = int(level_result.split("_")[1])
                        boss_page = BossPage(screen, font_path, level_num)
                        boss_result = boss_page.run()
                        
                        if boss_result == "back":
                            continue  # Return to level page (stay in level page loop)
                        elif boss_result == "quit":
                            break  # Exit game
                        elif boss_result and boss_result.startswith("boss_"):
                            # Boss selected, go to RoundPage
                            # Format: boss_level_bossIndex
                            parts = boss_result.split("_")
                            boss_level = int(parts[1])
                            boss_index = int(parts[2])
                            
                            round_page = RoundPage(screen, font_path, boss_level, boss_index)
                            round_result = round_page.run()
                            
                            if round_result == "back":
                                continue  # Return to boss page (stay in level page loop)
                            elif round_result == "quit":
                                break  # Exit game
                            elif round_result in ("button_e", "button_m", "button_h"):
                                # Round selected, go to GameplayPage
                                difficulty = round_result.split("_")[1]  # Extract "e", "m", or "h"
                                gameplay_page = GameplayPage(screen, font_path, difficulty)
                                gameplay_result = gameplay_page.run()
                                
                                if gameplay_result == "back":
                                    # Return to round page
                                    round_page = RoundPage(screen, font_path, boss_level, boss_index)
                                    round_result = round_page.run()
                                    if round_result == "back":
                                        continue
                                elif gameplay_result == "game_over":
                                    # Handle game over
                                    print("Game Over!")
                                    continue
                        else:
                            # If BossPage returns something unexpected, return to level page
                            continue
                    except Exception as e:
                        print(f"ERROR in navigation: {e}")
                        import traceback
                        traceback.print_exc()
                        continue  # Return to level page on error
        elif result == "quit":
            break
    
    pygame.quit()
    sys.exit()
