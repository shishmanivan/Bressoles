"""Native fullscreen and movable, decorated desktop windows."""
import sys

import pygame


LOGICAL_SCREEN_SIZE = (1680, 1050)
MIN_WINDOW_SIZE = (1280, 800)
ADAPTIVE_DISPLAY_FLAGS = pygame.RESIZABLE | pygame.DOUBLEBUF
FALLBACK_DISPLAY_FLAGS = pygame.HWSURFACE | pygame.DOUBLEBUF

# pygame 2.6 stores a borrowed Window pointer in SDL's event data without
# retaining it. Keep the wrapper alive while SDL can attach it to events.
_display_window = None


def _borrow_display_window():
    global _display_window
    from pygame._sdl2.video import Window

    _display_window = Window.from_display_module()
    return _display_window


def _windows_geometry():
    """Read the current monitor's work area (excluding its taskbar)."""
    if sys.platform != 'win32' or pygame.display.get_driver() == 'dummy':
        return None
    import ctypes
    from ctypes import wintypes

    class MonitorInfo(ctypes.Structure):
        _fields_ = [('size', wintypes.DWORD), ('monitor', wintypes.RECT),
                    ('work', wintypes.RECT), ('flags', wintypes.DWORD)]

    user32 = ctypes.WinDLL('user32', use_last_error=True)
    user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
    user32.MonitorFromWindow.restype = wintypes.HANDLE
    user32.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MonitorInfo)]
    user32.GetMonitorInfoW.restype = wintypes.BOOL
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.GetWindowRect.restype = wintypes.BOOL
    hwnd = pygame.display.get_wm_info().get('window', 0)
    monitor = user32.MonitorFromWindow(hwnd, 2)  # nearest monitor, primary before creation
    info = MonitorInfo()
    info.size = ctypes.sizeof(info)
    if not user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
        return None
    rect = info.work
    work = (rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top)
    outer = wintypes.RECT()
    outer_size = None
    outer_position = None
    if hwnd and user32.GetWindowRect(hwnd, ctypes.byref(outer)):
        outer_size = (outer.right - outer.left, outer.bottom - outer.top)
        outer_position = (outer.left, outer.top)
    return work, outer_size, outer_position


def _set_minimum_window_size():
    """Let SDL/Windows reject undersized resize requests before rendering."""
    if sys.platform != 'win32' or pygame.display.get_driver() == 'dummy':
        return
    import ctypes
    from pathlib import Path

    # Use the same SDL library as pygame; pygame 2.6 exposes no min-size setter.
    sdl = ctypes.CDLL(str(Path(pygame.__file__).parent / 'SDL2.dll'))
    sdl.SDL_GetWindowFromID.argtypes = [ctypes.c_uint32]
    sdl.SDL_GetWindowFromID.restype = ctypes.c_void_p
    sdl.SDL_SetWindowMinimumSize.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
    sdl.SDL_SetWindowMinimumSize.restype = None
    window = sdl.SDL_GetWindowFromID(_borrow_display_window().id)
    if not window:
        raise pygame.error('Could not find the game window for minimum size')
    sdl.SDL_SetWindowMinimumSize(window, *MIN_WINDOW_SIZE)


def fit_window_size(requested_size, work_area):
    """Leave desktop space around the window, including its title bar."""
    width, height = (max(MIN_WINDOW_SIZE[i], int(value))
                     for i, value in enumerate(requested_size))
    if work_area is None:
        return width, height
    _, _, available_width, available_height = work_area
    scale = min(1.0, available_width * .9 / width,
                max(1, available_height * .9 - 48) / height)
    return max(MIN_WINDOW_SIZE[0], int(width * scale)), max(MIN_WINDOW_SIZE[1], int(height * scale))


def create_game_display(logical_size=LOGICAL_SCREEN_SIZE):
    """Create a normal, centered window that fits inside the monitor work area."""
    logical_size = tuple(int(value) for value in logical_size)
    geometry = _windows_geometry()
    work = geometry[0] if geometry else None
    window_size = fit_window_size(logical_size, work)
    try:
        screen = pygame.display.set_mode(window_size, ADAPTIVE_DISPLAY_FLAGS)
    except pygame.error as error:
        print(f"WARNING: Adaptive display unavailable, using fixed window: {error}")
        screen = pygame.display.set_mode(window_size, FALLBACK_DISPLAY_FLAGS)
    _set_minimum_window_size()
    if work is not None:
        window = _borrow_display_window()
        # SDL can retain maximization/position when leaving fullscreen.
        window.restore()
        window.borderless = False
        window.resizable = True
        window.size = window_size
        geometry = _windows_geometry()
        outer = geometry[1] if geometry and geometry[1] else window_size
        x, y, width, height = work
        target = (x + max(0, (width - outer[0]) // 2),
                  y + max(0, (height - outer[1]) // 2))
        window.position = target
        # SDL and Windows can use different origins for decorated windows.
        actual = _windows_geometry()
        if actual and actual[2]:
            position = window.position
            window.position = (position[0] + target[0] - actual[2][0],
                               position[1] + target[1] - actual[2][1])
    return screen


def apply_display_settings(settings):
    if settings["fullscreen"]:
        screen = pygame.display.set_mode(settings["resolution"], pygame.FULLSCREEN | pygame.DOUBLEBUF)
        if sys.platform == 'win32' and pygame.display.get_driver() != 'dummy':
            _borrow_display_window()
        return screen
    return create_game_display(settings["resolution"])
