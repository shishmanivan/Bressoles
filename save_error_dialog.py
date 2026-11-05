"""Pause a failed save without discarding the pending game state."""
import pygame



def wait_for_save_retry(error, recovery_path):
    screen = pygame.display.get_surface()
    if screen is None:
        pygame.display.init()
        screen = pygame.display.set_mode((1280, 720))
    previous = screen.copy()
    pygame.font.init()
    # The recovery dialog must not need another file from the failing disk.
    font = pygame.font.Font(None, 26)
    clock = pygame.time.Clock()
    lines = [
        "Не удалось прочитать или записать данные игры.",
        "Игра приостановлена до восстановления доступа.",
        "Закройте программы, использующие файл, и проверьте свободное место.",
        ("Подготовленные данные сохранены во временном файле."
         if recovery_path else "Прогресс пока хранится только в памяти. Не закрывайте игру."),
        "Нажмите Enter или кнопку, чтобы повторить операцию.",
    ]
    canvas = pygame.Surface((1280, 720))
    button = pygame.Rect(340, 480, 600, 65)
    try:
        while True:
            canvas.fill((30, 26, 23))
            for index, line in enumerate(lines):
                text = font.render(line, True, (245, 232, 207))
                canvas.blit(text, text.get_rect(center=(640, 180 + index * 52)))
            pygame.draw.rect(canvas, (100, 76, 44), button, border_radius=8)
            label = font.render("Повторить операцию", True, (255, 245, 225))
            canvas.blit(label, label.get_rect(center=button.center))
            screen.blit(pygame.transform.smoothscale(canvas, screen.get_size()), (0, 0))
            pygame.display.flip()
            for event in pygame.event.get():
                if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    return
                if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                    x, y = event.pos
                    if button.collidepoint(x * 1280 / screen.get_width(), y * 720 / screen.get_height()):
                        return
                # Closing the window must not silently discard unsaved progress.
            clock.tick(30)
    finally:
        screen.blit(previous, (0, 0))
        pygame.display.flip()
