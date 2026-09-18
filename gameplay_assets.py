import os

import pygame

from adaptive_ui import cover_geometry
from asset_loaders import load_scaled_image
from card_catalog import CARD_IMAGE_BASE_IDS, MARKET_CARD_TURNS, PRICE_CARD_ACTIONS, PRICE_CARD_IDS
from game_data import REWARD_TOKEN_RANDOM_SILVER
from gameplay_card_rendering import draw_bid_modifier_text, is_bid_card
from sound_assets import load_card_taking_sound


_gameplay_core_assets_cache = {}
_end_turn_button_cache = {}
_gameplay_placeholders_cache = None
_gameplay_card_assets_cache = {}
_winlose_assets_cache = {}
_deck_view_assets_cache = {}
_card_placing_sound_cache = None
_card_placing_sound_loaded = False


def load_gameplay_background(viewport_size):
    """Fill the viewport with a centered, proportionally scaled master image."""
    master = load_scaled_image(
        os.path.join("GameplayPage", "Master Background.png"),
        warning_message="WARNING: GameplayPage Master Background.png not found:",
    )
    if master is None:
        return None

    scaled_size, position = cover_geometry(master.get_size(), viewport_size)
    background = pygame.Surface(viewport_size).convert()
    background.blit(pygame.transform.smoothscale(master, scaled_size), position)
    return background


def build_hand_frame(market_frame, target_size):
    """Reuse market-frame artwork, stretching only the undecorated edge spans.

    Five bands per axis keep both the corners and middle ornaments at their
    original on-screen scale. The cuts follow GameplayPage/Frame.png artwork.
    """
    def bands(source_length, target_length, fractions):
        source = [round(source_length * fraction) for fraction in fractions]
        middle_width = source[3] - source[2]
        middle_start = (target_length - middle_width) // 2
        target = [
            0, source[1], middle_start, middle_start + middle_width,
            target_length - (source_length - source[4]), target_length,
        ]
        if any(right <= left for left, right in zip(target, target[1:])):
            raise ValueError("Hand frame is too small to preserve its ornaments")
        return source, target

    source_x, target_x = bands(
        market_frame.get_width(), target_size[0], (0, .12, .38, .58, .88, 1),
    )
    source_y, target_y = bands(
        market_frame.get_height(), target_size[1], (0, .08, .42, .55, .92, 1),
    )
    frame = pygame.Surface(target_size, pygame.SRCALPHA)
    for row in range(5):
        for column in range(5):
            if row not in (0, 4) and column not in (0, 4):
                continue  # Keep the card area transparent.
            source_rect = pygame.Rect(
                source_x[column], source_y[row],
                source_x[column + 1] - source_x[column],
                source_y[row + 1] - source_y[row],
            )
            target_rect = pygame.Rect(
                target_x[column], target_y[row],
                target_x[column + 1] - target_x[column],
                target_y[row + 1] - target_y[row],
            )
            tile = market_frame.subsurface(source_rect)
            if tile.get_size() != target_rect.size:
                tile = pygame.transform.smoothscale(tile, target_rect.size)
            frame.blit(tile, target_rect)
    return frame


def load_trade_arrows():
    """Load supplied ordinary and buy/sell-all poses, rotating down variants."""
    all_frames, all_up = _load_arrow_sequence(
        os.path.join("GameplayPage", "ArrowAll", "ArrowAll.png"),
        [
            os.path.join("GameplayPage", "ArrowAll", "ArrowAll-1.png"),
            os.path.join("GameplayPage", "ArrowAll", "ArrowAll-2.png"),
        ],
        "WARNING: Buy/sell-all arrow image not found:",
    )
    all_down_frames = [pygame.transform.rotate(frame, 180) for frame in all_frames]
    assets = {
        "arrow_up": all_up,
        "arrow_anim_frames": all_frames,
        "arrow_down": all_down_frames[0] if all_down_frames else None,
        "arrow_down_frames": all_down_frames,
    }
    single_frames, single_up = _load_arrow_sequence(
        os.path.join("GameplayPage", "Arrow1.png"),
        [
            os.path.join("GameplayPage", "NewArrow", "Arrow-1.png"),
            os.path.join("GameplayPage", "NewArrow", "Arrow-2.png"),
        ],
        "WARNING: Ordinary arrow image not found:",
    )
    down_frames = [pygame.transform.rotate(frame, 180) for frame in single_frames]
    assets["arrow_mid_up"] = single_up
    assets["arrow_mid_up_frames"] = single_frames
    assets["arrow_mid_down"] = down_frames[0] if down_frames else None
    assets["arrow_mid_down_frames"] = down_frames
    return assets


def load_gameplay_core_assets(screen_width, screen_height):
    """Load core static assets used by GameplayPage."""
    cache_key = (screen_width, screen_height)
    cached = _gameplay_core_assets_cache.get(cache_key)
    if cached is not None:
        return dict(cached)

    assets = {}

    assets["background"] = load_gameplay_background((screen_width, screen_height))

    frame_path = os.path.join("GameplayPage", "Frame.png")
    if os.path.exists(frame_path):
        frame_original = pygame.image.load(frame_path).convert_alpha()
        frame_width = int((screen_width // 3 - 20) * 0.7)
        scale_factor = frame_width / frame_original.get_width()
        frame_height = int(frame_original.get_height() * scale_factor)
        assets["frame"] = pygame.transform.smoothscale(frame_original, (frame_width, frame_height)).convert_alpha()
    else:
        print("WARNING: Frame.png not found:", frame_path)
        assets["frame"] = None

    assets.update(load_trade_arrows())

    if assets["frame"] is not None:
        market_spacing = 10
        target_width = assets["frame"].get_width() * 3 + market_spacing * 2
        # Preserve the existing hand geometry (the old frame was 507 x 131).
        target_height = int(131 * (target_width / 507))
        assets["bottom_frame"] = build_hand_frame(
            assets["frame"], (target_width, target_height),
        )
    else:
        assets["bottom_frame"] = None

    assets["arrow_sound"] = _load_sound(os.path.join("Sounds", "Cliack3.wav"), "WARNING: Cliack3.wav not found at")
    assets["end_turn_sound"] = _load_sound(os.path.join("Sounds", "Click2.wav"), "WARNING: Click2.wav not found at")
    assets["menu_sound"] = _load_sound(os.path.join("Sounds", "Click2.wav"), "WARNING: Click2.wav not found at")
    assets["typewriter_sound"] = _load_sound(os.path.join("Sounds", "Typewriter.wav"), "WARNING: Typewriter.wav not found at")
    assets["cash_register_sound"] = _load_sound(
        os.path.join("Sounds", "cash-register.mp3"),
        "WARNING: cash-register.mp3 not found at",
    )
    assets["card_placing_sound"] = load_card_placing_sound()
    assets["card_hover_sound"] = _load_sound(os.path.join("Sounds", "Card.wav"), "WARNING: Card.wav not found at")
    assets["card_taking_sound"] = load_card_taking_sound()

    assets["animation_width"] = 118
    assets["animation_height"] = 101
    assets["price_unchanged_frames"] = _load_numbered_frames(
        os.path.join("GameplayPage", "Graph="),
        range(21),
        assets["animation_width"],
        assets["animation_height"],
        "WARNING: Graph= folder not found:",
        "WARNING: Frame {i}.png not found in Graph= folder",
    )
    assets["price_rise_frames"] = _load_numbered_frames(
        os.path.join("GameplayPage", "GraphRise"),
        range(1, 16),
        assets["animation_width"],
        assets["animation_height"],
        "WARNING: GraphRise folder not found:",
        "WARNING: Frame {i}.png not found in GraphRise folder",
    )
    assets["price_fall_frames"] = _load_numbered_frames(
        os.path.join("GameplayPage", "GraphDown"),
        range(1, 18),
        assets["animation_width"],
        assets["animation_height"],
        "WARNING: GraphDown folder not found:",
        "WARNING: Frame {i}.png not found in GraphDown folder",
    )

    assets["logo_a"] = _load_logo(os.path.join("GameplayPage", "A logo New.png"))
    assets["logo_b"] = _load_logo(os.path.join("GameplayPage", "B Logo New.png"))
    assets["logo_c"] = _load_logo(os.path.join("GameplayPage", "C Logo New.png"))
    assets["bundle_image"] = _load_scaled_half_image(
        os.path.join("GameplayPage", "A bundle of shares.png"),
        "WARNING: A bundle of shares.png not found:",
    )
    assets["dollar_image"] = _load_scaled_half_image(
        os.path.join("GameplayPage", "Dollar.png"),
        "WARNING: Dollar.png not found:",
    )
    napoleondor_path = os.path.join("Shop", "Napoleondor.png")
    if os.path.exists(napoleondor_path):
        napoleondor_original = pygame.image.load(napoleondor_path).convert_alpha()
        assets["napoleondor_image"] = pygame.transform.smoothscale(
            napoleondor_original,
            (34, 34),
        ).convert_alpha()
    else:
        print("WARNING: Napoleondor.png not found:", napoleondor_path)
        assets["napoleondor_image"] = None

    _gameplay_core_assets_cache[cache_key] = assets
    return dict(assets)


def load_end_turn_button(screen_width, screen_height):
    """Load End Turn button and its clickable rect."""
    cache_key = (screen_width, screen_height)
    cached = _end_turn_button_cache.get(cache_key)
    if cached is not None:
        button, rect = cached
        return button, rect.copy() if rect else None

    end_button_path = os.path.join("GameplayPage", "End Turn.png")
    if os.path.exists(end_button_path):
        end_button_original = pygame.image.load(end_button_path).convert_alpha()
        end_button_original = end_button_original.subsurface(end_button_original.get_bounding_rect()).copy()
        w, h = end_button_original.get_width(), end_button_original.get_height()
        button_width = round(250 / 1.5)
        new_size = (button_width, max(1, round(h * button_width / w)))
        end_button = pygame.transform.smoothscale(end_button_original, new_size).convert_alpha()
        button_margin_right = 50
        button_margin_bottom = 50
        button_x = screen_width - new_size[0] - button_margin_right
        button_y = screen_height - new_size[1] - button_margin_bottom
        rect = pygame.Rect(button_x, button_y, new_size[0], new_size[1])
        _end_turn_button_cache[cache_key] = (end_button, rect)
        return end_button, rect.copy()

    print("WARNING: End Turn.png not found:", end_button_path)
    _end_turn_button_cache[cache_key] = (None, None)
    return None, None


def load_gameplay_placeholders():
    """Load and scale GameplayPage placeholder images."""
    global _gameplay_placeholders_cache
    if _gameplay_placeholders_cache is not None:
        return dict(_gameplay_placeholders_cache)

    placeholder_path = os.path.join("GameplayPage", "Placeholder.png")
    placeholder = pygame.image.load(placeholder_path).convert_alpha() if os.path.exists(placeholder_path) else None
    if not placeholder:
        _gameplay_placeholders_cache = {
            "placeholder": None,
            "placeholder_bottom": None,
            "placeholder_market": None,
            "placeholder_side": None,
        }
        return dict(_gameplay_placeholders_cache)

    side_ph_w = int(96 * 0.85)
    side_ph_h = int(168 * 0.85)
    _gameplay_placeholders_cache = {
        "placeholder": placeholder,
        "placeholder_bottom": pygame.transform.smoothscale(placeholder, (138, 240)).convert_alpha(),
        "placeholder_market": pygame.transform.smoothscale(placeholder, (96, 168)).convert_alpha(),
        "placeholder_side": pygame.transform.smoothscale(placeholder, (side_ph_w, side_ph_h)).convert_alpha(),
    }
    return dict(_gameplay_placeholders_cache)


def load_gameplay_card_assets(
    card_types, card_size_bottom, card_size_market, card_size_side, *, original_card_ids=None,
):
    """Load card images, retaining only requested originals (None retains all)."""
    card_types_key = tuple(sorted((int(cid), int(card_type)) for cid, card_type in (card_types or {}).items()))
    original_ids = None if original_card_ids is None else frozenset(original_card_ids)
    cache_key = (
        card_types_key,
        tuple(card_size_bottom),
        tuple(card_size_market),
        tuple(card_size_side),
        original_ids,
    )
    cached = _gameplay_card_assets_cache.get(cache_key)
    if cached is not None:
        return _copy_card_assets(cached)

    card_base_mapping = _build_card_base_mapping()
    base_card_ids = [1, 2, 3, 4, 100]
    try:
        config_card_ids = [int(x) for x in (card_types.keys() if card_types else [])]
    except Exception:
        config_card_ids = []

    all_card_ids = sorted(set(base_card_ids + list(PRICE_CARD_IDS) + [REWARD_TOKEN_RANDOM_SILVER] + config_card_ids))
    card_images_original = {}
    card_images_bottom = {}
    card_images_market = {}
    card_images_side = {}
    base_image_cache = {}
    scaled_image_cache = {}

    for card_id in all_card_ids:
        base_id = card_base_mapping.get(card_id, card_id)
        if card_id == REWARD_TOKEN_RANDOM_SILVER or 200 < int(card_id) < 300:
            card_path_underscore = os.path.join("Cards", f"Card_{int(card_id)}.png")
            if not os.path.exists(card_path_underscore):
                card_path_underscore = os.path.join("RoundPage", "RandSilver.png")
            if not os.path.exists(card_path_underscore):
                card_path_underscore = os.path.join("Cards", "Card_201.png")
            card_path_space = None
        else:
            card_path_underscore = os.path.join("Cards", f"Card_{base_id}.png")
            card_path_space = os.path.join("Cards", f"Card {base_id}.png")

        card_path = None
        if os.path.exists(card_path_underscore):
            card_path = card_path_underscore
        elif card_path_space and os.path.exists(card_path_space):
            card_path = card_path_space

        if card_path:
            try:
                card_img = base_image_cache.get(base_id)
                if card_img is None:
                    card_img = pygame.image.load(card_path).convert_alpha()
                    base_image_cache[base_id] = card_img
                bottom_key = (base_id, "bottom", card_size_bottom)
                market_key = (base_id, "market", card_size_market)
                side_key = (base_id, "side", card_size_side)
                original_img = None
                if original_ids is None or card_id in original_ids:
                    original_img = card_img
                    if is_bid_card(card_id):
                        original_img = card_img.copy()
                        draw_bid_modifier_text(
                            original_img,
                            card_id,
                            0,
                            0,
                            (original_img.get_width(), original_img.get_height()),
                            None,
                        )
                card_images_original[card_id] = original_img
                if bottom_key not in scaled_image_cache:
                    scaled_image_cache[bottom_key] = pygame.transform.smoothscale(card_img, card_size_bottom).convert_alpha()
                if market_key not in scaled_image_cache:
                    scaled_image_cache[market_key] = pygame.transform.smoothscale(card_img, card_size_market).convert_alpha()
                if side_key not in scaled_image_cache:
                    scaled_image_cache[side_key] = pygame.transform.smoothscale(card_img, card_size_side).convert_alpha()
                bottom_img = scaled_image_cache[bottom_key]
                market_img = scaled_image_cache[market_key]
                side_img = scaled_image_cache[side_key]
                if is_bid_card(card_id):
                    bottom_img = bottom_img.copy()
                    market_img = market_img.copy()
                    side_img = side_img.copy()
                    draw_bid_modifier_text(bottom_img, card_id, 0, 0, card_size_bottom, None)
                    draw_bid_modifier_text(market_img, card_id, 0, 0, card_size_market, None)
                    draw_bid_modifier_text(side_img, card_id, 0, 0, card_size_side, None)
                card_images_bottom[card_id] = bottom_img
                card_images_market[card_id] = market_img
                card_images_side[card_id] = side_img
            except Exception as e:
                print(f"ERROR loading card {card_id} (base: {base_id}): {e}")
                card_images_original[card_id] = None
                card_images_bottom[card_id] = None
                card_images_market[card_id] = None
                card_images_side[card_id] = None
        else:
            print(
                f"WARNING: Card file not found for card {card_id} (base: {base_id}). "
                f"Tried: {card_path_underscore} and {card_path_space}"
            )
            card_images_original[card_id] = None
            card_images_bottom[card_id] = None
            card_images_market[card_id] = None
            card_images_side[card_id] = None

    assets = {
        "card_images_original": card_images_original,
        "card_images_bottom": card_images_bottom,
        "card_images_market": card_images_market,
        "card_images_side": card_images_side,
        "card_actions": _build_card_actions(),
        "card_turns": _build_card_turns(),
    }
    _gameplay_card_assets_cache[cache_key] = assets
    return _copy_card_assets(assets)


def load_winlose_assets(screen_width, screen_height):
    """Load Win/Lose window and OK button assets."""
    cache_key = (screen_width, screen_height)
    cached = _winlose_assets_cache.get(cache_key)
    if cached is not None:
        assets = dict(cached)
        assets["_winlose_last_tick"] = pygame.time.get_ticks()
        return assets

    assets = {}
    winlose_path = os.path.join("GameplayPage", "WinLose.png")
    if os.path.exists(winlose_path):
        winlose_original = pygame.image.load(winlose_path).convert_alpha()
        winlose_width = screen_width // 3
        winlose_height = screen_height // 3
        assets["win_lose_image"] = pygame.transform.smoothscale(
            winlose_original,
            (winlose_width, winlose_height),
        ).convert_alpha()
        assets["win_lose_x"] = (screen_width - winlose_width) // 2
        assets["win_lose_y"] = float(-winlose_height)
        assets["win_lose_target_y"] = float((screen_height - winlose_height) // 2)
        assets["win_lose_speed_pps"] = 1200.0
    else:
        print("WARNING: WinLose.png not found:", winlose_path)
        assets["win_lose_image"] = None
        assets["win_lose_x"] = 0
        assets["win_lose_y"] = 0.0
        assets["win_lose_target_y"] = 0
        assets["win_lose_speed_pps"] = 0.0

    assets["_winlose_last_tick"] = pygame.time.get_ticks()

    ok1_button, ok_button_base_size = _load_ok_button(os.path.join("GameplayPage", "Ok1.png"), "WARNING: Ok1.png not found:")
    assets["ok1_button"] = ok1_button
    assets["ok_button_base_size"] = ok_button_base_size

    ok2_button, ok2_size = _load_ok_button(os.path.join("GameplayPage", "Ok2.png"), "WARNING: Ok2.png not found:")
    assets["ok2_button"] = ok2_button
    if assets["ok_button_base_size"] == (0, 0):
        assets["ok_button_base_size"] = ok2_size

    finance_height = max(1, int(screen_height * 0.84))
    finance_width = max(1, int(finance_height * 1086 / 1448))
    finance_specs = (
        ("finance_report_image", "FinanceReport.png", (finance_width, finance_height)),
        ("card_report_image", "CardReport.png", (finance_width, finance_height)),
        ("approve_stamp_image", "ApproveStamp.png", (230, 96)),
        ("stamp_on_paper_image", "StampOnPaper.png", (205, 123)),
    )
    for key, filename, size in finance_specs:
        path = os.path.join("Arts", filename)
        if not os.path.exists(path):
            print(f"WARNING: {filename} not found:", path)
            assets[key] = None
            continue
        original = pygame.image.load(path).convert_alpha()
        assets[key] = pygame.transform.smoothscale(original, size).convert_alpha()

    assets["stamp_sound"] = _load_sound(
        os.path.join("Sounds", "Stamp.mp3"),
        "WARNING: Stamp.mp3 not found at",
    )
    assets["report_rustle_sound"] = _load_sound(
        os.path.join("Sounds", "Pen.mp3"),
        "WARNING: Pen.mp3 not found at",
    )

    _winlose_assets_cache[cache_key] = dict(assets)
    return dict(assets)


def load_deck_view_assets(screen_width, screen_height):
    """Load the collection-panel background and footer navigation icons."""
    cache_key = (screen_width, screen_height)
    cached = _deck_view_assets_cache.get(cache_key)
    if cached is not None:
        return dict(cached)

    background = None
    background_path = os.path.join("RoundPage", "SilverBlack.png")
    if os.path.exists(background_path):
        original = pygame.image.load(background_path).convert()
        background = pygame.transform.smoothscale(original, (screen_width, screen_height)).convert()
    else:
        print("WARNING: Deck view background not found:", background_path)

    icons = {
        mode: load_scaled_image(os.path.join("GameplayPage", filename), target_size=(96, 96))
        for mode, filename in (("deck", "Deck.png"), ("offers", "Offers.png"), ("bosses", "Bosses.png"))
    }

    assets = {
        "deck_view_background": background,
        "deck_toggle_card": icons["deck"],
        "collection_icons": icons,
    }
    _deck_view_assets_cache[cache_key] = assets
    return dict(assets)


def _copy_card_assets(assets):
    copied = dict(assets)
    for key in ("card_images_original", "card_images_bottom", "card_images_market", "card_images_side"):
        copied[key] = dict(assets.get(key, {}))
    copied["card_actions"] = dict(assets.get("card_actions", {}))
    copied["card_turns"] = dict(assets.get("card_turns", {}))
    return copied


def _load_arrow_sequence(base_path, extra_paths, warning_message):
    frames = []
    primary = None
    if os.path.exists(base_path):
        base_img = pygame.image.load(base_path).convert_alpha()
        base_img = pygame.transform.smoothscale(base_img, (60, 60)).convert_alpha()
        frames.append(base_img)
        primary = base_img
    else:
        print(warning_message, base_path)
    for extra_path in extra_paths:
        if os.path.exists(extra_path):
            img = pygame.image.load(extra_path).convert_alpha()
            img = pygame.transform.smoothscale(img, (60, 60)).convert_alpha()
            frames.append(img)
    while len(frames) < 3 and frames:
        frames.append(frames[-1])
    return frames, primary


def _load_numbered_frames(folder_path, indices, width, height, missing_folder_warning, missing_frame_template):
    frames = []
    if os.path.exists(folder_path):
        for i in indices:
            frame_path = os.path.join(folder_path, f"{i}.png")
            if os.path.exists(frame_path):
                frame_img = pygame.image.load(frame_path).convert_alpha()
                frame_img = pygame.transform.smoothscale(frame_img, (width, height)).convert_alpha()
                frames.append(frame_img)
            else:
                print(missing_frame_template.format(i=i))
    else:
        print(missing_folder_warning, folder_path)
    return frames


def _load_logo(path):
    if not os.path.exists(path):
        return None
    img = pygame.image.load(path).convert_alpha()
    max_logo_w, max_logo_h = 112, 128
    scale = min(max_logo_w / img.get_width(), max_logo_h / img.get_height())
    new_size = (int(img.get_width() * scale), int(img.get_height() * scale))
    return pygame.transform.smoothscale(img, new_size).convert_alpha()


def _load_scaled_half_image(path, warning_message):
    if not os.path.exists(path):
        print(warning_message, path)
        return None
    original = pygame.image.load(path).convert_alpha()
    new_size = (int(original.get_width() * 0.5), int(original.get_height() * 0.5))
    return pygame.transform.smoothscale(original, new_size).convert_alpha()


def _load_sound(path, warning_message):
    if os.path.exists(path):
        return pygame.mixer.Sound(path)
    print(warning_message, path)
    return None


def load_card_placing_sound():
    """Load the shared sound used whenever a card lands on a placeholder."""
    global _card_placing_sound_cache, _card_placing_sound_loaded
    if not _card_placing_sound_loaded:
        _card_placing_sound_cache = _load_sound(
            os.path.join("Sounds", "Placing Card.wav"),
            "WARNING: Placing Card.wav not found at",
        )
        _card_placing_sound_loaded = True
    return _card_placing_sound_cache


def _build_card_base_mapping():
    return dict(CARD_IMAGE_BASE_IDS)


def _build_card_actions():
    return dict(PRICE_CARD_ACTIONS)


def _build_card_turns():
    return dict(MARKET_CARD_TURNS)


def _load_ok_button(path, warning_message):
    if not os.path.exists(path):
        print(warning_message, path)
        return None, (0, 0)
    original = pygame.image.load(path).convert_alpha()
    ok_scale = 1.0
    size = (int(original.get_width() * ok_scale), int(original.get_height() * ok_scale))
    return pygame.transform.smoothscale(original, size).convert_alpha(), size
