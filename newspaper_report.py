"""Result newspaper: factual round journal, localized prose and report navigation."""
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
import json

import native_render as pygame
import game_state
import profile_manager
from player_market_stats import accumulate, summarize
from player_other_stats import average
from gameplay_other_stats import OtherStatsMixin
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
            expected_count = sum(event['probabilities'][outcome] for event in rolls) / 100
            summary[stock]['outcomes'][outcome] = {
                'count': actual,
                'expected_count': expected_count,
                'actual_percent': 100 * actual / count if count else None,
                'expected_percent': 100 * expected_count / count if count else None,
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
    if getattr(page, 'red_reward_exhausted', False):
        cards.append(translate('Вы уже получили все красные карты колоды.'))
    for entry in getattr(page, 'blocked_reward_cards', []) or []:
        cards.append(text('blocked', card=page._newspaper_card_name(entry['card_id'])))
    if getattr(page, 'is_final_boss', False) and page.win_lose_state == 'win':
        cards.append(page._get_card_report_boss_description())
    bonus = page._get_card_report_frugality_bonus()
    if bonus:
        cards.append(str(bonus))
    return [finance, cards, market]


class NewspaperReportMixin(OtherStatsMixin):
    def _record_run_market_rolls(self, rolls):
        if not rolls:
            return
        if not hasattr(self, 'run_market_roll_stats'):
            self.run_market_roll_stats = deepcopy(
                game_state.boss_progress.get(self.level_number, game_state.new_boss_progress_state()).get('market_roll_stats'))
        if self.run_market_roll_stats is None:
            return
        accumulate(self.run_market_roll_stats, rolls, (0, 0, 0))
        if not getattr(self, 'test_mode', False):
            progress = game_state.boss_progress.setdefault(self.level_number, game_state.new_boss_progress_state())
            progress['market_roll_stats'] = deepcopy(self.run_market_roll_stats)

    def _market_report_summary(self):
        scope = getattr(self, 'market_report_scope', 'round')
        if scope == 'round':
            return summarize_round_rolls(getattr(self, 'newspaper_events', []))
        if scope == 'run':
            stats = getattr(self, 'run_market_roll_stats', None)
        else:
            if not hasattr(self, '_lifetime_market_report_stats'):
                slot = getattr(self, 'profile_slot', None)
                self._lifetime_market_report_stats = (
                    profile_manager.load_profile(slot).get('market_roll_stats')
                    if slot and not getattr(self, 'test_mode', False) else None)
            stats = self._lifetime_market_report_stats
        totals = summarize(stats)
        if totals is None:
            return None
        return {stock: {'rolls': values['rolls'], 'outcomes': {
            outcome: {'count': row['actual'], 'expected_count': row['expected'],
                      'actual_percent': row['actual_percent'], 'expected_percent': row['expected_percent']}
            for outcome, row in values['outcomes'].items()}}
            for stock, values in totals.items()}

    def _market_report_tabs(self, rect):
        gap = 12
        width = round(rect.width * .21)
        left = rect.centerx - (4 * width + 3 * gap) // 2
        return {scope: pygame.Rect(left + index * (width + gap),
                                  rect.top + round(rect.height * .365), width, 28)
                for index, scope in enumerate(('round', 'run', 'lifetime', 'other'))}

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
        if getattr(self, 'result_report_stage', 'newspaper') == 'newspaper':
            now = pygame.time.get_ticks()
            elapsed = now - int(getattr(self, 'finance_stamp_started_at', 0) or now)
            shake = self._get_finance_report_shake(
                getattr(self, 'finance_stamp_state', 'idle'), elapsed,
            )
            rect.move_ip(*shake)
        return rect

    def _start_newspaper_entrance(self):
        self.newspaper_y = float(-self._newspaper_target_rect().height - 72)
        self.newspaper_closing = False
        self._winlose_last_tick = pygame.time.get_ticks()
        self.newspaper_reward_report_started_at = pygame.time.get_ticks()
        self.newspaper_reward_report_auto_opened = False

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
        if (
            not closing
            and self.newspaper_y == target
            and getattr(self, "is_boss_fight", False)
            and getattr(self, "win_lose_state", None) == "win"
            and not getattr(self, "newspaper_reward_report_auto_opened", False)
            and now - int(getattr(self, "newspaper_reward_report_started_at", now)) >= 500
            and getattr(self, "card_report_image", None)
        ):
            self.result_report_stage = "card_report"
            self.finance_report_y = float(self.screen.get_height() + 30)
            self.finance_stamp_state = "idle"
            self.finance_stamp_started_at = now
            self.newspaper_reward_report_auto_opened = True
            self._play_result_report_rustle()
            self._save_active_game()
        if closing and self.newspaper_y == target:
            self.result_transition_ready = 'round_select' if self.win_lose_state == 'win' else 'level_select'

    def _newspaper_button_layout(self):
        rect = self._newspaper_rect()
        boundaries = (.028, .340, .662, .972)
        buttons = {}
        for index, stage in enumerate(('finance', 'card_report', 'market_report')):
            if self.win_lose_state == 'lose' and stage in ('finance', 'card_report'):
                continue
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
            if stage == 'market_report' and click and self.finance_stamp_state == 'idle':
                report_rect = image.get_rect(topleft=(
                    (self.screen.get_width() - image.get_width()) // 2, round(self.finance_report_y)))
                for scope, tab in self._market_report_tabs(report_rect).items():
                    if tab.collidepoint(event.pos):
                        self.market_report_scope = scope
                        self._save_active_game()
                        return None
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

        centered(text('market_button'), rect.centerx, rect.top+round(rect.height*.325), 30, True, rect.width*.9)
        scope = getattr(self, 'market_report_scope', 'round')
        for tab_scope, tab in self._market_report_tabs(rect).items():
            self._newspaper_button(tab, text('scope_' + tab_scope), font_size=16)
            if scope == tab_scope:
                pygame.draw.line(self.screen, ink, (tab.left + 8, tab.bottom - 4),
                                 (tab.right - 8, tab.bottom - 4), 2)
        if scope == 'other':
            self._draw_other_report(rect)
            return
        summary = self._market_report_summary()
        if summary is None:
            centered(text('no_roll_history'), rect.centerx, rect.top + round(rect.height * .55),
                     20, width=rect.width * .9)
            return
        left_margin = rect.left + round(rect.width * .028)
        table_width = round(rect.width * .944)
        group_width = table_width / 3
        table_top = rect.top + round(rect.height * .405)
        table_bottom = rect.top + round(rect.height * .77)
        pygame.draw.line(self.screen, ink, (left_margin, table_top),
                         (left_margin + table_width, table_top), 2)
        for index, stock in enumerate('ABC'):
            left = left_margin + round(index * group_width)
            def x(fraction):
                return left + round(group_width * fraction)

            if index:
                for offset in (-2, 2):
                    pygame.draw.line(self.screen, ink, (left + offset, table_top),
                                     (left + offset, table_bottom), 1)
            divider = x(.63)
            pygame.draw.line(self.screen, ink, (divider, table_top + 12),
                             (divider, table_bottom - 12), 1)
            heading_y = table_top + 16
            centered(text('actual_heading'), x(.455), heading_y, 20, True, group_width * .30)
            centered(text('expected_heading'), x(.815), heading_y, 20, True, group_width * .32)
            row_centers = [rect.top + round(rect.height * fraction) for fraction in (.51, .61, .71)]
            stock_font = self._newspaper_font(48, True)
            stock_image = stock_font.render(stock, True, ink)
            self.screen.blit(stock_image, stock_image.get_rect(center=(x(.075), row_centers[1])))
            for row, outcome in enumerate(('rise', 'flat', 'fall')):
                center_y = row_centers[row]
                icon = getattr(self, 'market_report_icons', {}).get(outcome)
                if icon:
                    scale = min(group_width * .17 / icon.get_width(),
                                rect.height * .075 / icon.get_height())
                    size = (max(1, round(icon.get_width() * scale)),
                            max(1, round(icon.get_height() * scale)))
                    graph = pygame.transform.smoothscale(icon, size)
                    self.screen.blit(graph, graph.get_rect(center=(x(.205), center_y)))
                values = summary[stock]['outcomes'][outcome]
                expected = f"{values['expected_count']:.1f}".rstrip('0').rstrip('.')
                actual_percent = values['actual_percent']
                expected_percent = values['expected_percent']
                cells = ((.36, str(values['count'])),
                         (.53, '—' if actual_percent is None else f'{actual_percent:.1f}%'),
                         (.715, expected),
                         (.90, '—' if expected_percent is None else f'{expected_percent:.1f}%'))
                for position, label in cells:
                    centered(label, x(position), center_y - 12, 22, False, group_width * .16)
            centered(text('sample_count', count=summary[stock]['rolls']), x(.5),
                     table_bottom + 12, 15, width=group_width * .9)
        note_width = round(table_width * .62)
        note_y = rect.top + round(rect.height * .85)
        font = self._newspaper_font(13)
        for note in ('expectation_note', 'random_only'):
            for line in wrap_lines(text(note), font, note_width):
                self.screen.blit(font.render(line, True, ink), (left_margin, note_y))
                note_y += 16
            note_y += 5

    def _draw_other_report(self, rect):
        ink = (38, 30, 21)
        top = rect.top + round(rect.height * .43)
        bottom = rect.top + round(rect.height * .84)
        pygame.draw.line(self.screen, ink, (rect.centerx, top), (rect.centerx, bottom), 1)
        for index, (heading, stats) in enumerate((
                ('scope_run', getattr(self, 'other_stats_run', None)),
                ('scope_lifetime', getattr(self, 'other_stats_lifetime', None)))):
            left = rect.left + round(rect.width * (.045 + index * .5))
            width = round(rect.width * .41)
            font = self._newspaper_font(23, True)
            title = font.render(text(heading), True, ink)
            self.screen.blit(title, title.get_rect(centerx=left + width // 2, top=top))
            y = top + 55
            if stats is None:
                rows = [text('no_other_history')]
            else:
                best = stats['best']
                if best:
                    label = best['label']
                    key = 'other_boss' if label['boss'] else 'other_round'
                    identity = text(key, level=label['level'],
                                    number=label['boss_number'] if label['boss'] else label['round'])
                    best_value = f"{identity} — {best['earned']:g}"
                else:
                    best_value = '—'
                mean = average(stats)
                rows = [text('other_best', value=best_value),
                        text('other_cards', value=stats['cards']),
                        text('other_average', value='—' if mean is None else f'{mean:.1f}')]
            font = self._newspaper_font(21)
            for value in rows:
                for line in wrap_lines(value, font, width):
                    self.screen.blit(font.render(line, True, ink), (left, y))
                    y += 28
                y += 28
        font = self._newspaper_font(14)
        y = rect.top + round(rect.height * .87)
        for line in wrap_lines(text('other_note'), font, round(rect.width * .67)):
            self.screen.blit(font.render(line, True, ink), (rect.left + round(rect.width * .045), y))
            y += 18
