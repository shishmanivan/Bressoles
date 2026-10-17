"""Result newspaper: factual round journal, localized prose and report navigation."""
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
import json

import native_render as pygame
import game_state
from localization import get_language, translate


@lru_cache(maxsize=1)
def catalog():
    return json.loads((Path(__file__).parent / 'locales' / 'newspaper.json').read_text(encoding='utf-8'))


def text(key, **values):
    return catalog()[get_language()][key].format(**values)


def amount(value):
    return f'{float(value or 0):g}'


@lru_cache(maxsize=32)
def newspaper_font(size, bold=False):
    return pygame.font.Font(str(Path(__file__).parent / 'Fonts' /
                                ('OldStandard-Bold.ttf' if bold else 'OldStandard-Regular.ttf')), size)


def summarize_round_rolls(events):
    """Expected percentage is the mean of the actual per-trial probabilities."""
    summary = {}
    for market, stock in enumerate('ABC'):
        rolls = [event for event in events if event.get('kind') == 'roll' and event['market'] == market]
        count = len(rolls)
        summary[stock] = {'rolls': count, 'outcomes': {}}
        for outcome in ('rise', 'fall', 'flat'):
            actual = sum(event['outcome'] == outcome for event in rolls)
            summary[stock]['outcomes'][outcome] = {
                'count': actual,
                'actual_percent': 100 * actual / count if count else None,
                'expected_percent': sum(event['probabilities'][outcome] for event in rolls) / count if count else None,
            }
    return summary


def wrap_lines(value, font, width):
    """Word-wrap, including a single card name longer than a column."""
    lines, line = [], ''
    for word in value.split():
        trial = f'{line} {word}'.strip()
        if font.size(trial)[0] <= width:
            line = trial
            continue
        if line:
            lines.append(line)
        line = ''
        for char in word:
            if line and font.size(line + char)[0] > width:
                lines.append(line)
                line = ''
            line += char
    if line:
        lines.append(line)
    return lines


def articles(page, detailed=False):
    finance, cards, market = [], [], []
    intro = text('intro_boss' if getattr(page, 'is_boss_fight', False) else 'intro',
                 level=page.level_number, round=page.round_num)
    for target in (finance, cards, market):
        target.append(intro)
    for event in getattr(page, 'newspaper_events', []):
        kind = event.get('kind')
        if kind == 'finance':
            finance.append(text('finance_turn', day=event['day'], cash=amount(event['cash']),
                                coins=amount(event['coins']), change=amount(event['change'])))
            for income in event.get('income', []):
                finance.append(text('turn_income', day=event['day'], value=amount(income['amount']),
                                    source={'sideway': 'Sideway', 'full_deployment': 'Full Deployment'}.get(income['source'], text('other_income'))))
            for stock, before, after in zip('ABC', event['before_prices'], event['prices']):
                market.append(text('market_' + ('up' if after > before else 'down' if after < before else 'flat'),
                                   day=event['day'], stock=stock, before=amount(before), after=amount(after)))
        elif kind in ('draw', 'deal'):
            cards.append(text(kind, day=event['day'], card=page._newspaper_card_name(event['card_id'])))
            description = page._newspaper_card_description(event['card_id'])
            if description:
                cards.append(description)
        elif kind == 'roll' and detailed:
            market.append(text('roll', day=event['day'], stock='ABC'[event['market']],
                               outcome=text(event['outcome']), sample=amount(event['random_value']),
                               probability=amount(event['probabilities'][event['outcome']])))
    if not any(e.get('kind') == 'finance' for e in getattr(page, 'newspaper_events', [])):
        finance.append(text('legacy'))
        market.append(text('legacy'))
    for entry in getattr(page, 'finance_report_entries', []):
        finance.append(text('income', label=translate(entry['label']), value=amount(entry['amount'])))
    finance.append(text('balance', cash=amount(page.Money), coins=amount(game_state.napoleondors)))
    rewards = list(getattr(page, 'last_earned_cards', []) or [])
    for card in rewards:
        cards.append(text('reward_boss' if getattr(page, 'is_boss_fight', False) else 'reward',
                          round=page.round_num, card=page._newspaper_card_name(card)))
        description = page._newspaper_card_description(card)
        if description:
            cards.append(description)
    if not rewards:
        cards.append(text('no_rewards'))
    for entry in getattr(page, 'blocked_reward_cards', []) or []:
        cards.append(text('blocked', card=page._newspaper_card_name(entry['card_id'])))
    if getattr(page, 'is_final_boss', False) and page.win_lose_state == 'win':
        cards.append(page._get_card_report_boss_description())
    bonus = page._get_card_report_frugality_bonus()
    if bonus:
        cards.append(str(bonus))
    return [finance, cards, market]


class NewspaperReportMixin:
    def _newspaper_event(self, kind, **data):
        if not hasattr(self, 'newspaper_events'):
            self.newspaper_events = []
        self.newspaper_events.append({'kind': kind, 'day': getattr(self, 'Day', 1), **deepcopy(data)})
        self._newspaper_surface_cache = None
        self._newspaper_market_cache = None

    def _capture_newspaper_turn(self, final=False):
        day = getattr(self, 'Day', 1)
        events = getattr(self, 'newspaper_events', [])
        sources = {e['source']: float(e.get('amount', 0))
                   for e in getattr(game_state, 'pending_finance_report_entries', [])}
        current = next((e for e in events if e['kind'] == 'finance' and e['day'] == day), None)
        if current:
            if final:
                current['cash'] = self.Money
                current['prices'] = [getattr(self, attr, 0) for attr in ('Aprice', 'BPrice', 'CPrice')]
                current['change'] += float(game_state.napoleondors or 0) - current['coins']
                current['coins'] = float(game_state.napoleondors or 0)
                current['income_sources'] = sources
                current['income'] = [{'source': source, 'amount': value-current.get('income_before', sources).get(source, 0)}
                                     for source, value in sources.items()
                                     if value > current.get('income_before', sources).get(source, 0)]
                self._newspaper_surface_cache = None
                self._newspaper_market_cache = None
            return
        previous = next((e for e in reversed(events) if e['kind'] == 'finance'), None)
        baseline = previous or getattr(self, 'newspaper_opening', {})
        prices = [getattr(self, attr, 0) for attr in ('Aprice', 'BPrice', 'CPrice')]
        coins = float(game_state.napoleondors or 0)
        before_sources = baseline.get('income_sources', sources)
        self._newspaper_event('finance', cash=self.Money, coins=coins,
                              change=coins - baseline.get('coins', coins),
                              prices=prices, before_prices=baseline.get('prices', prices),
                              income_sources=sources, income_before=before_sources,
                              income=[{'source': source, 'amount': value-before_sources.get(source, 0)}
                                      for source, value in sources.items() if value > before_sources.get(source, 0)])

    def _newspaper_card_name(self, card_id):
        from gameplay_page import FIELD_CARD_TOOLTIPS
        try:
            content = FIELD_CARD_TOOLTIPS.get(int(card_id))
        except (ValueError, TypeError):
            content = None
        return translate(str(content[0])) if content else text('card', id=card_id)

    def _newspaper_card_description(self, card_id):
        from gameplay_page import FIELD_CARD_TOOLTIPS
        try:
            content = FIELD_CARD_TOOLTIPS.get(int(card_id))
        except (ValueError, TypeError):
            content = None
        return translate(str(content[1])) if content and len(content) > 1 else ''

    def _newspaper_target_rect(self):
        width, height = self.screen.get_size()
        h = height - 82
        w = round(h * 1056 / 1488)
        return pygame.Rect((width - w) // 2, 12, w, h)

    def _newspaper_rect(self):
        rect = self._newspaper_target_rect()
        rect.y = round(getattr(self, 'newspaper_y', rect.y))
        return rect

    def _start_newspaper_entrance(self):
        self.newspaper_y = float(-self._newspaper_target_rect().height - 72)
        self.newspaper_closing = False
        self._winlose_last_tick = pygame.time.get_ticks()

    def _update_newspaper_animation(self, dt):
        now = pygame.time.get_ticks()
        state = getattr(self, 'finance_stamp_state', 'idle')
        elapsed = now - getattr(self, 'finance_stamp_started_at', now)
        if state == 'pressing' and elapsed >= 170:
            self.finance_stamp_state = 'flying'
            self.finance_stamp_started_at = now
        elif state == 'flying' and elapsed >= 300:
            self.finance_stamp_state = 'stamped'
            self.finance_stamp_started_at = now
        elif state == 'stamped' and elapsed >= 360:
            self.finance_stamp_state = 'closing'
            self.newspaper_closing = True
        rect = self._newspaper_target_rect()
        closing = getattr(self, 'newspaper_closing', False)
        target = float(-rect.height - 72 if closing else rect.top)
        current = float(getattr(self, 'newspaper_y', target))
        step = 1800 * dt
        self.newspaper_y = min(target, current + step) if current < target else max(target, current - step)
        if closing and self.newspaper_y == target:
            self.result_transition_ready = 'round_select' if self.win_lose_state == 'win' else 'level_select'

    def _newspaper_button_layout(self):
        rect = self._newspaper_rect()
        boundaries = (.028, .340, .662, .972)
        buttons = {}
        for index, stage in enumerate(('finance', 'card_report', 'market_report')):
            left = rect.left + round(rect.width * boundaries[index])
            right = rect.left + round(rect.width * boundaries[index + 1])
            width = min(round(rect.width * .26), right - left - 28)
            buttons[stage] = pygame.Rect((left + right - width) // 2, rect.bottom - 53, width, 28)
        stamp = self._newspaper_stamp_image()
        size = stamp.get_size() if stamp else (buttons['market_report'].width, 90)
        buttons['continue'] = pygame.Rect(0, 0, *size)
        buttons['continue'].midbottom = (buttons['market_report'].centerx, buttons['market_report'].top - 12)
        return buttons

    def _newspaper_stamp_image(self):
        original = getattr(self, 'approve_stamp_rotated', None)
        if original is None:
            return None
        width = round(self._newspaper_target_rect().width * .26)
        cache = getattr(self, '_newspaper_stamp_image_cache', None)
        if not cache or cache[0] != (id(original), width):
            height = max(1, round(original.get_height() * width / original.get_width()))
            cache = ((id(original), width), pygame.transform.smoothscale(original, (width, height)))
            self._newspaper_stamp_image_cache = cache
        return cache[1]

    def _newspaper_font(self, size, bold=False):
        return newspaper_font(size, bold)

    def _newspaper_button(self, rect, label, font_size=15):
        pygame.draw.rect(self.screen, (232, 212, 168), rect, border_radius=3)
        pygame.draw.rect(self.screen, (66, 48, 26), rect, 1, border_radius=3)
        size = font_size
        while size > 9 and self._newspaper_font(size, True).size(label)[0] > rect.width - 10:
            size -= 1
        surface = self._newspaper_font(size, True).render(label, True, (34, 26, 19))
        self.screen.blit(surface, surface.get_rect(center=rect.center))

    def _draw_newspaper(self, active=True):
        rect = self._newspaper_rect()
        cache = getattr(self, '_newspaper_surface_cache', None)
        key = (get_language(), rect.size, self.win_lose_state)
        if not cache or cache[0] != key:
            surface = pygame.Surface(rect.size, pygame.SRCALPHA)
            image = getattr(self, 'newspaper_report_image', None)
            if image:
                surface.blit(pygame.transform.smoothscale(image, rect.size), (0, 0))
            else:
                surface.fill((236, 219, 176))
                masthead = self._newspaper_font(52, True).render('BRESSOLES', True, (34, 26, 19))
                surface.blit(masthead, masthead.get_rect(center=(rect.width // 2, int(rect.height * .16))))
                for x in (.34, .66):
                    pygame.draw.line(surface, (66, 48, 26), (int(rect.width*x), int(rect.height*.329)),
                                     (int(rect.width*x), rect.height-40))
            headline = text('win' if self.win_lose_state == 'win' else 'lose')
            size = 31
            while size > 16 and self._newspaper_font(size, True).size(headline)[0] > rect.width * .91:
                size -= 1
            title = self._newspaper_font(size, True).render(headline, True, (34, 26, 19))
            surface.blit(title, title.get_rect(center=(rect.width//2, round(rect.height*.282))))
            body_font = self._newspaper_font(12)
            column_width = round(rect.width * .322)
            body_width = column_width - 20
            for index, (heading, paragraphs) in enumerate(zip(('finances', 'cards', 'market'), articles(self))):
                x = round(rect.width * .028) + index * column_width + 9
                y = round(rect.height * .341)
                hsize = 19
                while hsize > 11 and self._newspaper_font(hsize, True).size(text(heading))[0] > body_width:
                    hsize -= 1
                heading_image = self._newspaper_font(hsize, True).render(text(heading), True, (34, 26, 19))
                surface.blit(heading_image, heading_image.get_rect(centerx=x + body_width//2, top=y))
                y += 32
                # Each article is one continuous justified block, without paragraph breaks.
                lines = wrap_lines(' '.join(paragraphs), body_font, body_width)
                body_bottom = rect.height - 70
                if index == 2:
                    body_bottom = min(body_bottom, self._newspaper_button_layout()['continue'].top - rect.top - 12)
                for number, line in enumerate(lines):
                    if y + 14 > body_bottom:
                        break
                    words = line.split()
                    if number < len(lines)-1 and len(words) > 1:
                        space = (body_width - sum(body_font.size(w)[0] for w in words)) / (len(words)-1)
                        cursor = float(x)
                        for word in words:
                            ink = body_font.render(word, True, (38, 30, 21))
                            surface.blit(ink, (round(cursor), y))
                            cursor += body_font.size(word)[0] + space
                    else:
                        surface.blit(body_font.render(line, True, (38, 30, 21)), (x, y))
                    y += 13
            self._newspaper_surface_cache = (key, surface)
            cache = self._newspaper_surface_cache
        self.screen.blit(cache[1], rect.topleft)
        for stage, button in self._newspaper_button_layout().items():
            if stage == 'continue':
                stamp = self._newspaper_stamp_image()
                if active:
                    self._draw_result_stamp(button.center, stamp)
                elif stamp:
                    self.screen.blit(stamp, button.topleft)
                continue
            self._newspaper_button(button, text({'finance':'finance_button', 'card_report':'cards_button',
                                                 'market_report':'market_button', 'continue':'continue'}[stage]),
                                   font_size=15 if stage == 'continue' else 13)

    def _handle_newspaper_input(self, event):
        stage = getattr(self, 'result_report_stage', 'newspaper')
        if stage == 'newspaper':
            if (getattr(self, 'newspaper_closing', False)
                    or getattr(self, 'finance_stamp_state', 'idle') != 'idle'
                    or self._newspaper_rect().top != self._newspaper_target_rect().top
                    or event.type != pygame.MOUSEBUTTONDOWN or event.button != 1):
                return None
            for target, rect in self._newspaper_button_layout().items():
                if not rect.collidepoint(event.pos):
                    continue
                if target == 'continue':
                    self.finance_stamp_state = 'pressing'
                    self.finance_stamp_started_at = pygame.time.get_ticks()
                    if getattr(self, 'stamp_sound', None):
                        self.stamp_sound.play()
                    self._save_active_game()
                    return None
                self.result_report_stage = target
                self.finance_report_y = float(self.screen.get_height() + 30)
                self.finance_stamp_state = 'idle'
                self.finance_stamp_started_at = 0
                self.finance_stamp_rect = None
                self._winlose_last_tick = pygame.time.get_ticks()
                self._play_result_report_rustle()
                self._save_active_game()
                return None
        else:
            image = self._get_active_result_report_image()
            if not image or abs(self.finance_report_y - (self.screen.get_height()-image.get_height())//2) > 1:
                return None
            click = event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
            escape = event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE
            stamp = getattr(self, 'finance_stamp_rect', None)
            if self.finance_stamp_state == 'idle' and (escape or (click and stamp and stamp.collidepoint(event.pos))):
                if getattr(self, 'stamp_sound', None):
                    self.stamp_sound.play()
                self.finance_stamp_state = 'pressing'
                self.finance_stamp_started_at = pygame.time.get_ticks()
        return None

    def _return_to_newspaper(self):
        self.result_report_stage = 'newspaper'
        self.finance_stamp_state = 'idle'
        self.finance_stamp_started_at = 0
        self.finance_stamp_rect = None
        self.newspaper_y = float(self._newspaper_target_rect().top)
        self.newspaper_closing = False
        self._winlose_last_tick = pygame.time.get_ticks()
        self._save_active_game()

    def _draw_newspaper_detail(self):
        self._draw_finance_report()

    def _draw_market_report_rows(self, rect):
        ink = (38, 30, 21)
        def centered(label, center_x, top, size=17, bold=False, width=None):
            if width:
                while size > 10 and self._newspaper_font(size, bold).size(label)[0] > width:
                    size -= 1
            surface = self._newspaper_font(size, bold).render(label, True, ink)
            self.screen.blit(surface, surface.get_rect(centerx=center_x, top=top))

        centered(text('market_button'), rect.centerx, rect.top+round(rect.height*.265), 30, True, rect.width*.9)
        summary = summarize_round_rolls(getattr(self, 'newspaper_events', []))
        boundaries = (.028, .340, .662, .972)
        icons = getattr(self, 'market_report_icons', {})
        for index, stock in enumerate('ABC'):
            left = rect.left+round(rect.width*boundaries[index])+10
            right = rect.left+round(rect.width*boundaries[index+1])-10
            center = (left+right)//2
            centered(stock, center, rect.top+round(rect.height*.345), 29, True)
            centered(text('sample_count', count=summary[stock]['rolls']), center,
                     rect.top+round(rect.height*.385), 14, width=right-left)
            for row, outcome in enumerate(('rise', 'fall', 'flat')):
                y = rect.top+round(rect.height*(.425 + row*.13))
                values = summary[stock]['outcomes'][outcome]
                centered(text(outcome), center, y, 17, True, right-left)
                icon = icons.get(outcome)
                if icon:
                    icon = pygame.transform.smoothscale(icon, (68, 68))
                    self.screen.blit(icon, (left, y+29))
                metric_left = left+76
                metric_center = (metric_left+right)//2
                for line, (key, value) in enumerate((('actual_count', values['count']),
                                                     ('actual_percent', values['actual_percent']),
                                                     ('expected_percent', values['expected_percent']))):
                    shown = str(value) if key == 'actual_count' else ('—' if value is None else f'{value:.1f}%')
                    centered(text(key, value=shown), metric_center, y+29+line*23,
                             14, key=='actual_count', right-metric_left)
        for index, note in enumerate(('expectation_note', 'random_only')):
            left = rect.left+round(rect.width*boundaries[index])+12
            width = round(rect.width*(boundaries[index+1]-boundaries[index]))-24
            y = rect.top+round(rect.height*.835)
            font = self._newspaper_font(13)
            for line in wrap_lines(text(note), font, width):
                self.screen.blit(font.render(line, True, ink), (left, y))
                y += 15
