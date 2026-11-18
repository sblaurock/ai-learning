"""Play one line of ABC melody, as found in melodies.txt or printed by the model.

    python3 play_melody.py "effedBAB|ddedB2A2|effedBAB|dBABd2d2"
    python3 play_melody.py -f melodies.txt -n 3       # third line of a file
    python3 play_melody.py -f melodies.txt --random   # any line
    python3 play_melody.py "..." --bpm 80 --out tune.wav

Only the ABC that melodies.txt uses is understood: notes, rests, lengths,
accidentals, octave marks, dotted rhythms, triplets and bar lines. Anything else
is skipped with a warning, because model samples can contain stray characters
and a half-heard tune is more useful than an error.
"""
import argparse, math, os, random, re, struct, subprocess, sys, tempfile, wave

RATE = 44100
STEP = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
SHARP_ORDER, FLAT_ORDER = 'FCGDAEB', 'BEADGCF'
MAJOR_SIGNATURE = {'C': 0, 'G': 1, 'D': 2, 'A': 3, 'E': 4, 'B': 5, 'F#': 6,
                   'F': -1, 'Bb': -2, 'Eb': -3, 'Ab': -4, 'Db': -5}  # sharps positive, flats negative

TOKEN = re.compile(r"\(3|[<>|]|(\^{1,2}|_{1,2}|=)?([A-Ga-gz])([,']*)(\d*)(/*)(\d*)")


def key_signature(key):
    n = MAJOR_SIGNATURE[key]
    return {c: 1 for c in SHARP_ORDER[:n]} if n >= 0 else {c: -1 for c in FLAT_ORDER[:-n]}


def parse(line, key):
    """Return [(midi note or None for a rest, length in eighth notes)]."""
    signature = key_signature(key)
    bar_accidentals = {}  # in ABC an accidental lasts until the bar line, for that one pitch
    events, triplet_left, broken, pos = [], 0, None, 0
    for m in TOKEN.finditer(line):
        if line[pos:m.start()].strip():
            print(f'skipping {line[pos:m.start()]!r}', file=sys.stderr)
        pos = m.end()
        tok = m.group(0)
        if tok == '(3':
            triplet_left = 3
        elif tok == '|':
            bar_accidentals.clear()
        elif tok in '<>':
            broken = tok
        else:
            acc, letter, octave, num, slashes, den = m.groups()
            length = int(num or 1) / (int(den) if den else 2 ** len(slashes))
            if triplet_left:
                length *= 2 / 3
                triplet_left -= 1
            if broken and events:  # A>B is A dotted then B halved; A<B the reverse
                long_, short = (1.5, 0.5) if broken == '>' else (0.5, 1.5)
                events[-1] = (events[-1][0], events[-1][1] * long_)
                length *= short
            broken = None
            if letter == 'z':
                events.append((None, length))
                continue
            # Uppercase C is middle C, lowercase is the octave above, and each
            # comma or apostrophe moves one further octave down or up.
            note = 60 + STEP[letter.upper()] + (12 if letter.islower() else 0)
            note += 12 * (octave.count("'") - octave.count(','))
            pitch_id = (letter, octave)
            if acc is not None:
                bar_accidentals[pitch_id] = {'^': 1, '^^': 2, '_': -1, '__': -2, '=': 0}[acc]
            note += bar_accidentals.get(pitch_id, signature.get(letter.upper(), 0))
            events.append((note, length))
    if line[pos:].strip():
        print(f'skipping {line[pos:]!r}', file=sys.stderr)
    return events


def render(events, bpm):
    """Synthesize a plucked, slightly reedy tone: decaying sine plus two quieter overtones."""
    eighth = 60 / bpm / 2
    samples = []
    for note, length in events:
        n = int(length * eighth * RATE)
        if note is None:
            samples.extend([0.0] * n)
            continue
        f = 440 * 2 ** ((note - 69) / 12)
        attack, release = int(0.005 * RATE), int(0.01 * RATE)  # short ramps stop clicks at note edges
        for i in range(n):
            t = i / RATE
            env = math.exp(-3 * t) * min(1, i / attack, (n - i) / release)
            w = 2 * math.pi * f * t
            samples.append(env * (math.sin(w) + 0.4 * math.sin(2 * w) + 0.15 * math.sin(3 * w)))
    peak = max((abs(s) for s in samples), default=1) or 1
    return b''.join(struct.pack('<h', int(s / peak * 0.8 * 32767)) for s in samples)


def write_wav(path, frames):
    with wave.open(path, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(frames)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('line', nargs='?', help='the melody, e.g. "effedBAB|ddedB2A2"')
    ap.add_argument('-f', '--file', help='read the melody from this file instead')
    ap.add_argument('-n', type=int, default=1, help='which line of --file, counting from 1')
    ap.add_argument('--random', action='store_true', help='pick a random line of --file')
    ap.add_argument('--key', default='D', choices=MAJOR_SIGNATURE, help='major key (default D, matching melodies.txt)')
    ap.add_argument('--bpm', type=float, default=100, help='quarter notes per minute (default 100)')
    ap.add_argument('--out', help='save a .wav here instead of playing it')
    args = ap.parse_args()

    if args.file:
        lines = [l.strip() for l in open(args.file) if l.strip()]
        line = random.choice(lines) if args.random else lines[args.n - 1]
    elif args.line:
        line = args.line
    else:
        ap.error('give a melody line or --file')
    # Model output is printed as "sample  3: ..."; accept it pasted as-is.
    line = re.sub(r'^sample\s*\d+:\s*', '', line.strip())
    print(line)

    frames = render(parse(line, args.key), args.bpm)
    if args.out:
        write_wav(args.out, frames)
        print(f'wrote {args.out}')
        return
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, 'melody.wav')
        write_wav(path, frames)
        if sys.platform == 'darwin':
            subprocess.run(['afplay', path])
        else:
            sys.exit('no player configured for this platform; use --out to save a .wav')


if __name__ == '__main__':
    main()
