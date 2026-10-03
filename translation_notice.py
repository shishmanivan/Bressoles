"""Target-language consent, shown before changing the active locale."""
import pygame
from sound_assets import load_button_sound

NOTICES = {
    'FR': (
        'Cette traduction a été réalisée par une machine électrique — le meilleur traducteur de l’Exposition universelle de 1867.\n\n'
        'Si les erreurs de la machine risquent d’offenser votre sens philologique du beau, il vous sied de renoncer à cette version linguistique.',
        'Renoncer',
    ),
    'DE': (
        'Diese Übersetzung wurde von einer elektrischen Maschine angefertigt — dem besten Übersetzer der Weltausstellung von 1867.\n\n'
        'Sollten die Fehler der Maschine Ihr philologisches Schönheitsempfinden beleidigen können, so sei Ihnen angeraten, auf diese Sprachfassung zu verzichten.',
        'Verzichten',
    ),
    'HU': (
        'E fordítás egy elektromos gép műve — az 1867-es világkiállítás legkiválóbb fordítójáé.\n\n'
        'Ha a gép tévedései sérthetik az Ön filológiai szépérzékét, úgy tanácsos lemondania e nyelvi változatról.',
        'Elutasítás',
    ),
}


class TranslationNotice:
    def __init__(self, screen, language):
        self.screen = screen
        self.language = language
        self.text, self.decline_label = NOTICES[language]
        self.picture = pygame.image.load('UI/Translator.png').convert_alpha()
        self.frame = pygame.image.load('UI/Ornate Button Blank.png').convert_alpha()
        bounds = max(pygame.mask.from_surface(self.frame, 127).get_bounding_rects(), key=lambda rect: rect.width * rect.height)
        self.frame = self.frame.subsurface(bounds).copy()
        self.focus = 0
        self.pressed_index = None
        self.press_until = 0
        self.pending_decision = None
        self.click_sound = load_button_sound()
        self._size = None
        self.layout()

    def layout(self):
        if self._size == self.screen.get_size():
            return
        self._size = self.screen.get_size()
        w, h = self._size
        self.panel = pygame.Rect(0, 0, min(1100, w - 32), min(980, h - 24))
        self.panel.center = (w // 2, h // 2)
        margin = max(16, round(self.panel.width * .04))
        available = (self.panel.width - 2 * margin, int(self.panel.height * .47))
        ratio = min(available[0] / self.picture.get_width(), available[1] / self.picture.get_height())
        self.art = pygame.transform.smoothscale(self.picture, (round(self.picture.get_width()*ratio), round(self.picture.get_height()*ratio)))
        self.art_rect = self.art.get_rect(midtop=(self.panel.centerx, self.panel.top + margin))
        button_width = min(340, int(self.panel.width * .38))
        button_height = min(round(button_width * self.frame.get_height() / self.frame.get_width()), int(self.panel.height * .15))
        self.button_image = pygame.transform.smoothscale(self.frame, (button_width, button_height))
        self.buttons = [self.button_image.get_rect(midbottom=(self.panel.centerx + offset, self.panel.bottom-margin)) for offset in (-round(self.panel.width*.23), round(self.panel.width*.23))]
        self.text_rect = pygame.Rect(self.panel.left+margin, self.art_rect.bottom+16, self.panel.width-2*margin, self.buttons[0].top-self.art_rect.bottom-30)
        for size in range(min(29, max(16, round(h/36))), 10, -1):
            font = pygame.font.Font('Fonts/OldStandard-Regular.ttf', size)
            lines = []
            for paragraph in self.text.split('\n'):
                line = ''
                for word in paragraph.split():
                    candidate = (line + ' ' + word).strip()
                    if line and font.size(candidate)[0] > self.text_rect.width:
                        lines.append(line)
                        line = word
                    else:
                        line = candidate
                lines.append(line)
            if len(lines) * font.get_linesize() <= self.text_rect.height:
                break
        self.lines = [font.render(line, True, (57, 39, 24)) for line in lines]
        self.line_height = font.get_linesize()
        self.labels = []
        for text in ('OK', self.decline_label):
            for size in range(max(16, round(button_height*.27)), 9, -1):
                label = pygame.font.Font('Fonts/OldStandard-Bold.ttf', size).render(text, True, (57, 29, 12))
                if label.get_width() <= button_width * .65:
                    break
            self.labels.append(label)

    def start_press(self, index):
        if self.pending_decision is not None:
            return
        self.pressed_index = index
        self.pending_decision = 'accept' if index == 0 else 'decline'
        self.press_until = pygame.time.get_ticks() + 110
        if self.click_sound is not None:
            self.click_sound.play()

    def poll_decision(self):
        if self.pending_decision is not None and pygame.time.get_ticks() >= self.press_until:
            decision = self.pending_decision
            self.pending_decision = None
            self.pressed_index = None
            return decision
        return None

    def handle_event(self, event):
        if event.type == pygame.QUIT:
            return 'quit'
        if event.type == pygame.VIDEORESIZE:
            self.screen = pygame.display.get_surface() or self.screen
            self.layout()
        if self.pending_decision is not None:
            return None
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return 'decline'
            if event.key in (pygame.K_TAB, pygame.K_LEFT, pygame.K_RIGHT):
                self.focus = 1 - self.focus
            if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self.start_press(self.focus)
        if event.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN):
            for index, rect in enumerate(self.buttons):
                if rect.collidepoint(event.pos):
                    self.focus = index
                    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        self.start_press(index)
        return None

    def draw(self):
        self.layout()
        shade = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        shade.fill((20, 13, 7, 175))
        self.screen.blit(shade, (0, 0))
        pygame.draw.rect(self.screen, (233, 214, 175), self.panel, border_radius=8)
        pygame.draw.rect(self.screen, (92, 65, 36), self.panel, width=3, border_radius=8)
        self.screen.blit(self.art, self.art_rect)
        for index, line in enumerate(self.lines):
            self.screen.blit(line, (self.text_rect.x, self.text_rect.y + index*self.line_height))
        for index, rect in enumerate(self.buttons):
            button = self.button_image.copy()
            button.blit(self.labels[index], self.labels[index].get_rect(center=button.get_rect().center))
            if index == self.pressed_index:
                button = pygame.transform.smoothscale(button, (max(1, int(rect.width * .96)), max(1, int(rect.height * .96))))
            self.screen.blit(button, button.get_rect(center=rect.center))
