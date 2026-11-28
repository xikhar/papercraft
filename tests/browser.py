"""The templates and the capture pipeline in a real browser, start to finish.

    python -I -B tests/browser.py [--keep <dir>] [--only stills,formats,pages,video,film,audio]

Runs scripts/capture.py the way a build would and checks what comes out: the 3D template builds with no page error,
passes the look gates in day, dusk and night, and its hero's cards do not cut into each other; a vertical frame
renders at its size; the structures sampler and the 2D template build; a video's frames are the right steps in the
right colours on both the fast (WebCodecs) and the PNG path; a hero-less film turns from day to night with
H.mixMood, lights its lamps and panes, shows an image card's own back, and a time= still is the video's frame; an
MP4 with sound has the level it reports. Needs what capture.py needs (Python, Playwright, Chrome, ffmpeg) plus numpy
and Pillow. About three minutes.
"""
import argparse, os, re, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..')).replace(os.sep, '/')
SKILL = os.path.normpath(os.path.join(HERE, '..', 'skills', 'papercraft'))
ASSETS = os.path.join(SKILL, 'assets').replace('\\', '/')
CAPTURE = os.path.join(SKILL, 'scripts', 'capture.py')
MEASURE = os.path.join(SKILL, 'scripts', 'measure.py')
PAL = [(200, 40, 40), (40, 180, 60), (50, 60, 200), (230, 200, 60), (60, 200, 200), (200, 60, 190)]
ENV = dict(os.environ, MSYS_NO_PATHCONV='1', PYTHONIOENCODING='utf-8')


def py(script, *args, timeout=900):
    r = subprocess.run([sys.executable, '-I', '-B', script, *args], capture_output=True, text=True, encoding='utf-8',
                       errors='replace', env=ENV, timeout=timeout)
    return r.returncode, (r.stdout or '') + (r.stderr or '')


def tail(text, n=6):
    return ' | '.join(l.strip()[:160] for l in text.strip().splitlines()[-n:])


def video_frames(mp4):
    """Every frame of an MP4 as (grey of the top half, rgb of the bottom half), read at the centre of each half."""
    import numpy as np
    p = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height',
                        '-of', 'csv=p=0', mp4], capture_output=True, text=True).stdout.strip().split(',')
    w, h = int(p[0]), int(p[1])
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', mp4, '-vf', 'scale=in_color_matrix=bt709:in_range=tv,format=rgb24',
                          '-f', 'rawvideo', '-'], capture_output=True).stdout
    fr = np.frombuffer(raw, dtype=np.uint8).reshape(-1, h, w, 3).astype(float)
    return [(float(f[h // 8:h * 3 // 8, w // 4:w * 3 // 4].mean()), f[h * 5 // 8:h * 7 // 8, w // 4:w * 3 // 4].reshape(-1, 3).mean(0)) for f in fr]


def audio_levels(mp4):
    """(integrated LUFS, peak dBFS) of an MP4's sound, or None when it has none."""
    r = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', mp4, '-af', 'ebur128,volumedetect', '-f', 'null', '-'],
                       capture_output=True, text=True, encoding='utf-8', errors='replace').stderr
    i, pk = re.findall(r'\bI:\s+(-?[\d.]+) LUFS', r), re.findall(r'max_volume: (-?[\d.]+) dB', r)
    return (float(i[-1]), float(pk[-1])) if i and pk else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--keep', default='', help='keep the captures in this folder')
    ap.add_argument('--only', default='', help='comma-separated parts: stills, formats, pages, video, film, audio')
    a = ap.parse_args()
    for tool in ('ffmpeg', 'ffprobe'):
        if not shutil.which(tool):
            sys.exit(f'browser.py: {tool} is not on PATH')
    try:
        import numpy, PIL, playwright  # noqa: F401
    except ImportError as e:
        sys.exit(f'browser.py: {e}; pip install numpy pillow playwright')
    from PIL import Image
    parts = [p.strip() for p in a.only.split(',') if p.strip()] or ['stills', 'formats', 'pages', 'video', 'film', 'audio']
    tmp = (a.keep or tempfile.mkdtemp(prefix='pc_browser_')).replace('\\', '/')
    os.makedirs(tmp, exist_ok=True)
    fails, n = [], 0

    def check(ok, what, detail=''):
        nonlocal n
        n += 1
        print(f'  {"ok  " if ok else "FAIL"} {what}{("  " + detail) if detail else ""}', flush=True)
        if not ok:
            fails.append(what)
        return ok

    T3 = ['--page', 'templates/popup-3d/index.html']
    if 'stills' in parts:
        print('3D template: day, dusk, night', flush=True)
        out = f'{tmp}/3d'
        rc, log = py(CAPTURE, ASSETS, 'overview', 'mood=dusk', 'mood=night', *T3, '--out', out)
        check(rc == 0 and 'PAGE ERROR' not in log, 'builds in three moods with no page error', '' if rc == 0 else tail(log))
        check(log.count('hero: no card cuts into another') == 3, 'the hero\'s cards do not cut into each other')
        for shot, profile in (('overview', 'storybook'), ('mood-dusk', 'dusk'), ('mood-night', 'night')):
            f = f'{out}/{shot}.png'
            if not os.path.isfile(f):
                check(False, f'{shot}: the capture exists')
                continue
            rc, log = py(MEASURE, f, '--profile', profile, '--compact', '--strict')
            check(rc == 0, f'{shot}: every look gate passes ({profile})', '' if rc == 0 else tail(log, 2))

    if 'formats' in parts:
        print('3D template: a vertical frame', flush=True)
        out = f'{tmp}/reel'
        rc, log = py(CAPTURE, ASSETS, 'overview', *T3, '--size', 'reel', '--out', out)
        f = f'{out}/overview.png'
        size = Image.open(f).size if os.path.isfile(f) else None
        check(rc == 0 and size == (1080, 1920), '9:16 renders at 1080x1920 with no page error', f'{size}' if rc == 0 else tail(log))
        check('hero: no card cuts into another' in log, 'the hero\'s cards do not cut into each other at 9:16')

    if 'pages' in parts:
        print('the other pages', flush=True)
        for label, page in (('structures sampler', 'templates/popup-3d/structures.html'), ('2D template', 'templates/popup-2d/index.html')):
            out = f'{tmp}/{label.split()[0]}'
            rc, log = py(CAPTURE, ASSETS, 'overview', '--page', page, '--out', out)
            check(rc == 0 and 'PAGE ERROR' not in log and os.path.isfile(f'{out}/overview.png'), f'{label} builds with no page error', '' if rc == 0 else tail(log))

    if 'video' in parts:
        print('video: which step, which colour, on both paths', flush=True)
        steps = os.path.join(HERE, 'pages', 'steps').replace('\\', '/')
        for label, extra, want_fast in (('fast path', [], True), ('PNG path', ['--png-frames'], False)):
            out = f'{tmp}/video_{label.split()[0].lower()}'
            rc, log = py(CAPTURE, steps, 'a:timeline=0.5,30', 'b:timeline=0.4,30,0.2', '--size', '640x360', '--out', out, *extra)
            if not check(rc == 0, f'{label}: two clips encode', '' if rc == 0 else tail(log)):
                continue
            fast = log.count('through WebCodecs')
            check(fast == (2 if want_fast else 0), f'{label}: the frames came the expected way', f'{fast} of 2 clips through WebCodecs')
            for clip, first, count in (('a', 1, 15), ('b', 7, 12)):
                fr = video_frames(f'{out}/{clip}.mp4')
                want = [first + i for i in range(count)]
                got = [round(g / 16) % 16 for g, _ in fr]
                check(len(fr) == count and got == [s % 16 for s in want], f'{label}, clip {clip}: every frame is its own step', f'{len(fr)} frames, steps {got}')
                if len(fr) == count:
                    grey = max(abs(g - (s * 16) % 256) for (g, _), s in zip(fr, want))
                    col = max(float(abs(c - PAL[s % 6]).max()) for (_, c), s in zip(fr, want))
                    check(grey <= 5 and col <= 8, f'{label}, clip {clip}: greys and colours are the ones drawn', f'worst grey off by {grey:.1f}, worst colour by {col:.1f} (limits 5, 8)')

    if 'film' in parts:
        print('a film: light over time, lamps, lit panes, an image card with its own back, stills at a film time', flush=True)
        import numpy as np
        out, FILM = f'{tmp}/film', 'tests/pages/film/index.html'
        rc, log = py(CAPTURE, REPO, 'day:time=1', 'night:time=4', 'clip:timeline=4,30', '--page', FILM, '--size', '960x540', '--out', out)
        rc2, log2 = py(CAPTURE, REPO, 'back:time=1', '--page', FILM + '?view=back', '--size', '960x540', '--out', out)
        ok = check(rc == 0 and rc2 == 0 and 'PAGE ERROR' not in log + log2, 'the film page builds, plays and turns to night with no page error',
                   '' if rc == 0 and rc2 == 0 else tail(log if rc else log2))
        if ok:
            px = lambda name: np.asarray(Image.open(f'{out}/{name}.png').convert('RGB')).astype(float)
            day, night, back = px('day'), px('night'), px('back')
            luma = lambda a: float((a @ np.array([0.2126, 0.7152, 0.0722])).mean())
            box = lambda a, x0, x1, y0, y1: a[y0:y1, x0:x1].reshape(-1, 3)
            # the frame: an octagon image card in the middle (x 334-626, y 122-382), four bushes round it, a lamp by
            # each of the two near bushes
            ground_d, ground_n = box(day, 300, 660, 10, 60).mean(0), box(night, 300, 660, 10, 60).mean(0)
            check(luma(night) < 0.6 * luma(day) and ground_n[2] > ground_n[0] + 15 and ground_d[0] > ground_d[2] + 15,
                  'H.mixMood turns the day to night', f'mean luma {luma(day):.0f} -> {luma(night):.0f}, ground rgb {ground_d.round()} -> {ground_n.round()}')
            pane_d, pane_n = luma(box(day, 465, 495, 255, 285)), luma(box(night, 465, 495, 255, 285))
            face_n = luma(box(night, 360, 410, 200, 300))
            check(pane_n > pane_d + 20 and pane_n > 2 * face_n, 'the glow mask of the image card lights up at night',
                  f'pane luma {pane_d:.0f} by day, {pane_n:.0f} at night, the card round it {face_n:.0f}')
            def bush(a, x0, x1, y0, y1):          # the bush pixels in a box: greener than blue
                b = box(a, x0, x1, y0, y1)
                b = b[b[:, 1] > b[:, 2] + 8]
                return float((b @ np.array([0.2126, 0.7152, 0.0722])).mean()) if len(b) > 50 else 0.0
            near_n, far_n = bush(night, 40, 200, 370, 480), bush(night, 55, 190, 225, 315)
            near_d, far_d = bush(day, 40, 200, 370, 480), bush(day, 55, 190, 225, 315)
            check(near_d > 0 and far_d > 0 and far_n > 0 and near_n / far_n > 1.25 * near_d / far_d, 'the lamps come on as the light turns',
                  f'near bush / far bush luma {near_d / max(1, far_d):.2f} by day, {near_n / max(1, far_n):.2f} at night')
            face = box(day, 360, 410, 200, 300).mean(0)
            stripe, blue = box(back, 350, 400, 200, 300).mean(0), box(back, 480, 600, 200, 300).mean(0)
            check(face[0] > face[2] + 60 and blue[2] > blue[0] + 15 and stripe[0] > stripe[2] + 15,
                  'the image card shows its own back art from behind, the right way round',
                  f'front {face.round()}, back {blue.round()}, its stripe on the left {stripe.round()}')
            rc3, log3 = py(CAPTURE, REPO, 'late:time=3', 'early:time=1', '--page', FILM + '?cue', '--size', '960x540', '--out', out)
            if check(rc3 == 0 and 'PAGE ERROR' not in log3, 'a light set from a cue plays', '' if rc3 == 0 else tail(log3)):
                late, early = luma(px('late')), luma(px('early'))
                check(late < 0.6 * early and abs(early - luma(day)) < 12, 'restart() puts the starting light back',
                      f'mean luma {late:.0f} after the cue, {early:.0f} in the still taken after it (day {luma(day):.0f})')
            mp4 = f'{out}/clip.mp4'
            if os.path.isfile(mp4):
                raw = subprocess.run(['ffmpeg', '-v', 'error', '-sseof', '-0.2', '-i', mp4, '-vf', 'scale=in_color_matrix=bt709:in_range=tv,format=rgb24',
                                      '-f', 'rawvideo', '-'], capture_output=True).stdout
                fr = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 540, 960, 3).astype(float)
                d = float(np.abs(fr[-1] - night).mean()) if len(fr) else 99.0
                check(len(fr) > 0 and d <= 4.0, 'a time= still is the frame the video has at that time', f'mean difference {d:.2f} levels (limit 4)')
            else:
                check(False, 'the film clip was written')

    if 'audio' in parts:
        print('sound', flush=True)
        out = f'{tmp}/audio'
        rc, log = py(CAPTURE, ASSETS, 'paper:timeline=4,30', *T3, '--size', '720p', '--audio', '--out', out)
        lv = audio_levels(f'{out}/paper.mp4') if rc == 0 else None
        check(rc == 0 and lv is not None, 'the template\'s opening renders with its paper sounds', '' if rc == 0 else tail(log))
        if lv:
            check(-60 <= lv[1] <= -6, 'paper alone is audible and keeps the kit\'s quiet level', f'peak {lv[1]:.1f} dBFS (expected -60 to -6)')
        tone = f'{tmp}/tone.wav'
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-f', 'lavfi', '-i', 'sine=frequency=220:duration=6', '-af', 'volume=-20dB', '-ar', '44100', tone])
        rc, log = py(CAPTURE, ASSETS, 'mix:timeline=4,30', *T3, '--size', '720p', '--audio', '--music-wav', tone, '--out', out)
        lv = audio_levels(f'{out}/mix.mp4') if rc == 0 else None
        check(rc == 0 and lv is not None, 'the same clip mixes with a music file', '' if rc == 0 else tail(log))
        if lv:
            check(abs(lv[0] + 16) <= 1 and lv[1] <= -1, 'the mix sits at -16 LUFS and does not clip', f'{lv[0]:.1f} LUFS, peak {lv[1]:.1f} dBFS')
        rc2, log2 = py(CAPTURE, ASSETS, 'loop:timeline=4,30', *T3, '--size', '720p', '--audio', '--loop', '--music-wav', tone, '--out', out)

        def tail_db(mp4):   # the mean level of the last quarter second
            r = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-sseof', '-0.25', '-i', mp4, '-af', 'volumedetect', '-f', 'null', '-'],
                               capture_output=True, text=True, encoding='utf-8', errors='replace').stderr
            m = re.findall(r'mean_volume: (-?[\d.]+) dB', r)
            return float(m[-1]) if m else None
        faded, kept = (tail_db(f'{out}/mix.mp4'), tail_db(f'{out}/loop.mp4')) if rc == 0 and rc2 == 0 else (None, None)
        check(faded is not None and kept is not None and kept > faded + 6, '--loop leaves the music unfaded at the end',
              f'last quarter second {faded} dB faded, {kept} dB with --loop' if faded is not None else tail(log2))

    print(f'browser: {n - len(fails)}/{n} checks passed' + (f'; failed: {"; ".join(fails)}' if fails else ''))
    if not a.keep:
        shutil.rmtree(tmp, ignore_errors=True)
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    main()
