"""scripts/extract_cutouts.py on drawn sheets whose right answer is known.

    python -I -B tests/cutouts.py [--script other_extract_cutouts.py] [--keep <dir>]

Six pieces are drawn once (4x supersampled, so every edge pixel is a true mix) and laid on several backdrops. Each
sheet is cut, the cutouts are laid back over a teal card, and the result is compared with the same pieces drawn on
teal directly: any rim the backdrop left shows as an error in the edge band. Needs numpy and Pillow.
"""
import argparse, os, re, shutil, subprocess, sys, tempfile

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, '..', 'skills', 'papercraft', 'scripts', 'extract_cutouts.py')
W, H, SS = 1200, 800, 4
INK = (40, 34, 30)
TEAL = np.array([40, 120, 130], dtype=np.float32)
# name: bounding box, in reading order (rows top to bottom, each row left to right)
PIECES = {'white': (60, 80, 300, 280), 'red': (380, 80, 580, 280), 'ring': (660, 70, 900, 290),
          'mustard': (60, 560, 260, 720), 'tall': (380, 330, 560, 740), 'star': (700, 620, 760, 680)}
BIG = ['white', 'red', 'ring', 'mustard', 'tall']        # the star is under the default --min-area


def draw_pieces():
    """The pieces alone: (colour premultiplied by alpha [H, W, 3], alpha [H, W] 0..1)."""
    im = Image.new('RGBA', (W * SS, H * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    s = lambda box: tuple(v * SS for v in box)
    d.rounded_rectangle(s(PIECES['white']), radius=26 * SS, fill=(250, 250, 246, 255))            # light, no outline
    d.ellipse(s(PIECES['red']), fill=INK + (255,))
    x0, y0, x1, y1 = PIECES['red']
    d.ellipse(s((x0 + 6, y0 + 6, x1 - 6, y1 - 6)), fill=(200, 50, 40, 255))
    x0, y0, x1, y1 = PIECES['ring']
    d.ellipse(s((x0, y0, x1, y1)), fill=INK + (255,))
    d.ellipse(s((x0 + 6, y0 + 6, x1 - 6, y1 - 6)), fill=(238, 224, 196, 255))
    d.ellipse(s((x0 + 70, y0 + 60, x1 - 70, y1 - 60)), fill=INK + (255,))
    d.ellipse(s((x0 + 76, y0 + 66, x1 - 76, y1 - 66)), fill=(0, 0, 0, 0))                          # a hole
    x0, y0, x1, y1 = PIECES['mustard']
    d.polygon([(x0 * SS, y1 * SS), ((x0 + x1) // 2 * SS, y0 * SS), (x1 * SS, y1 * SS)], fill=INK + (255,))
    d.polygon([((x0 + 14) * SS, (y1 - 7) * SS), ((x0 + x1) // 2 * SS, (y0 + 16) * SS), ((x1 - 14) * SS, (y1 - 7) * SS)],
              fill=(220, 170, 60, 255))
    x0, y0, x1, y1 = PIECES['tall']
    d.rounded_rectangle(s((x0, y0, x1, y1)), radius=20 * SS, fill=INK + (255,))
    d.rounded_rectangle(s((x0 + 5, y0 + 5, x1 - 5, y1 - 5)), radius=16 * SS, fill=(238, 224, 196, 255))
    x0, y0, x1, y1 = PIECES['star']
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    d.polygon([(cx * SS, y0 * SS), ((cx + 9) * SS, (cy - 9) * SS), (x1 * SS, cy * SS), ((cx + 9) * SS, (cy + 9) * SS),
               (cx * SS, y1 * SS), ((cx - 9) * SS, (cy + 9) * SS), (x0 * SS, cy * SS), ((cx - 9) * SS, (cy - 9) * SS)],
              fill=(40, 50, 90, 255))
    a = np.asarray(im).astype(np.float32)
    al = a[:, :, 3] / 255.0
    pm = (a[:, :, :3] * al[:, :, None]).reshape(H, SS, W, SS, 3).mean((1, 3))
    return pm, al.reshape(H, SS, W, SS).mean((1, 3))


def on(pm, al, backdrop):
    return pm + (1.0 - al[:, :, None]) * np.array(backdrop, dtype=np.float32)


def run(script, sheet, out, *args):
    if os.path.isdir(out):
        shutil.rmtree(out)
    return subprocess.run([sys.executable, '-I', '-B', script, sheet, '--out', out, *args], capture_output=True, text=True)


def boxes_of(stdout):
    """[(name, x0, y0, x1, y1)] from the lines the script prints for the cutouts it wrote."""
    out = []
    for line in stdout.splitlines():
        m = re.search(r'\[\d+\] (\S+)\.png .*\((\d+),(\d+)\)-\((\d+),(\d+)\)', line)
        if m:
            out.append((m[1],) + tuple(int(v) for v in m.groups()[1:]))
    return out


def which_piece(box):
    for name, (x0, y0, x1, y1) in PIECES.items():
        if abs(box[1] - x0) <= 4 and abs(box[2] - y0) <= 4 and abs(box[3] - x1) <= 4 and abs(box[4] - y1) <= 4:
            return name
    return '?'


def lay_back(out, boxes, pad):
    """The cutouts over a teal card, each where it was cut from."""
    card = np.tile(TEAL, (H, W, 1))
    for name, x0, y0, x1, y1 in boxes:
        p = np.asarray(Image.open(os.path.join(out, name + '.png')).convert('RGBA')).astype(np.float32)
        p = p[pad:p.shape[0] - pad, pad:p.shape[1] - pad]
        a = p[:, :, 3:4] / 255.0
        card[y0:y1, x0:x1] = p[:, :, :3] * a + card[y0:y1, x0:x1] * (1.0 - a)
    return card


def grow(mask, r):
    m = mask.copy()
    for _ in range(r):
        p = np.pad(m, 1)
        m = p[1:-1, 1:-1] | p[:-2, 1:-1] | p[2:, 1:-1] | p[1:-1, :-2] | p[1:-1, 2:]
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--script', default=SCRIPT)
    ap.add_argument('--keep', default='', help='keep the sheets and cutouts in this folder')
    a = ap.parse_args()
    tmp = a.keep or tempfile.mkdtemp(prefix='pc_cutouts_')
    os.makedirs(tmp, exist_ok=True)
    pm, al = draw_pieces()
    truth = on(pm, al, TEAL)
    edge = grow((al > 0.02) & (al < 0.98), 2)
    fails, n = [], 0

    def check(ok, what, detail=''):
        nonlocal n
        n += 1
        print(f'  {"ok  " if ok else "FAIL"} {what}{("  " + detail) if detail else ""}')
        if not ok:
            fails.append(what)

    def save(name, backdrop, fmt='png'):
        path = os.path.join(tmp, f'{name}.{fmt}')
        im = Image.fromarray(np.clip(np.round(on(pm, al, backdrop)), 0, 255).astype(np.uint8), 'RGB')
        im.save(path, quality=90) if fmt == 'jpg' else im.save(path)
        return path

    # ---- the edge left by each backdrop: limits are levels of error (0-255) over the edge band, mean and 95th centile.
    # The outermost, mostly-backdrop pixel of an edge is cut away on purpose (a crisp cut, no halo): that is the
    # error that remains. A rim of backdrop colour is several times larger, and is what the limits catch.
    for name, backdrop, fmt, extra, lim in [
        ('magenta', (255, 0, 255), 'png', [], (6.5, 45)),
        ('magenta_jpg', (255, 0, 255), 'jpg', [], (11.5, 45)),
        ('green', (0, 255, 0), 'png', [], (6.5, 45)),
        ('blue', (0, 0, 255), 'png', ['--key', '#0000FF'], (6.5, 45)),
        ('white', (255, 255, 255), 'png', ['--punch-holes'], (8, 30)),
    ]:
        print(f'{name} backdrop')
        sheet, out = save(name, backdrop, fmt), os.path.join(tmp, name + '_out')
        r = run(a.script, sheet, out, '--pad', '6', *extra)
        if r.returncode:
            check(False, f'{name}: the script runs', (r.stderr or r.stdout).strip()[-300:])
            continue
        boxes = boxes_of(r.stdout)
        found = [which_piece(b) for b in boxes]
        if name == 'white':   # the light piece cannot be told from a white backdrop: it is not expected back
            check([f for f in found if f != 'white'] == [p for p in BIG if p != 'white'], f'{name}: pieces in reading order', str(found))
        else:
            check(found == BIG, f'{name}: five pieces in reading order', str(found))
        err = np.abs(lay_back(out, boxes, 6) - truth).max(axis=2)
        band = edge & (grow(al > 0.5, 3) if name != 'white' else True)
        if name == 'white':
            x0, y0, x1, y1 = PIECES['white']
            band = band.copy(); band[y0 - 4:y1 + 4, x0 - 4:x1 + 4] = False
        m, p95 = float(err[band].mean()), float(np.percentile(err[band], 95))
        check(m <= lim[0] and p95 <= lim[1], f'{name}: no rim from the backdrop', f'edge error mean {m:.1f}, 95th centile {p95:.1f} (limits {lim[0]}, {lim[1]})')
        if 'ring' in found:
            b = boxes[found.index('ring')]
            ring = np.asarray(Image.open(os.path.join(out, b[0] + '.png')))
            check(ring[ring.shape[0] // 2, ring.shape[1] // 2, 3] == 0, f'{name}: the hole in the ring is clear')
        if 'white' in found:
            b = boxes[found.index('white')]
            p = np.asarray(Image.open(os.path.join(out, b[0] + '.png'))).astype(np.float32)
            seen = p[:, :, 3] > 60
            off = (p[:, :, :3].min(axis=2) < 200) & seen
            share = 100.0 * off.sum() / max(1, (seen & (grow(~seen, 3))).sum())
            check(share <= 1.5, f'{name}: the light piece keeps a light edge', f'{share:.1f} % of its edge pixels are dark or tinted (limit 1.5)')

    # ---- names, small pieces and bad input
    print('names and small pieces')
    sheet, out = save('names', (255, 0, 255)), os.path.join(tmp, 'names_out')
    r = run(a.script, sheet, out, '--names', 'a,b,c,d,e,f')
    check(r.returncode != 0 and not os.path.isdir(out), 'six names for five pieces fails and writes nothing', (r.stderr.strip().splitlines() or [''])[-1][:150])
    check('dropped' in (r.stdout + r.stderr), 'the dropped small island is reported')
    r = run(a.script, sheet, out, '--names', 'a,b,c,d,e,f', '--min-area', '0.001')
    got = [which_piece(b) for b in boxes_of(r.stdout)]
    check(r.returncode == 0 and got == list(PIECES) and os.path.isfile(os.path.join(out, 'f.png')), 'six names fit once --min-area keeps the star', str(got))
    r = run(a.script, sheet, out, '--names', '../a,b,c,d,e')
    check(r.returncode != 0 and 'Traceback' not in r.stderr, 'a name with a path in it is refused')
    r = run(a.script, sheet, out, '--despill', '0')
    check(r.returncode == 0 and len(boxes_of(r.stdout)) == 5, '--despill 0 runs', r.stderr.strip()[-200:])
    r = run(a.script, os.path.join(tmp, 'nope.png'), out)
    check(r.returncode != 0 and 'Traceback' not in r.stderr, 'a missing sheet is a plain error')
    r = run(a.script, save('holes', (255, 0, 255)), out, '--keep-holes')
    ring = [b for b in boxes_of(r.stdout) if which_piece(b) == 'ring']
    check(bool(ring) and np.asarray(Image.open(os.path.join(out, ring[0][0] + '.png')))[122, 132, 3] == 255, '--keep-holes keeps the hole in the ring')

    # ---- a sheet that is already transparent: its alpha is the backdrop, dark outlines survive
    print('transparent sheet')
    rgba = np.dstack([np.clip(np.round(pm / np.maximum(al, 1e-4)[:, :, None]), 0, 255), np.round(al * 255)]).astype(np.uint8)
    sheet, out = os.path.join(tmp, 'clear.png'), os.path.join(tmp, 'clear_out')
    Image.fromarray(rgba, 'RGBA').save(sheet)
    r = run(a.script, sheet, out, '--pad', '0')
    boxes = boxes_of(r.stdout)
    check(r.returncode == 0 and [which_piece(b) for b in boxes] == BIG, 'five pieces from the alpha alone', r.stderr.strip()[-200:])
    if boxes:
        worst = 0
        for name, x0, y0, x1, y1 in boxes:
            p = np.asarray(Image.open(os.path.join(out, name + '.png')))
            keep = p[:, :, 3] > 24
            worst = max(worst, int(np.abs(p[:, :, 3].astype(int) - rgba[y0:y1, x0:x1, 3].astype(int))[keep].max()))
        check(worst == 0, 'the alpha is kept as it came (dark outlines survive)', f'largest change {worst}')

    print(f'cutouts: {n - len(fails)}/{n} checks passed' + (f'; failed: {"; ".join(fails)}' if fails else ''))
    if not a.keep:
        shutil.rmtree(tmp, ignore_errors=True)
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    main()
