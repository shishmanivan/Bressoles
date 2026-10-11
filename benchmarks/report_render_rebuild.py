"""Regenerate the measured tables from render_before.json / render_after.json."""
import json
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parent


def load(name):
    return json.loads((ROOT / name).read_text(encoding='utf-8'))


def main():
    before, after = load('render_before.json'), load('render_after.json')
    sizes = list(dict.fromkeys(tuple(sample['size']) for sample in before['samples']))
    scenes = list(dict.fromkeys(sample['scenario'] for sample in before['samples']))
    def rows(data, size, scene):
        return [s for s in data['samples'] if tuple(s['size']) == size and s['scenario'] == scene]
    def metric(data, size, scene, category='frame', key='p95_ms'):
        return median(s[category][key] for s in rows(data, size, scene))
    lines = ['# Измерения рендера: до / после', '',
             'Числа ниже — медиана p95 трёх прогонов, миллисекунды на кадр. '
             'Это короткие замеры текущего компьютера, а не сертификация целевого ноутбука.', '',
             '| Сцена | ' + ' | '.join(f'{w}×{h}' for w,h in sizes) + ' |',
             '|---|' + '---:|'*len(sizes)]
    for scene in scenes:
        cells = [f'{metric(before, size, scene):.2f} → {metric(after, size, scene):.2f}' for size in sizes]
        lines.append('| ' + scene + ' | ' + ' | '.join(cells) + ' |')
    lines += ['', '## Один прыжок: подробности после оптимизации', '',
              '| Размер | p50 | p95 | p99 | >16,7 мс / 108 | >33,3 мс / 108 | Подготовка p95 | Показ и композиция p95 |',
              '|---|---:|---:|---:|---:|---:|---:|---:|']
    for size in sizes:
        samples = rows(after, size, 'jump')
        numbers = [metric(after, size, 'jump', key=f'p{p}_ms') for p in (50,95,99)]
        lines.append(f'| {size[0]}×{size[1]} | ' + ' | '.join(f'{n:.2f}' for n in numbers)
            + f' | {sum(s["frame"]["over_16_7"] for s in samples)}'
            + f' | {sum(s["frame"]["over_33_3"] for s in samples)}'
            + f' | {metric(after, size, "jump", "prepare"):.2f}'
            + f' | {metric(after, size, "jump", "present"):.2f} |')
    lines += ['', '## Первый показ и ресурсы', '',
              'Первый кадр указан отдельно от конструктора страницы и пяти кадров прогрева. '
              'Только самый первый конструктор в процессе имеет холодные кэши загрузчиков; '
              'последующие конструкторы используют общие ресурсы.', '',
              '| Размер | Первый static до → после, мс | CPU прыжка, % одного ядра | RSS после, МиБ | Native-кэш, МиБ / записей |',
              '|---|---:|---:|---:|---:|']
    for size in sizes:
        samples = rows(after, size, 'jump')
        cold = [median(s['first_frame_ms'] for s in rows(data,size,'static')) for data in (before,after)]
        lines.append(f'| {size[0]}×{size[1]} | {cold[0]:.1f} → {cold[1]:.1f}'
            + f' | {median(s["cpu_percent_one_core"] for s in samples):.1f}'
            + f' | {median(s["memory"]["rss"] for s in samples)/1024**2:.1f}'
            + f' | {median(s["cache_bytes"] for s in samples)/1024**2:.1f} / '
            + f'{median(s["cache_entries"] for s in samples):.0f} |')
    index = {(tuple(s['size']),s['scenario'],s['run']):s for s in before['samples']}
    equal = sum(s['hash'] == index[(tuple(s['size']),s['scenario'],s['run'])]['hash'] for s in after['samples'])
    lines += ['', f'Совпадение итоговых RGBA-хэшей: **{equal} / {len(after["samples"])}**.', '',
              'Первичные данные: `render_before.json`, `render_after.json`. '
              'Снимки: `output/render_rebuild/render_before/` и `render_after/`.', '']
    (ROOT / 'RENDER_REBUILD_TABLES.md').write_text('\n'.join(lines), encoding='utf-8')
    runtime_report()


def runtime_report():
    lines = ['# Длинные прогоны и время анимаций', '',
             'Это отдельные прогоны с обработчиком пустого ввода; они не заменяют '
             'основное сравнение одинаковых кадров. Числа p95 — медианы трёх прогонов.', '']
    if (ROOT / 'render_update.json').exists():
        flip, update = load('render_flip.json'), load('render_update.json')
        lines += ['## Полный и частичный показ', '',
                  '120 кадров × 3 прогона на сцену. Пересборка повреждённых областей '
                  'включена в обоих вариантах; меняется только вызов SDL display.', '',
                  '| Размер | Сцена | flip p95, мс | update(rects) p95, мс |',
                  '|---|---|---:|---:|']
        for size in ((1366,768), (1920,1080), (3840,2160)):
            for scene in ('static', 'jump'):
                values = [median(s['frame']['p95_ms'] for s in data['samples']
                    if tuple(s['size']) == size and s['scenario'] == scene) for data in (flip,update)]
                lines.append(f'| {size[0]}×{size[1]} | {scene} | {values[0]:.2f} | {values[1]:.2f} |')
        lines += ['', 'Оставлен полный flip: в целевом 1080p выигрыш p95 одного прыжка '
                  'около 4%, меньше наблюдаемой вариативности. На 4K частичный показ '
                  'помогает сильнее, но не достигает бюджета 16,7 мс. Полный путь проще '
                  'при смене страниц, восстановлении окна и модальных переходах.', '',
                  'За 120 кадров прыжка: 0 загрузок файлов, 0 вытеснений, '
                  '0 снимков plain Surface. На первом цикле появляются ещё 1–2 '
                  'варианта текста и один изображения из-за округления границ; '
                  'затем повторные циклы используют те же рецепты/варианты. '
                  'Неподвижная сцена прогревает только исходную позицию.']
    if (ROOT / 'render_turn_after.json').exists():
        before, after = load('render_turn_before.json'), load('render_turn_after.json')
        lines += ['', '## Последовательное завершение хода', '',
                  '600 кадров, Clock.tick(60), настоящий SDL и реальное время. '
                  'Длительность включает завершение эффектов и переходов руки. '
                  'FPS означает частоту цикла, а не измеренную частоту физической развёртки.', '',
                  '| Размер | Ход до → после, мс | p95 до → после, мс | FPS до → после |',
                  '|---|---:|---:|---:|']
        for size in ((1366,768),(1920,1080)):
            groups = [[s for s in d['samples'] if tuple(s['size']) == size] for d in (before,after)]
            duration = [median(s['end_turn_duration_ms'] for s in group) for group in groups]
            frame = [median(s['frame']['p95_ms'] for s in group) for group in groups]
            fps = [median(s['output_fps'] for s in group) for group in groups]
            lines.append(f'| {size[0]}×{size[1]} | {duration[0]:.0f} → {duration[1]:.0f}'
                + f' | {frame[0]:.2f} → {frame[1]:.2f} | {fps[0]:.1f} → {fps[1]:.1f} |')
    if (ROOT / 'render_runtime_after.json').exists():
        data = load('render_runtime_after.json')
        lines += ['', '## Прыжки по реальным часам после возобновления работы', '',
                  '240 кадров, Clock.tick(60), три прогона. Сохраняем каждый прогон: '
                  'скорость исполнения резко изменилась во время этой серии. '
                  'Причина изменения нагрузки/производительности машины не установлена; '
                  'медленные прогоны не отброшены.', '',
                  '| Размер | Прогон | p95 кадра, мс | FPS | Длительность прыжка min / median / max, мс |',
                  '|---|---:|---:|---:|---:|']
        for sample in data['samples']:
            durations = sample['jump_durations_ms']
            w,h = sample['size']
            lines.append(f'| {w}×{h} | {sample["run"]+1} | {sample["frame"]["p95_ms"]:.2f}'
                + f' | {sample["output_fps"]:.1f} | {min(durations)} / {median(durations):.0f} / {max(durations)} |')
        lines += ['', 'Проверка целевого p95 ≤16,7 мс в 1080p **не считается завершённой**: '
                  'короткая серия укладывается, более длинные и повторные — не всегда. '
                  'Для приёмки нужен повтор на целевом ноутбуке с зафиксированными '
                  'питанием, загрузкой ОС, монитором и DPI. Растягивания логики на '
                  'число кадров нет; момент регистрации завершения ограничен '
                  'фактическим интервалом обновления.']
    path = ROOT / 'render_lifecycle.json'
    if path.exists():
        data = load(path.name)
        lines += ['', '## Повторные модальные окна и resize', '',
                  'Каждый цикл: пауза, колода, закрытие, 1920×1080, возврат к '
                  '1366×768, изменение Turns/цены. Между циклами собирается мусор.', '',
                  '| Прогон | Циклы | RSS после 1-го / последнего, МиБ | Максимум RSS, МиБ |',
                  '|---|---:|---:|---:|']
        for sample in data['samples']:
            values = [m['rss']/1024**2 for m in sample['memory_cycles']]
            lines.append(f'| {sample["run"]+1} | {len(values)} | {values[0]:.1f} / {values[-1]:.1f} | {max(values):.1f} |')
        lines += ['', 'Это ограниченная проверка циклов интерфейса, не многочасовой '
                  'прогон всех боссов/раундов. Повторные настоящие эффекты хода проверены '
                  'отдельной серией выше. Память исходных ресурсов входит в RSS.']
    (ROOT / 'RENDER_REBUILD_RUNTIME.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')


if __name__ == '__main__':
    main()
