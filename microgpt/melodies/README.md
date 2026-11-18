# microgpt melodies

Training the tiny character-level GPT on folk tunes instead of names. The model
reads and writes melodies as text in [ABC notation](https://abcnotation.com/), and
`play_melody.py` turns that text back into sound so you can hear what it learned.

## What's here

| File | What it is |
|---|---|
| `microgpt-melodies.py` | The model and training script, copied from `../microgpt-random-seed.py` with `block_size = 48` for melody-length lines. |
| `melodies.txt` | Training data: one 4-bar phrase of a D-major reel per line. |
| `../play_melody.py` | Plays one line of melody. It sits one folder up; move it here with `mv ../play_melody.py .` if you prefer, and drop the `../` from the commands below. |

## Setup: point the script at the melody data

`microgpt-melodies.py` reads `melodies.txt`.

Run everything from inside this folder: the script opens its data file by a
relative path.

## Train and generate

```
cd melodies
python3 microgpt-melodies.py
```

The script trains for `num_steps` steps, one phrase per step, then prints 20 new
phrases. Measured on this machine with dummy lines of full length: `block_size = 24` took about
0.56 s per step and `block_size = 64` about 2.2 s, so 48 should land around
20–30 minutes for 1,000 steps. 48 itself has not been timed.

Sampling is reseeded from OS randomness just before generation, so training is the
same every run (seed 42) but the melodies differ each time.

## Listen

```
python3 ../play_melody.py "effedBAB|ddedB2A2|effedBAB|dBABd2d2"
python3 ../play_melody.py "sample  3: d2efafef|afefedBA|..."   # model output pasted as printed
python3 ../play_melody.py -f melodies.txt -n 5                  # line 5 of a file
python3 ../play_melody.py -f melodies.txt --random              # compare against real tunes
python3 ../play_melody.py "..." --bpm 140                       # reels are played fast; default is 100
python3 ../play_melody.py "..." --out tune.wav                  # save instead of playing
```

It plays through macOS's `afplay`; elsewhere use `--out` and open the WAV. It
assumes D major unless you pass `--key`. Characters it doesn't understand are
skipped with a warning, so a half-broken sample still plays.

A good habit: play a few random training lines first, so you know what "right"
sounds like, then play the model's samples.

## Reading the notation

Every line is in D major (F and C are sharp unless marked otherwise), with a plain
note lasting one eighth note.

| Text | Meaning |
|---|---|
| `C D E F G A B` | the octave starting at middle C |
| `c d e f g a b` | the octave above |
| `B,` `a'` | `,` drops an octave, `'` raises one |
| `d2` `A3` `B/` | note lengths: 2× and 3× an eighth, half an eighth |
| `^f` `=c` `_b` | sharp, natural, flat, lasting until the next bar line |
| `A>B` `A<B` | dotted pair: long-short or short-long |
| `(3efg` | triplet: three notes in the time of two |
| `z` | rest |
| `\|` | bar line; a reel bar adds up to eight eighth notes |

## Where the data came from

[The Session](https://thesession.org), an Irish traditional music community, publishes
its tune database at [github.com/adactio/TheSession-data](https://github.com/adactio/TheSession-data)
(`csv/tunes.csv`). `melodies.txt` was built from the November 2026 copy:

| Stage | Count |
|---|---|
| tune settings in the file | 55,791 |
| reels | 20,333 |
| reels in D major, the most common key, without a key change mid-tune | 4,930 |
| unique 4-bar phrases that fit in 47 characters | 16,462 |

Cleaning steps, and why:

- **Only reels in one key.** A model this small blurs several scales and rhythms into mush.
- **Removed:** chord symbols, ornaments, grace notes, bowing marks, slurs, ties and repeat
  signs. These are performance detail, not melody, and every extra symbol is another
  token the model has to learn.
- **Only the second of two repeat endings is kept.** Keeping both puts nine bars in an
  eight-bar part, and every phrase after it would start mid-phrase.
- **Only bars that add up to a full reel bar are kept.** This drops pickup notes and
  anything that didn't parse. The tune is split at each dropped bar, so a 4-bar group
  never straddles the gap.
- **Phrases longer than 47 characters are dropped.** The script adds a start/end
  token (BOS) to each line, and `block_size` must cover the line plus that token. Longer
  lines are cut off without warning at line 161, and the model would never learn
  how they end.
- **Exact duplicates are removed.** Many tunes share phrases, and repeats would
  overweight them.

The converter that does this, `make_melodies.py`, is not in the repository yet.
Its arguments are `tunes.csv out.txt [mode] [bars] [block_size]`, e.g.
`Gmajor 2 24` for 2-bar G-major phrases.

## Things to try

Change one thing at a time so you can tell what made the difference.

- **`temperature`** (line 190): lower is safer and more repetitive, higher is wilder.
- **Longer phrases**: rebuild the data with 8 bars (a full tune part) and raise
  `block_size` to fit. Training gets much slower: each step costs more than in
  proportion to line length, because every note attends to every earlier note.
- **A bigger model** (`n_embd`, `n_layer`): try this when samples sound random or stuck on a
  few notes. Doubling `n_embd` roughly quadruples the time per step, and a bigger
  model usually needs more `num_steps` too.
- **More of the data**: 1,000 steps sees only a small slice of `melodies.txt`;
  raising `num_steps` uses more of it.
- **Another key or tune type**: rebuild with a different mode (e.g. `Gmajor`) and
  pass the matching `--key` to the player.
