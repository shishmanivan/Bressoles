"""Build Bressoles Display from original vector drawings (no source font).

Build-only dependencies: fonttools==4.66.1, skia-pathops==0.9.2, brotli==1.2.0.
Run from any directory; outputs go to Fonts/. Lowercase uses drawn small capitals,
as in the menu reference. This is a display face, intended for headings/menus.
"""

from pathlib import Path
from datetime import datetime, timezone
import math
import unicodedata

import pathops
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.recordingPen import RecordingPen
from fontTools.misc.bezierTools import splitCubicAtT
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.svgLib.path import parse_path
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.ttLib import TTFont, newTable

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "Fonts"
UPM = 1000
CAP = 700
GLYPHS = {}


def soften_corners(path, outer_radius=11, inner_radius=25):
    """Replace tangent discontinuities with fillets; retain existing curves.

    Work on united outlines, so intersections receive the same treatment as
    serif tips. Each cut is limited to 44% of either adjacent segment, keeping
    thin serifs and accent strokes intact. Smooth extrema remain untouched.
    Pathops supplies counterclockwise outer contours: negative turns are
    concave ink corners and get the more generous bracket radius.
    """
    recording = RecordingPen()
    path.draw(recording)
    contours, segments = [], []
    current = start = None
    for operation, points in recording.value:
        if operation == "moveTo":
            current = start = points[0]
            segments = []
        elif operation in ("lineTo", "curveTo", "qCurveTo"):
            segment = (current, *points)
            if operation == "qCurveTo":
                a, b, c = segment
                segment = (a, tuple(a[j] + 2*(b[j]-a[j])/3 for j in (0, 1)),
                           tuple(c[j] + 2*(b[j]-c[j])/3 for j in (0, 1)), c)
            if any(math.dist(segment[0], p) > .001 for p in segment[1:]):
                segments.append(segment)
            current = points[-1]
        elif operation == "closePath":
            if math.dist(current, start) > .001:
                segments.append((current, start))
            if segments:
                contours.append(segments)

    def point(segment, t):
        work = list(segment)
        while len(work) > 1:
            work = [tuple((1-t)*a[j] + t*b[j] for j in (0, 1))
                    for a, b in zip(work, work[1:])]
        return work[0]

    def tangent(segment, at_end):
        ordered = list(reversed(segment)) if at_end else segment
        for p in ordered[1:]:
            delta = tuple(p[j] - ordered[0][j] for j in (0, 1))
            length = math.hypot(*delta)
            if length > .001:
                sign = -1 if at_end else 1
                return tuple(sign*v/length for v in delta)
        raise ValueError("Degenerate outline segment")

    def samples(segment):
        count = 1 if len(segment) == 2 else 32
        points = [point(segment, i/count) for i in range(count+1)]
        lengths = [0.0]
        for a, b in zip(points, points[1:]):
            lengths.append(lengths[-1] + math.dist(a, b))
        return lengths

    def parameter(lengths, distance):
        for i in range(1, len(lengths)):
            if lengths[i] >= distance:
                interval = lengths[i] - lengths[i-1]
                return (i-1 + (distance-lengths[i-1])/interval)/(len(lengths)-1)
        return 1.0

    result = pathops.Path()
    pen = result.getPen()
    for segments in contours:
        lengths = [samples(s) for s in segments]
        trims, handles = [], []
        for i, segment in enumerate(segments):
            a, b = tangent(segments[i-1], True), tangent(segment, False)
            turn = math.atan2(a[0]*b[1] - a[1]*b[0], a[0]*b[0] + a[1]*b[1])
            angle = abs(turn)
            if angle < .06:
                trims.append(0)
                handles.append(0)
                continue
            radius = outer_radius if turn > 0 else inner_radius
            ratio = math.tan(min(angle, math.pi-.001)/2)
            trim = min(radius*ratio, lengths[i-1][-1]*.44, lengths[i][-1]*.44)
            trims.append(trim)
            handles.append(trim * (4/3) * math.tan(angle/4) / ratio)
        clipped = []
        for i, segment in enumerate(segments):
            t0 = parameter(lengths[i], trims[i])
            t1 = parameter(lengths[i], lengths[i][-1] - trims[(i+1) % len(segments)])
            if len(segment) == 2:
                clipped.append((point(segment, t0), point(segment, t1)))
            else:
                # Keep the middle section of the exact original Bezier.
                clipped.append(splitCubicAtT(*segment, t0, t1)[1])
        pen.moveTo(clipped[0][0])
        for i, segment in enumerate(clipped):
            if len(segment) == 2:
                pen.lineTo(segment[-1])
            else:
                pen.curveTo(*segment[1:])
            next_i = (i+1) % len(clipped)
            next_segment = clipped[next_i]
            if trims[next_i] > 0:
                a, b = tangent(segment, True), tangent(next_segment, False)
                handle = handles[next_i]
                pen.curveTo(tuple(segment[-1][j] + handle*a[j] for j in (0, 1)),
                            tuple(next_segment[0][j] - handle*b[j] for j in (0, 1)),
                            next_segment[0])
        pen.closePath()
    return pathops.simplify(result)


def svg(commands):
    p = pathops.Path()
    parse_path(commands, p.getPen())
    return p


def polygon(*points):
    p = pathops.Path()
    pen = p.getPen()
    pen.moveTo(points[0])
    for point in points[1:]:
        pen.lineTo(point)
    pen.closePath()
    return p


def box(x0, y0, x1, y1):
    return polygon((x0, y0), (x1, y0), (x1, y1), (x0, y1))


def ellipse(x0, y0, x1, y1):
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    rx, ry = (x1 - x0) / 2, (y1 - y0) / 2
    k = 0.55228475
    return svg(f"M {cx} {y0} C {cx+k*rx} {y0} {x1} {cy-k*ry} {x1} {cy} "
               f"C {x1} {cy+k*ry} {cx+k*rx} {y1} {cx} {y1} "
               f"C {cx-k*rx} {y1} {x0} {cy+k*ry} {x0} {cy} "
               f"C {x0} {cy-k*ry} {cx-k*rx} {y0} {cx} {y0} Z")


def join(*parts):
    p = pathops.Path()
    for part in parts:
        p = pathops.op(p, part, pathops.PathOp.UNION)
    return p


def cut(outer, inner):
    return pathops.op(outer, inner, pathops.PathOp.DIFFERENCE)


def transform(p, sx=1, sy=1, dx=0, dy=0):
    out = pathops.Path()
    p.draw(TransformPen(out.getPen(), (sx, 0, 0, sy, dx, dy)))
    return out


def stem(x, width=108, bottom=0, top=CAP, serif=43):
    # Curved brackets connect the main stroke to fine, slightly cupped serifs.
    a, b, s = x, x + width, serif
    return svg(f"M {a-s} {bottom} L {b+s} {bottom} L {b+s} {bottom+22} "
               f"C {b+9} {bottom+24} {b} {bottom+34} {b} {bottom+76} "
               f"L {b} {top-76} C {b} {top-34} {b+9} {top-24} {b+s} {top-22} "
               f"L {b+s} {top} L {a-s} {top} L {a-s} {top-22} "
               f"C {a-9} {top-24} {a} {top-34} {a} {top-76} "
               f"L {a} {bottom+76} C {a} {bottom+34} {a-9} {bottom+24} {a-s} {bottom+22} Z")


def stroke(x0, y0, x1, y1, width):
    length = math.hypot(x1-x0, y1-y0)
    nx, ny = -(y1-y0)*width/(2*length), (x1-x0)*width/(2*length)
    return polygon((x0+nx, y0+ny), (x1+nx, y1+ny),
                   (x1-nx, y1-ny), (x0-nx, y0-ny))


def foot(cx, width=145, y=0):
    return svg(f"M {cx-width/2} {y} L {cx+width/2} {y} L {cx+width/2} {y+23} "
               f"C {cx+24} {y+26} {cx+19} {y+33} {cx+13} {y+53} "
               f"L {cx-13} {y+53} C {cx-19} {y+33} {cx-24} {y+26} {cx-width/2} {y+23} Z")


def head(cx, width=145, y=700):
    return transform(foot(cx, width), sy=-1, dy=y)


def oval(width=550):
    return cut(ellipse(32, -12, width-32, 712),
               ellipse(148, 27, width-148, 673))


def bar_right(y, end=452, tall=30, flare=155, upside=False):
    # Tapered, concave beak on the free end of E/F/L/T arms.
    p = svg(f"M 105 {y} L {end} {y} L {end+7} {y+flare} L {end-20} {y+flare} "
            f"C {end-38} {y+48} {end-72} {y+tall} {end-139} {y+tall} L 105 {y+tall} Z")
    return transform(p, sy=-1, dy=700) if upside else p


def bowl(bottom, top, end, start=131, heavy=104):
    mid = (bottom + top) / 2
    p = svg(f"M {start} {bottom} L {end-155} {bottom} "
            f"C {end-42} {bottom} {end} {bottom+58} {end} {mid} "
            f"C {end} {top-53} {end-48} {top} {end-162} {top} L {start} {top} Z")
    hole = svg(f"M {start+38} {bottom+34} L {end-169} {bottom+34} "
               f"C {end-heavy-8} {bottom+34} {end-heavy} {bottom+83} {end-heavy} {mid} "
               f"C {end-heavy} {top-80} {end-heavy-10} {top-34} {end-174} {top-34} "
               f"L {start+38} {top-34} Z")
    return cut(p, hole)


def register(char, path, advance):
    GLYPHS[char] = (pathops.simplify(path), advance)


def latin():
    # Continuous diagonal silhouettes avoid the projecting butt ends that
    # occurred when separate rectangular strokes were united at the apex.
    a = svg("M 9 0 L 148 0 L 148 22 C 102 26 93 37 109 91 L 153 239 "
            "L 360 239 L 406 78 C 417 38 403 27 359 22 L 359 0 L 531 0 "
            "L 531 22 C 495 27 482 44 467 92 L 286 697 "
            "C 282 713 264 716 260 700 L 65 101 C 50 39 42 27 9 22 Z")
    a = cut(a, svg("M 164 273 L 260 595 C 262 602 266 602 268 595 L 350 273 Z"))
    register("A", a, 540)
    register("B", join(stem(67), bowl(0, 358, 472), bowl(335, 700, 446)), 520)
    c = svg("M 471 695 L 471 505 L 442 505 C 427 617 382 674 285 674 "
            "C 183 674 149 554 149 350 C 149 134 192 26 292 26 "
            "C 371 26 422 74 460 162 L 488 151 C 449 34 382 -12 275 -12 "
            "C 108 -12 31 138 31 349 C 31 565 122 712 280 712 "
            "C 344 712 393 694 429 671 L 449 695 Z")
    register("C", c, 535)
    d = cut(svg("M 117 0 L 271 0 C 449 0 516 129 516 349 "
                "C 516 572 445 700 269 700 L 117 700 Z"),
            svg("M 174 34 L 254 34 C 365 34 398 136 398 351 "
                "C 398 566 363 666 249 666 L 174 666 Z"))
    register("D", join(stem(67), d), 563)
    e_middle = svg("M 133 330 L 273 330 C 326 330 342 310 350 244 L 377 244 "
                   "L 377 454 L 350 454 C 342 386 326 365 273 365 L 133 365 Z")
    register("E", join(stem(67), bar_right(0), bar_right(0, upside=True), e_middle), 506)
    register("F", join(stem(67), bar_right(0, upside=True), e_middle), 490)
    register("G", join(c, box(305, 295, 507, 329),
                       box(393, 81, 487, 304),
                       svg("M 393 81 C 425 75 463 108 487 151 L 487 63 "
                           "C 457 40 417 20 371 10 L 360 37 C 383 42 393 57 393 81 Z")), 558)
    register("H", join(stem(67), stem(397), box(144, 332, 435, 367)), 572)
    register("I", stem(68, 108, serif=47), 244)
    j = svg("M 255 700 L 449 700 L 449 677 C 408 674 402 661 402 622 "
            "L 402 175 C 402 41 331 -13 232 -13 C 117 -13 58 44 58 112 "
            "C 58 159 87 181 117 181 C 149 181 169 159 169 129 "
            "C 169 92 138 81 129 61 C 153 33 179 23 213 23 "
            "C 275 23 293 67 293 167 L 293 622 C 293 661 286 674 255 677 Z")
    register("J", j, 480)
    k_arm = join(stroke(175, 338, 414, 661, 38), head(417, 151),
                 svg("M 256 459 C 321 356 365 231 440 74 "
                     "C 459 36 475 28 515 22 L 515 0 L 307 0 L 307 22 "
                     "C 343 24 352 34 337 68 L 190 361 Z"))
    register("K", join(stem(67), k_arm), 555)
    register("L", join(stem(67), bar_right(0, end=440, flare=188)), 494)
    register("M", join(stem(67, 34), stem(514, 105),
                       svg("M 86 700 L 185 700 L 343 270 L 500 700 L 537 700 "
                           "L 336 94 C 332 80 318 80 314 94 Z")), 684)
    register("N", join(stem(67, 34), stem(426, 34),
                       svg("M 78 700 L 171 700 L 426 187 L 460 104 L 460 0 "
                           "L 427 0 C 415 0 408 10 401 24 L 101 586 L 78 630 Z")), 530)
    register("O", oval(), 550)
    register("P", join(stem(67), bowl(318, 700, 466)), 509)
    q_tail = svg("M 273 139 C 335 89 359 18 413 -33 C 441 -60 467 -63 505 -39 "
                 "L 519 -62 C 453 -117 397 -102 357 -51 C 325 -11 300 61 257 115 Z")
    register("Q", join(oval(), q_tail), 559)
    r_leg = svg("M 240 356 C 333 349 355 297 388 192 L 424 84 "
                "C 439 39 453 26 494 31 L 501 8 C 391 -25 350 13 325 111 "
                "L 286 260 C 274 306 250 321 170 320 L 170 356 Z")
    register("R", join(stem(67), bowl(321, 700, 458), r_leg), 541)
    s = svg("M 444 695 L 444 510 L 415 510 C 397 620 356 674 277 674 "
            "C 197 674 164 629 164 573 C 164 495 223 468 306 427 "
            "C 416 373 483 319 483 207 C 483 66 390 -12 272 -12 "
            "C 197 -12 142 11 93 43 L 74 12 L 49 12 L 49 225 L 79 225 "
            "C 102 92 158 26 253 26 C 335 26 374 73 374 140 "
            "C 374 219 313 250 223 296 C 112 351 57 403 57 509 "
            "C 57 633 148 712 268 712 C 329 712 377 690 407 669 L 424 695 Z")
    register("S", s, 530)
    t_arm = svg("M 31 700 L 502 700 L 510 501 L 482 501 "
                "C 465 633 439 666 359 666 L 321 666 L 321 635 L 212 635 "
                "L 212 666 L 174 666 C 94 666 68 633 51 501 L 23 501 Z")
    register("T", join(stem(212, 109), t_arm), 535)
    u = svg("M 23 700 L 226 700 L 226 677 C 183 674 177 661 177 622 "
            "L 177 181 C 177 73 224 30 295 30 C 378 30 424 88 424 195 "
            "L 424 613 C 424 657 414 674 368 677 L 368 700 L 516 700 "
            "L 516 677 C 470 674 460 657 460 613 L 460 202 "
            "C 460 53 396 -12 270 -12 C 151 -12 67 44 67 183 "
            "L 67 622 C 67 661 60 674 23 677 Z")
    register("U", u, 541)
    register("V", join(svg("M 61 700 L 166 700 L 302 188 L 456 700 L 494 700 "
                           "L 287 7 C 282 -10 259 -10 254 10 Z"),
                       head(99, 176), head(473, 135)), 548)
    register("W", join(svg("M 44 700 L 141 700 L 278 188 L 370 581 L 338 700 "
                           "L 442 700 L 560 190 L 668 700 L 705 700 L 548 9 "
                           "C 544 -8 522 -8 517 9 L 389 531 L 253 9 "
                           "C 248 -8 222 -8 217 9 Z"),
                       head(83, 159), head(390, 155), head(672, 129)), 746)
    register("X", join(stroke(105, 657, 448, 41, 96),
                       stroke(105, 40, 443, 661, 36),
                       head(102, 161), head(448, 133), foot(104, 133), foot(448, 171)), 548)
    register("Y", join(svg("M 50 700 L 158 700 L 291 429 L 439 700 L 480 700 "
                           "L 326 371 L 323 326 L 218 326 L 218 359 Z"),
                       cut(stem(218, 105), box(0, 340, 600, 710)),
                       head(96, 163), head(447, 136)), 521)
    z = svg("M 51 700 L 468 700 L 468 673 L 175 35 L 310 35 "
            "C 392 35 430 64 453 189 L 481 189 L 470 0 L 35 0 L 35 29 "
            "L 329 665 L 206 665 C 126 665 92 635 72 524 L 45 524 Z")
    register("Z", z, 515)


def cyrillic():
    for c, latin_c in {"А":"A", "В":"B", "Е":"E", "К":"K", "М":"M", "Н":"H",
                       "О":"O", "Р":"P", "С":"C", "Т":"T", "Х":"X"}.items():
        GLYPHS[c] = GLYPHS[latin_c]
    register("Б", join(stem(67), bowl(0, 384, 473),
                       bar_right(0, end=434, flare=144, upside=True)), 520)
    register("Г", join(stem(67), bar_right(0, end=426, flare=189, upside=True)), 477)
    # Д / Л use the same inclined left support and generous counters.
    support = join(stroke(130, 45, 275, 663, 37), stem(395, 108),
                   box(255, 665, 476, 700), foot(131, 141))
    d_base = svg("M 52 34 L 527 34 L 536 -124 L 506 -124 "
                 "C 495 -25 474 0 415 0 L 163 0 C 103 0 83 -25 72 -124 L 42 -124 Z")
    register("Д", join(support, d_base), 585)
    register("Л", join(support,
                       svg("M 145 78 C 131 -4 72 -19 29 14 L 42 42 "
                           "C 75 20 99 47 116 111 Z")), 571)
    # Free arms meet the central stem directly, without extra mirrored stems.
    arm = join(stroke(445, 338, 684, 661, 38), head(687, 151),
               svg("M 526 459 C 591 356 635 231 710 74 "
                   "C 729 36 745 28 785 22 L 785 0 L 577 0 L 577 22 "
                   "C 613 24 622 34 607 68 L 460 361 Z"))
    register("Ж", join(stem(337, 108), arm,
                       transform(arm, sx=-1, dx=782)), 790)
    z = svg("M 426 695 L 426 523 L 399 523 C 380 625 341 674 266 674 "
            "C 209 674 169 643 151 608 L 125 621 C 151 678 203 712 278 712 "
            "C 392 712 468 642 468 535 C 468 445 415 383 330 360 "
            "C 429 343 486 278 486 180 C 486 61 398 -12 269 -12 "
            "C 146 -12 59 52 42 157 L 74 163 C 102 74 151 27 236 27 "
            "C 325 27 374 79 374 181 C 374 286 327 338 245 338 "
            "L 188 338 L 188 373 L 245 373 C 314 373 358 421 358 521 "
            "C 358 623 322 675 263 675 L 403 695 Z")
    register("З", z, 530)
    register("И", join(stem(67), stem(397), stroke(168, 68, 405, 633, 43)), 572)
    register("П", join(stem(67), stem(397), box(138, 666, 437, 700)), 572)
    register("У", join(stroke(111, 662, 314, 269, 100),
                       stroke(145, -3, 461, 665, 37),
                       head(104, 170), head(463, 136),
                       svg("M 207 96 C 169 -7 111 -23 58 5 L 71 40 "
                           "C 104 22 134 51 147 98 C 157 134 187 127 207 96 Z")), 528)
    register("Ф", join(transform(oval(655), sy=.73, dy=97),
                       stem(277, 105, bottom=-5, top=705)), 660)
    register("Ц", join(stem(67), stem(397), box(137, 0, 514, 34),
                       svg("M 450 34 L 548 34 L 548 -124 L 519 -124 "
                           "C 512 -28 494 0 450 0 Z")), 592)
    register("Ч", join(stem(397),
                       svg("M 24 700 L 218 700 L 218 677 C 182 674 176 661 176 622 "
                           "L 176 426 C 176 345 212 316 274 316 C 320 316 370 331 414 365 "
                           "L 429 331 C 362 274 301 259 230 259 C 121 259 67 312 67 427 "
                           "L 67 622 C 67 661 60 674 24 677 Z")), 570)
    register("Ш", join(stem(67), stem(347), stem(627), box(140, 0, 685, 34)), 802)
    register("Щ", join(GLYPHS["Ш"][0],
                       svg("M 682 34 L 779 34 L 788 -124 L 757 -124 "
                           "C 750 -28 731 0 682 0 Z")), 825)
    register("Ь", join(stem(67), bowl(0, 371, 468)), 515)
    register("Ы", join(GLYPHS["Ь"][0], stem(547)), 722)
    register("Ъ", join(transform(GLYPHS["Ь"][0], dx=89),
                       svg("M 29 700 L 209 700 L 209 666 L 143 666 "
                           "C 93 666 74 629 57 514 L 29 514 Z")), 605)
    register("Э", join(transform(GLYPHS["C"][0], sx=-1, dx=535),
                       box(147, 334, 421, 370)), 535)
    register("Ю", join(stem(67), transform(oval(), dx=266), box(145, 334, 410, 369)), 816)
    register("Я", transform(GLYPHS["R"][0], sx=-1, dx=541), 541)
    # Ukrainian and Belarusian additions are useful to the game's future locales.
    GLYPHS["І"] = GLYPHS["I"]
    register("Є", join(GLYPHS["C"][0], box(152, 334, 423, 370)), 535)
    register("Ґ", join(GLYPHS["Г"][0], box(347, 686, 432, 805)), 477)


def accents(mark, cx, baseline=740):
    if mark == "\u0301":  # acute
        return polygon((cx-66, baseline), (cx-20, baseline),
                       (cx+91, baseline+114), (cx+10, baseline+114))
    if mark == "\u0300":
        return transform(accents("\u0301", 0, baseline), sx=-1, dx=cx)
    if mark == "\u0302":
        return polygon((cx-122, baseline), (cx-79, baseline), (cx, baseline+62),
                       (cx+80, baseline), (cx+122, baseline), (cx+34, baseline+112),
                       (cx-35, baseline+112))
    if mark == "\u0308":
        return join(ellipse(cx-106, baseline, cx-35, baseline+71),
                    ellipse(cx+35, baseline, cx+106, baseline+71))
    if mark == "\u030b":  # Hungarian double acute, distinct from diaeresis
        return join(accents("\u0301", cx-67, baseline), accents("\u0301", cx+65, baseline))
    if mark == "\u0306":
        return svg(f"M {cx-122} {baseline+111} L {cx-96} {baseline+111} "
                   f"C {cx-77} {baseline+41} {cx+77} {baseline+41} {cx+96} {baseline+111} "
                   f"L {cx+122} {baseline+111} C {cx+116} {baseline-19} {cx-116} {baseline-19} {cx-122} {baseline+111} Z")
    if mark == "\u030a":
        return cut(ellipse(cx-70, baseline-4, cx+70, baseline+128),
                   ellipse(cx-36, baseline+30, cx+36, baseline+94))
    if mark == "\u0303":
        return svg(f"M {cx-127} {baseline+12} C {cx-82} {baseline+113} {cx-37} {baseline+102} {cx+7} {baseline+69} "
                   f"C {cx+54} {baseline+34} {cx+77} {baseline+32} {cx+105} {baseline+94} L {cx+127} {baseline+80} "
                   f"C {cx+86} {baseline-22} {cx+42} {baseline-12} {cx-7} {baseline+24} "
                   f"C {cx-52} {baseline+58} {cx-78} {baseline+60} {cx-105} {baseline} Z")
    if mark == "\u030c":
        return transform(accents("\u0302", cx, 0), sy=-1, dy=baseline+112)
    if mark == "\u0304":
        return box(cx-115, baseline+24, cx+115, baseline+63)
    if mark == "\u0307":
        return ellipse(cx-36, baseline, cx+36, baseline+72)
    if mark == "\u0327":
        return svg(f"M {cx-19} 8 L {cx+30} 8 L {cx+1} -49 "
                   f"C {cx+97} -54 {cx+81} -148 {cx-9} -158 "
                   f"C {cx-42} -161 {cx-68} -151 {cx-80} -140 L {cx-66} -116 "
                   f"C {cx-8} -145 {cx+41} -113 {cx+15} -87 L {cx-36} -73 Z")
    if mark == "\u0328":
        return svg(f"M {cx+8} 5 L {cx+47} 5 C {cx-59} -81 {cx-3} -138 {cx+62} -91 "
                   f"L {cx+79} -113 C {cx-6} -185 {cx-123} -105 {cx+8} 5 Z")
    raise ValueError(f"Unsupported accent {ord(mark):04X}")


def digits_and_symbols():
    # Original lining figures, with the same stroke contrast as the capitals.
    register("0", transform(oval(500), sy=.92), 500)
    register("1", join(stem(226, 107, top=644),
                       svg("M 112 539 L 112 568 C 183 586 214 610 248 650 "
                           "L 276 650 L 276 542 Z")), 470)
    two = svg("M 57 475 C 56 589 139 655 254 655 C 372 655 441 584 441 490 "
              "C 441 358 308 297 220 222 L 101 116 L 305 116 "
              "C 374 116 402 137 424 208 L 453 208 L 432 0 L 48 0 L 48 40 "
              "C 73 131 153 216 246 311 C 310 378 332 430 332 500 "
              "C 332 579 300 616 243 616 C 183 616 137 579 127 526 "
              "C 186 536 193 443 131 431 C 85 422 57 442 57 475 Z")
    register("2", two, 500)
    register("3", transform(GLYPHS["З"][0], sx=.94, sy=.92), 500)
    register("4", join(stem(302, 100, top=648), box(30, 188, 468, 226),
                       stroke(46, 217, 309, 633, 36), box(293, 644, 402, 656)), 510)
    five = svg("M 108 643 L 437 643 L 416 541 L 137 541 L 122 369 "
               "C 166 403 212 420 274 420 C 396 420 462 341 462 217 "
               "C 462 70 366 -12 245 -12 C 130 -12 65 54 57 125 "
               "C 53 180 111 203 144 170 C 174 136 153 98 118 94 "
               "C 140 50 183 26 232 26 C 314 26 350 90 350 204 "
               "C 350 315 306 366 237 366 C 184 366 138 343 113 318 L 78 332 Z")
    register("5", five, 505)
    six = join(cut(ellipse(43, -12, 462, 656), ellipse(157, 24, 357, 593)),
               cut(ellipse(128, -12, 464, 396), ellipse(172, 27, 351, 354)))
    # Open the upper counter into the curved shoulder of 6.
    six = cut(six, box(286, 405, 550, 540))
    register("6", six, 510)
    seven = svg("M 63 644 L 468 644 L 468 612 C 373 437 327 249 299 0 "
                "L 185 0 C 218 229 301 418 400 538 L 188 538 "
                "C 127 538 105 513 86 440 L 58 440 Z")
    register("7", seven, 508)
    register("8", join(cut(ellipse(69, 307, 441, 656), ellipse(172, 347, 338, 620)),
                       cut(ellipse(40, -12, 470, 356), ellipse(150, 26, 360, 318))), 510)
    register("9", transform(six, sx=-1, sy=-1, dx=510, dy=644), 510)
    register(".", ellipse(55, -8, 148, 85), 207)
    comma = join(GLYPHS["."][0], svg("M 136 45 C 170 -36 130 -104 70 -135 "
                                    "L 55 -109 C 105 -80 110 -46 89 -7 Z"))
    register(",", comma, 207)
    register(":", join(GLYPHS["."][0], transform(GLYPHS["."][0], dy=367)), 207)
    register(";", join(comma, transform(GLYPHS["."][0], dy=367)), 207)
    register("!", join(svg("M 55 700 L 163 700 L 136 169 L 83 169 Z"),
                       ellipse(62, -7, 156, 87)), 218)
    register("?", join(svg("M 42 539 C 42 650 120 712 222 712 C 349 712 416 640 416 537 "
                          "C 416 437 351 398 292 359 C 246 329 228 296 225 171 "
                          "L 189 171 C 174 309 192 369 244 419 C 284 458 304 482 304 543 "
                          "C 304 633 271 675 216 675 C 158 675 119 640 112 590 "
                          "C 173 600 188 515 132 492 C 86 473 42 493 42 539 Z"),
                       ellipse(162, -7, 255, 86)), 465)
    register("-", box(42, 246, 269, 289), 311)
    register("–", box(40, 246, 485, 289), 525)
    register("—", box(40, 246, 846, 289), 886)
    register("_", box(0, -105, 500, -64), 500)
    register("+", join(box(49, 273, 467, 311), box(239, 80, 277, 504)), 516)
    register("=", join(box(49, 191, 467, 230), box(49, 354, 467, 393)), 516)
    register("×", join(stroke(86, 110, 417, 470, 39), stroke(86, 470, 417, 110, 39)), 503)
    register("÷", join(box(49, 273, 467, 311), ellipse(222, 95, 294, 167),
                       ellipse(222, 417, 294, 489)), 516)
    register("/", stroke(43, -42, 327, 725, 38), 370)
    register("\\", transform(GLYPHS["/"][0], sx=-1, dx=370), 370)
    paren = svg("M 231 744 L 252 720 C 119 551 112 152 252 -57 L 229 -81 "
                "C 9 130 13 538 231 744 Z")
    register("(", paren, 290)
    register(")", transform(paren, sx=-1, dx=290), 290)
    register("[", join(box(71, -80, 145, 744), box(71, 710, 247, 744),
                       box(71, -80, 247, -46)), 295)
    register("]", transform(GLYPHS["["][0], sx=-1, dx=295), 295)
    quote = svg("M 65 700 L 155 700 L 119 498 L 79 498 Z")
    register("'", quote, 215)
    register('"', join(quote, transform(quote, dx=133)), 348)
    register("’", transform(comma, dy=627), 207)
    register("‘", transform(GLYPHS["’"][0], sx=-1, sy=-1, dx=207, dy=1200), 207)
    register("“", join(GLYPHS["‘"][0], transform(GLYPHS["‘"][0], dx=142)), 349)
    register("”", join(GLYPHS["’"][0], transform(GLYPHS["’"][0], dx=142)), 349)
    register("„", join(comma, transform(comma, dx=142)), 349)
    chevron = join(stroke(160, 108, 64, 287, 35), stroke(64, 287, 160, 464, 35))
    register("‹", chevron, 226)
    register("›", transform(chevron, sx=-1, dx=226), 226)
    register("«", join(chevron, transform(chevron, dx=148)), 374)
    register("»", transform(GLYPHS["«"][0], sx=-1, dx=374), 374)
    register("…", join(GLYPHS["."][0], transform(GLYPHS["."][0], dx=200),
                       transform(GLYPHS["."][0], dx=400)), 607)
    register("%", join(stroke(88, -5, 536, 705, 35),
                       cut(ellipse(33, 387, 281, 712), ellipse(108, 420, 206, 679)),
                       cut(ellipse(344, -12, 592, 313), ellipse(419, 21, 517, 280))), 630)
    register("‰", join(GLYPHS["%"][0],
                       cut(ellipse(630, -12, 878, 313), ellipse(705, 21, 803, 280))), 916)
    amp = svg("M 556 0 L 393 0 L 346 60 C 292 7 232 -12 175 -12 "
              "C 82 -12 24 42 24 133 C 24 230 78 284 164 340 "
              "C 111 409 82 453 82 523 C 82 635 157 712 260 712 "
              "C 354 712 406 651 406 572 C 406 486 345 432 264 390 L 406 184 "
              "C 447 250 455 301 447 338 C 440 355 423 365 392 366 "
              "L 392 390 L 548 390 L 548 366 C 494 361 491 328 477 282 "
              "C 464 227 445 188 427 157 L 484 73 C 511 34 524 26 556 22 Z")
    amp = cut(amp, svg("M 238 425 C 299 463 333 508 333 564 "
                       "C 333 630 306 675 261 675 C 210 675 185 636 185 584 "
                       "C 185 527 207 474 238 425 Z"))
    amp = cut(amp, svg("M 188 305 C 135 272 117 218 117 161 "
                       "C 117 79 161 30 225 30 C 264 30 296 48 327 87 Z"))
    register("&", amp, 595)
    register("*", join(stroke(128, 417, 128, 702, 30),
                       stroke(6, 489, 250, 631, 30), stroke(6, 631, 250, 489, 30)), 280)
    register("#", join(stroke(154, -10, 266, 711, 35), stroke(319, -10, 431, 711, 35),
                       box(56, 227, 465, 268), box(80, 443, 489, 484)), 545)
    register("@", join(transform(oval(740), sy=.9),
                       transform(oval(360), sx=.85, sy=.54, dx=202, dy=130),
                       stem(448, 62, bottom=155, top=467, serif=0)), 740)
    register("$", join(GLYPHS["S"][0], box(245, -107, 278, 803)), 530)
    register("€", join(GLYPHS["C"][0], box(8, 399, 318, 434), box(8, 267, 302, 302)), 535)
    register("£", join(transform(GLYPHS["L"][0], dx=8), box(15, 308, 353, 343)), 510)
    register("₽", join(GLYPHS["P"][0], box(18, 213, 327, 247)), 509)
    register("<", join(stroke(434, 104, 71, 292, 35), stroke(71, 292, 434, 480, 35)), 505)
    register(">", transform(GLYPHS["<"][0], sx=-1, dx=505), 505)
    register("|", box(76, -85, 113, 744), 190)
    register("{", join(transform(paren, sx=.8), box(36, 311, 96, 347)), 250)
    register("}", transform(GLYPHS["{"][0], sx=-1, dx=250), 250)
    register("^", accents("\u0302", 160, 390), 320)
    register("`", accents("\u0300", 133, 510), 266)
    register("~", accents("\u0303", 171, 234), 342)
    register("°", cut(ellipse(56, 475, 246, 705), ellipse(103, 520, 199, 660)), 302)
    register("•", ellipse(74, 244, 175, 345), 249)
    register("·", ellipse(74, 250, 139, 315), 213)
    # Number sign with an original small o and a rule, commonly used in Russian.
    register("№", join(GLYPHS["N"][0], transform(oval(420), sx=.55, sy=.45, dx=520, dy=376),
                       box(544, 306, 744, 336)), 790)


def finish_alphabets():
    # Explicit designs for letters without canonical Unicode decomposition.
    register("Æ", join(transform(GLYPHS["A"][0], sx=.78),
                       transform(GLYPHS["E"][0], dx=307)), 813)
    register("Œ", join(transform(oval(), sx=.95), transform(GLYPHS["E"][0], dx=356)), 862)
    register("Ø", join(GLYPHS["O"][0], stroke(81, 6, 469, 694, 38)), 550)
    register("Ł", join(GLYPHS["L"][0], stroke(36, 222, 279, 425, 38)), 494)
    register("Ð", join(GLYPHS["D"][0], box(6, 334, 295, 369)), 563)
    register("Þ", join(stem(67), bowl(173, 543, 466)), 509)
    # Historical long-s + short-s ligature; it remains distinct from SS.
    register("ẞ", join(stem(67), transform(GLYPHS["S"][0], sx=.66, dx=172),
                       box(146, 658, 341, 692)), 522)
    GLYPHS["ß"] = (transform(GLYPHS["ẞ"][0], sx=.79, sy=.74), 418)
    for upper in list(GLYPHS):
        lower = upper.lower()
        if len(lower) == 1 and lower != upper and lower not in GLYPHS:
            p, advance = GLYPHS[upper]
            register(lower, transform(p, sx=.79, sy=.74), round(advance*.79)+7)

    supported_marks = set("\u0300\u0301\u0302\u0303\u0304\u0306\u0307\u0308\u030a\u030b\u030c\u0327\u0328")
    for cp in list(range(0xC0, 0x250)) + list(range(0x400, 0x500)) + [0x1E9E]:
        char = chr(cp)
        if char in GLYPHS:
            continue
        nfd = unicodedata.normalize("NFD", char)
        if len(nfd) >= 2 and nfd[0] in GLYPHS and all(m in supported_marks for m in nfd[1:]):
            base, advance = GLYPHS[nfd[0]]
            small = nfd[0].islower()
            mark_parts = []
            for mark in nfd[1:]:
                p = accents(mark, 0, 740)
                below = unicodedata.combining(mark) == 202
                mark_parts.append(transform(p, sx=.86 if small else 1,
                                            sy=.86 if small else 1,
                                            dx=advance/2, dy=-79 if small and not below else 0))
            register(char, join(base, *mark_parts), advance)

    # Spacing and combining marks, including anchors for decomposed input.
    for mark in supported_marks:
        register(mark, accents(mark, 0), 0)
    empty = pathops.Path()
    for char in " \u00a0\u202f":
        register(char, empty, 218 if char != "\u202f" else 135)
    register("\u200b", empty, 0)
    register("\u00ad", GLYPHS["-"][0], GLYPHS["-"][1])
    register("´", accents("\u0301", 135, 510), 270)
    register("¨", accents("\u0308", 135, 510), 270)


def glyph_name(char):
    return f"uni{ord(char):04X}"


def bounds(path):
    pen = BoundsPen(None)
    path.draw(pen)
    return pen.bounds


def build():
    GLYPHS.clear()
    latin()
    cyrillic()
    digits_and_symbols()
    finish_alphabets()
    # Round once, after all derivative glyphs and accents have been assembled.
    # This also rounds Cyrillic joins and the counters of B/P/Б/Ь consistently.
    for char, (path, advance) in list(GLYPHS.items()):
        scale = .76 if char.islower() else 1
        if not char.isalpha():
            scale = .72
        GLYPHS[char] = (soften_corners(path, 11*scale, 25*scale), advance)
    glyphs, metrics = {}, {}
    notdef = cut(box(45, 0, 455, 700), box(86, 41, 414, 659))
    all_paths = {".notdef": (notdef, 500)}
    all_paths.update({glyph_name(c): g for c, g in sorted(GLYPHS.items(), key=lambda x: ord(x[0]))})
    for name, (path, advance) in all_paths.items():
        pen = TTGlyphPen(None)
        path.draw(Cu2QuPen(pen, max_err=0.65, reverse_direction=True))
        glyphs[name] = pen.glyph()
        # Use the rounded quadratic export's bounds, not cubic source bounds.
        glyphs[name].recalcBounds(None)
        metrics[name] = (advance, glyphs[name].xMin if glyphs[name].numberOfContours else 0)

    fb = FontBuilder(UPM, isTTF=True)
    fb.setupGlyphOrder(list(all_paths))
    fb.setupCharacterMap({ord(c): glyph_name(c) for c in GLYPHS})
    fb.setupGlyf(glyphs)
    fb.setupHorizontalMetrics(metrics)
    fb.setupHorizontalHeader(ascent=940, descent=-230, lineGap=20)
    fb.setupNameTable({
        "familyName": "Bressoles Display", "styleName": "Regular",
        "uniqueFontIdentifier": "Bressoles Display 0.110 softened outlines",
        "fullName": "Bressoles Display Regular", "psName": "BressolesDisplay-Regular",
        "version": "Version 0.110",
        "copyright": "Bressoles project. Original vector outlines, 2026.",
        "description": "Menu lettering inspired by the Bressoles reference. Lowercase is small capitals. Latin, Cyrillic, French and Hungarian.",
    })
    fb.setupOS2(sTypoAscender=940, sTypoDescender=-230, sTypoLineGap=20,
                usWinAscent=960, usWinDescent=230, sxHeight=518, sCapHeight=700,
                usWeightClass=600, usWidthClass=4, fsSelection=0xC0)
    fb.setupPost()
    fb.setupMaxp()
    font = fb.font
    font["head"].flags |= 0x08
    font["head"].fontRevision = .110
    font.recalcTimestamp = False
    timestamp = int(datetime(2026, 9, 30, tzinfo=timezone.utc).timestamp()) + 2082844800
    font["head"].created = timestamp
    font["head"].modified = timestamp + 86400
    for name_id, value in [(1, "Бресоль"), (2, "Обычный"), (4, "Бресоль — меню")]:
        font["name"].setName(value, name_id, 3, 1, 0x419)
    font["OS/2"].version = 4
    font["OS/2"].recalcUnicodeRanges(font)
    font["OS/2"].recalcCodePageRanges(font)
    gasp = newTable("gasp")
    gasp.gaspRange = {65535: 15}
    font["gasp"] = gasp
    features = ["languagesystem DFLT dflt;", "languagesystem latn dflt;", "languagesystem cyrl dflt;"]
    for mark in sorted(c for c in GLYPHS if unicodedata.combining(c)):
        above = unicodedata.combining(mark) != 202
        anchor_y = 740 if above else 0
        cls = "@TOP" if above else "@BOTTOM"
        features.append(f"markClass {glyph_name(mark)} <anchor 0 {anchor_y}> {cls};")
    features.append("feature mark {")
    for char, (p, advance) in GLYPHS.items():
        if char.isalpha() and not unicodedata.combining(char):
            y = 557 if char.islower() else 740
            features.append(f"pos base {glyph_name(char)} <anchor {round(advance/2)} {y}> mark @TOP "
                            f"<anchor {round(advance/2)} 0> mark @BOTTOM;")
    features.append("} mark;")

    # Optical pairs based on the shapes of the new outlines. Both GPOS and a
    # legacy kern table are emitted: pygame/SDL_ttf can use the latter.
    kerning = {}
    pairs = [("AV", -47), ("AW", -31), ("AY", -46), ("AT", -35),
             ("FA", -32), ("LA", -10), ("LT", -31), ("LV", -33), ("LY", -38),
             ("PA", -38), ("TA", -35), ("TO", -15), ("TC", -15), ("TY", -12),
             ("VA", -47), ("VO", -18), ("WA", -31), ("WO", -12),
             ("YA", -46), ("YO", -27), ("YC", -26), ("YT", -13),
             ("АУ", -39), ("ТА", -35), ("ГА", -35), ("ГЛ", -25), ("ГУ", -18),
             ("РА", -38), ("УА", -43), ("ТО", -15), ("ТД", -22),
             ("ЛТ", -20), ("ОУ", -12), ("ФА", -22)]
    features.append("feature kern {")
    for pair, value in pairs:
        left, right = pair
        for a, b in [(left, right), (left, right.lower()), (left.lower(), right), (left.lower(), right.lower())]:
            if a in GLYPHS and b in GLYPHS:
                val = round(value*(.79 if a.islower() and b.islower() else 1))
                kerning[(glyph_name(a), glyph_name(b))] = val
    for (a, b), value in kerning.items():
        features.append(f"pos {a} {b} {value};")
    features.append("} kern;")
    addOpenTypeFeaturesFromString(font, "\n".join(features))
    kern = newTable("kern")
    from fontTools.ttLib.tables._k_e_r_n import KernTable_format_0
    sub = KernTable_format_0()
    sub.version, sub.coverage, sub.kernTable = 0, 1, kerning
    kern.version, kern.kernTables = 0, [sub]
    font["kern"] = kern
    OUT.mkdir(exist_ok=True)
    ttf_path = OUT / "BressolesDisplay-Regular.ttf"
    font.save(ttf_path)
    web = TTFont(ttf_path, recalcTimestamp=False)
    web.flavor = "woff2"
    web.save(OUT / "BressolesDisplay-Regular.woff2")
    print(f"Built {ttf_path}: {len(GLYPHS)} encoded characters, {len(kerning)} kern pairs.")


if __name__ == "__main__":
    build()
