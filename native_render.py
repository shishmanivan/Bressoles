"""Resolution-independent artwork and native-pixel UI drawing.

Pages retain design coordinates for layout and input. Canvas translates draw
operations, not a completed framebuffer. Surface recipes retain original image
pixels and font descriptions through intermediate sizes and composite widgets.
This is a scoped pygame facade; the pygame module itself is never patched.
"""
from collections import OrderedDict
import pygame as _pg


def __getattr__(name):
    return getattr(_pg, name)


_cache = OrderedDict()
_cache_bytes = 0
_CACHE_LIMIT = 64 * 1024 * 1024


class Recipe:
    def __init__(self, size, kind, data):
        self.size, self.kind, self.data = tuple(size), kind, data


def _snapshot(surface):
    if isinstance(surface, Surface):
        return surface.recipe()
    return Recipe(surface.get_size(), 'pixels', _pg.Surface.copy(surface))


def _point(point, sx, sy):
    return round(point[0] * sx), round(point[1] * sy)


def _rect(rect, sx, sy):
    rect = _pg.Rect(rect)
    x, y = _point(rect.topleft, sx, sy)
    right, bottom = _point(rect.bottomright, sx, sy)
    return _pg.Rect(x, y, right - x, bottom - y)


def _draw_scaled(name, target, args, kwargs, sx, sy):
    args, kwargs = list(args), dict(kwargs)
    scale = min(sx, sy)
    def length(value):
        return max(1, round(value * scale)) if value > 0 else value
    if name in ('rect', 'ellipse'):
        args[1] = _rect(args[1], sx, sy)
        for i in range(2, len(args)):
            args[i] = length(args[i])
        for key in tuple(kwargs):
            if key == 'width' or key.startswith('border'):
                kwargs[key] = length(kwargs[key])
    elif name == 'line':
        args[1], args[2] = _point(args[1], sx, sy), _point(args[2], sx, sy)
        if len(args) > 3:
            args[3] = length(args[3])
    elif name in ('lines', 'polygon'):
        index = 2 if name == 'lines' else 1
        args[index] = [_point(p, sx, sy) for p in args[index]]
        if len(args) > index + 1:
            args[index + 1] = length(args[index + 1])
    elif name == 'circle':
        args[1] = _point(args[1], sx, sy)
        args[2] = length(args[2])
        if len(args) > 3:
            args[3] = length(args[3])
    if 'width' in kwargs:
        kwargs['width'] = length(kwargs['width']) if name not in ('rect', 'ellipse') else kwargs['width']
    return getattr(_pg.draw, name)(target, *args, **kwargs)


def _font_at(path, size, styles):
    font = _pg.font.Font(path, size)
    for name, value in styles:
        getattr(font, 'set_' + name)(value)
    return font


def render(recipe, size):
    global _cache_bytes
    size = tuple(max(1, round(v)) for v in size)
    key = (recipe, size)
    cached = _cache.get(key)
    if cached is not None:
        _cache.move_to_end(key)
        return cached
    sx, sy = size[0] / max(1, recipe.size[0]), size[1] / max(1, recipe.size[1])
    kind, data = recipe.kind, recipe.data
    if kind == 'pixels':
        result = data.copy() if data.get_size() == size else _pg.transform.smoothscale(data, size)
    elif kind == 'scale':
        result = render(data, size)
    elif kind == 'font':
        path, point_size, styles, text, antialias, color, background = data
        # Keep native glyph rasterization. Never resample rendered letters to
        # compensate for font-hinting differences in their final dimensions.
        result = _font_at(path, max(1, round(point_size * sy)), styles).render(
            text, antialias, color, background)
    elif kind == 'crop':
        source, crop = data
        # Crop original pixels before resampling (including scaled frame tiles).
        while source.kind == 'scale':
            parent = source.data
            crop = _rect(crop, parent.size[0] / source.size[0], parent.size[1] / source.size[1])
            source = parent
        if source.kind == 'pixels':
            pixels = source.data.subsurface(crop.clip(source.data.get_rect()))
            result = _pg.transform.smoothscale(pixels, size)
        else:
            # Composite/cropped labels also retain native font rasterization.
            crop_sx, crop_sy = size[0] / max(1, crop.width), size[1] / max(1, crop.height)
            pixels = render(source, (source.size[0] * crop_sx, source.size[1] * crop_sy))
            result = pixels.subsurface(_rect(crop, crop_sx, crop_sy).clip(pixels.get_rect())).copy()
    elif kind == 'rotate':
        source, angle = data
        result = _pg.transform.rotate(render(source, (source.size[0] * sx, source.size[1] * sy)), angle)
    elif kind == 'state':
        source, alpha, colorkey = data
        result = render(source, size).copy()
        result.set_alpha(alpha)
        result.set_colorkey(colorkey)
    elif kind == 'composite':
        base, operations, flags = data
        result = render(base, size).copy() if base else _pg.Surface(size, flags)
        for operation in operations:
            name, values, clip = operation
            result.set_clip(_rect(clip, sx, sy))
            if name == 'fill':
                color, rect, special = values
                result.fill(color, _rect(rect, sx, sy), special)
            elif name == 'blit':
                source, position, area, special = values
                source_size = _rect(_pg.Rect(position, source.size), sx, sy).size
                pixels = render(source, source_size)
                result.blit(pixels, _point(position, sx, sy),
                            _rect(area, sx, sy) if area is not None else None, special)
            else:
                args, kwargs = values
                _draw_scaled(name, result, args, kwargs, sx, sy)
        result.set_clip(None)
    else:
        raise ValueError(kind)
    # Shared cache is bounded by bytes and count, including temporary text.
    cost = result.get_pitch() * result.get_height()
    if cost <= _CACHE_LIMIT:
        _cache[key] = result
        _cache_bytes += cost
        while _cache_bytes > _CACHE_LIMIT or len(_cache) > 512:
            _, old = _cache.popitem(last=False)
            _cache_bytes -= old.get_pitch() * old.get_height()
    return result


class Surface(_pg.Surface):
    """Ordinary logical-size Surface retaining a replayable artwork recipe."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._base = None
        self._operations = []
        self._recipe = None

    @classmethod
    def wrap(cls, pixels, recipe=None):
        if isinstance(pixels, cls):
            result = pixels
        else:
            result = cls(pixels.get_size(), pixels.get_flags() & _pg.SRCALPHA)
            _pg.Surface.blit(result, pixels, (0, 0))
        result._base = recipe or Recipe(pixels.get_size(), 'pixels', pixels)
        result._operations = []
        result._recipe = None
        return result

    def recipe(self):
        if self._recipe is None:
            base = self._base
            if self._operations or base is None:
                base = Recipe(self.get_size(), 'composite',
                              (base, tuple(self._operations), self.get_flags() & _pg.SRCALPHA))
            self._recipe = Recipe(self.get_size(), 'state', (base, self.get_alpha(), self.get_colorkey())) if self.get_alpha() != 255 or self.get_colorkey() else base
        return self._recipe

    def record(self, name, values):
        self._operations.append((name, values, self.get_clip().copy()))
        self._recipe = None

    def fill(self, color, rect=None, special_flags=0):
        result = super().fill(color, rect, special_flags)
        if rect is None and special_flags == 0 and self.get_clip() == self.get_rect():
            self._base, self._operations = None, []
        self.record('fill', (color, _pg.Rect(rect) if rect is not None else self.get_rect(), special_flags))
        return result

    def blit(self, source, dest, area=None, special_flags=0):
        result = super().blit(source, dest, area, special_flags)
        position = dest.topleft if hasattr(dest, 'topleft') else tuple(dest[:2])
        self.record('blit', (_snapshot(source), position, _pg.Rect(area) if area is not None else None, special_flags))
        return result

    def copy(self):
        result = Surface.wrap(_pg.Surface.copy(self), self.recipe())
        _pg.Surface.set_alpha(result, self.get_alpha())
        return result

    def convert_alpha(self, *args):
        return Surface.wrap(_pg.Surface.convert_alpha(self, *args), self.recipe())

    def convert(self, *args):
        return Surface.wrap(_pg.Surface.convert(self, *args), self.recipe())

    def subsurface(self, *args):
        crop = _pg.Rect(*args)
        return Surface.wrap(_pg.Surface.copy(_pg.Surface.subsurface(self, crop)), Recipe(crop.size, 'crop', (self.recipe(), crop)))

    def set_alpha(self, value, flags=0):
        super().set_alpha(value, flags)
        self._recipe = None

    def set_colorkey(self, value=None, flags=0):
        super().set_colorkey(value, flags)
        self._recipe = None


class Canvas(_pg.Surface):
    """Design-coordinate API backed by a framebuffer at final pixel size."""
    def __init__(self, logical_size):
        super().__init__(logical_size, _pg.SRCALPHA)
        self.modal_layers = []
        self.configure(logical_size)

    def configure(self, size):
        if not hasattr(self, 'pixels') or self.pixels.get_size() != tuple(size):
            self.pixels = _pg.Surface(size, _pg.SRCALPHA)
        self.sx, self.sy = size[0] / self.get_width(), size[1] / self.get_height()
        self.set_clip(None)

    def fill(self, color, rect=None, special_flags=0):
        logical = self.get_rect() if rect is None else _pg.Rect(rect)
        self.pixels.fill(color, _rect(logical, self.sx, self.sy), special_flags)
        return logical.clip(self.get_clip())

    def blit(self, source, dest, area=None, special_flags=0):
        position = dest.topleft if hasattr(dest, 'topleft') else tuple(dest[:2])
        target = _rect(_pg.Rect(position, source.get_size()), self.sx, self.sy)
        pixels = render(_snapshot(source), target.size)
        self.pixels.blit(pixels, _point(position, self.sx, self.sy),
                         _rect(area, self.sx, self.sy) if area is not None else None, special_flags)
        return _pg.Rect(position, _pg.Rect(area).size if area is not None else source.get_size()).clip(self.get_clip())

    def set_clip(self, rect=None):
        super().set_clip(rect)
        self.pixels.set_clip(_rect(self.get_clip(), self.sx, self.sy))

    def get_at(self, position):
        return self.pixels.get_at(_point(position, self.sx, self.sy))


class Font(_pg.font.Font):
    def __init__(self, path, size):
        super().__init__(path, size)
        self.path, self.point_size = path, size
        self._renders = OrderedDict()

    def render(self, text, antialias, color, background=None):
        styles = tuple((name, getattr(self, 'get_' + name)())
                       for name in ('bold', 'italic', 'underline', 'strikethrough'))
        key = (text, antialias, tuple(_pg.Color(color)),
               tuple(_pg.Color(background)) if background is not None else None, styles)
        result = self._renders.get(key)
        if result is None:
            pixels = super().render(text, antialias, color, background)
            result = Surface.wrap(pixels, Recipe(pixels.get_size(), 'font',
                                  (self.path, self.point_size, styles, text, antialias, color, background)))
            self._renders[key] = result
            if len(self._renders) > 64:
                self._renders.popitem(last=False)
        return result.copy()


class Proxy:
    def __init__(self, module, **overrides):
        self.module, self.overrides = module, overrides

    def __getattr__(self, name):
        return self.overrides.get(name, getattr(self.module, name))


def _load(*args, **kwargs):
    return Surface.wrap(_pg.image.load(*args, **kwargs))


def _smoothscale(source, size, dest_surface=None):
    pixels = (_pg.transform.smoothscale(source, size) if dest_surface is None
              else _pg.transform.smoothscale(source, size, dest_surface))
    if dest_surface is not None:
        return pixels
    recipe = _snapshot(source)
    while recipe.kind == 'scale':
        recipe = recipe.data
    return Surface.wrap(pixels, Recipe(size, 'scale', recipe))


def _rotate(source, angle):
    pixels = _pg.transform.rotate(source, angle)
    return Surface.wrap(pixels, Recipe(pixels.get_size(), 'rotate', (_snapshot(source), angle)))


def _drawing(name):
    def draw(target, *args, **kwargs):
        if isinstance(target, Canvas):
            result = _draw_scaled(name, target.pixels, args, kwargs, target.sx, target.sy)
            return _rect(result, 1 / target.sx, 1 / target.sy)
        result = getattr(_pg.draw, name)(target, *args, **kwargs)
        if isinstance(target, Surface):
            target.record(name, (args, kwargs))
        return result
    return draw


draw = Proxy(_pg.draw, **{name: _drawing(name) for name in ('rect', 'line', 'lines', 'polygon', 'circle', 'ellipse')})
image = Proxy(_pg.image, load=_load)
transform = Proxy(_pg.transform, smoothscale=_smoothscale, rotate=_rotate)
font = Proxy(_pg.font, Font=Font)
