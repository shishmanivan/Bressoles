import pygame


LOGICAL_SCREEN_SIZE = (1680, 1050)
ADAPTIVE_DISPLAY_FLAGS = pygame.RESIZABLE | pygame.DOUBLEBUF
FALLBACK_DISPLAY_FLAGS = pygame.HWSURFACE | pygame.DOUBLEBUF


def create_game_display(logical_size=LOGICAL_SCREEN_SIZE):
    """Create a resizable display whose surface follows the actual viewport."""
    logical_size = tuple(int(value) for value in logical_size)
    try:
        return pygame.display.set_mode(logical_size, ADAPTIVE_DISPLAY_FLAGS)
    except pygame.error as error:
        print(f"WARNING: Adaptive display unavailable, using fixed window: {error}")
        return pygame.display.set_mode(logical_size, FALLBACK_DISPLAY_FLAGS)
