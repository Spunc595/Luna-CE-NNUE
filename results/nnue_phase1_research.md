# NNUE reopening, phase 1: research (2026-09-25)

Reading and measurement only: no dataset downloaded (except a 24 MB prefix of one file, as a probe, see 1a), no engine
code changed, no decision taken. Every statement below says whether it was **observed** (read in a source or measured) or
**inferred**.

## 1a. `linrock/bullet-training-data`

- **It is on Hugging Face, not GitHub** (`huggingface.co/datasets/linrock/bullet-training-data`, created 2025-02-13, public,
  not gated). There is **no dataset card** (`README.md` returns 404) and the license field is empty: **no license is
  declared on the repository.** The source material is documented at `robotmoon.com/nnue-training-data`: Leela training data
  converted to binpack (see 1d); the S1 part was originally generated with Stockfish (see 1c).
- **Size and files** (observed, Hugging Face tree API): 23 files, **306.1 GB compressed** (zstd), two subsets:
  - `S1/UHO.pdist.iter-{1..10}.bullet.bin.zst`: 10 files of 19.80 GB each (198.0 GB);
  - `S2/test77nov-unfilt-test79-maraprmay-v6-dd.skip-see-ge0.wdl-pdist.iter-{1..12}.bullet.bin.zst`: 12 files of about 9.00 GB each (108.1 GB).
- **Format** (observed, decoded from a probe): `bullet` "ChessBoard", 32 bytes per position (occupancy u64, 16 bytes of piece nibbles,
  score i16, result u8, king squares, padding); side-to-move relative; result 0/1/2 = loss/draw/win for the side to move.
- **How many positions.** *Observed:* a 24 MB range of `S1 iter-1` and of `S2 iter-1` decompresses at a ratio of 1.99 and
  1.94 (1.56 M and 1.52 M positions in the prefix), which extrapolates to about **1.2 billion positions in one S1 file and
  0.55 billion in one S2 file** (an extrapolation from a prefix: the ratio may drift along the file). *Inferred, and not
  the same number for S2:* the training schedules of minifish and Petrel read 12 S2 files for 120 superbatches of
  100,007,936 positions = 12.0 billion, i.e. 1.0 billion per file if each is read once. The two figures disagree by a
  factor of about 1.8 for S2; the loader may be reading the files more than once, or the prefix ratio is pessimistic.
  Either way: **the billion is reached with one S1 file or two S2 files**, and the whole repository holds on the order of
  10 to 19 billion positions.
- Sample decoded (200,000 records each): S1 scores span +/-7,290 cp (1st/99th percentile -1,888/+1,952), S2 span +/-26,624
  (a clamp); mean 16.6 / 16.3 pieces on the board; 18% / 20% of positions have 8 pieces or fewer; W/D/L about 26/47/26% (S1)
  and 31/38/32% (S2) (loss/draw/win for the side to move).

**Does it reach the billion?** Yes, several times over. **With how many files?** One S1 file (about 20 GB compressed) or two
S2 files (about 18 GB) already exceed a billion positions; the full S2 set that Petrel trains on is 108 GB compressed.

## 1b. Petrel's recipe (all of it is in the repository, `net/petrel.rs`)

`AleksPeshkov/petrel`, `net/readme.txt`: the network is "created from scratch" with a fork of `bullet` (CPU backend),
a config "based on `bullet/examples/simple.rs` and influenced by" minifish's, on "Lc0 data files processed by Linrock" from
**S2 only**. Petrel 4.0 (2026-08-04, **3536 Elo CCRL Blitz**, "major strength improvement by increasing NNUE size 128 -> 1024"):

| | value (file at tag `v4.0`) |
|---|---|
| architecture | `Chess768` (no king buckets, no mirroring), `(768 -> 1024) x 2 -> 1`, SCReLU, single output |
| data | S2, the 12 files `...wdl-pdist.iter-1..12.bullet.bin` |
| training length | **240 superbatches**, batch 4,096, 24,416 batches per superbatch = **24.0 billion positions seen** |
| optimiser | AdamW; weight decay 0.01 (input weights, clipped +/-2.0), 0.02 (output, clipped to the quantisation bound) |
| learning rate | cosine decay, peak 4e-4, final = peak / 40 |
| WDL weight (lambda) | cosine decay from **0.0 to 0.1** |
| loss | sigmoid, power error 2.6; `eval_scale` 800 |
| quantisation | QA 1024, QB 8 (x400 output scale) |
| starting point | from scratch |

Petrel 4.1 (2026-09-08): `Chess768hm` (horizontal mirroring), **360 superbatches (36.0 billion positions seen)**, peak lr 4e-4
final /100, weight decay 0.005, output quantisation QB 16; the release notes say "WDL 0.0 -> 0.2" (I read the tagged script's
optimiser and schedule, not its WDL line, and the script was changed again later: commit "120sb WDL 0.2 -> 0.1", 2026-09-17).
The recipe is documented; it is not "undocumented".

**A correction to the premise of the phase.** The document says Petrel reached 3536 with "1 billion positions". The
configuration says **24 billion positions seen** (36 for 4.1) from a dataset of about 6.6 to 12 billion. The rule of thumb
of "a million positions per neuron" (about a billion for 1024 neurons) is therefore closer to a *minimum* than to what the
strongest reference net was trained on; the order of magnitude of the whole job is ten times larger than the billion.
(3536 Elo is Petrel's, with its own search; it is not a target for Luna's network.)

## 1c. Linrock's Kaggle writeup (read in full, via a text rendering of the page)

`kaggle.com/competitions/fide-google-efficiency-chess-ai-challenge/writeups/linrock-my-solution-cfish-nnue-data-1st`:

- Tiny net: 768 inputs (dual perspective, horizontal king mirroring), one hidden layer of 64 neurons, trained with `bullet`.
  "The most important aspect of the network strength was in data selection and processing." Best raw data: Leela's smaller
  ResNet runs, T77 and T79; data from larger networks "performed worse".
- **Two stages from scratch**: Stage 1, 100 superbatches (**10 billion positions**), data *originally generated with
  Stockfish*, trained purely on the position score of a 5,000-node search; Stage 2, 120 superbatches (**12 billion**),
  data from lc0, trained on a blend of score (converted from the average value Q) and game outcome. Stage 2 resumes from the
  end of Stage 1; both use AdamW with a linearly decaying learning rate. Training on weaker data first and the strongest
  last beat training on the strongest from scratch.
- **Filtering** (the data was prepared as several passes with different stochastic filters, stacked so that the sequential
  loader simulates several traversals): flatten the piece-count distribution (positions cluster at 32 pieces because all
  games start from the initial position); stochastic skipping where the game outcome is likely to match the position
  score; skip the first 28 plies of every game; **keep positions where a piece sacrifice is the best move (skip when
  SEE >= 0)**. Preprocessing "tens of billions" of positions is too heavy, so the piece-count flattening is done at loading time.
- That also explains the file names: `pdist` = the piece-count distribution flattening; `see-ge0` = "skip SEE >= 0" (the sacrifice filter, S2 only);
  `wdl` = the game-outcome blend, `UHO` = the Unbalanced Human Openings the Stockfish games started from.
- `min-v2`: **not defined in the writeup or in the scripts I could read** (open). Not needed for anything below.

## 1d. The pipeline, confirmed (the earlier guess was right in the direction you suspected)

`test80` is **Leela's T80 run**: `linrock/lc0-data-converter/lc0_data_downloader.sh` downloads from
`storage.lczero.org/files/training_data/test80`, and `robotmoon.com/nnue-training-data` states the data is "Converted from
Leela training data into the binpack data format". T77/T79 are Leela runs as well; the data is **not** Stockfish/fishtest
data (S1 is the exception: Stockfish games). Meanings, from Linrock's own scripts (`nnue-data`, `lc0-data-converter`):

- **`v6-dd`** (the file names' `v6-dd`, script `csv_filter_v6_dd.py`): filter version 6 with de-duplication. It drops the
  start position of each game, plies <= 28, positions with a single legal move, positions where the best move is clearly the
  only good one (the two best Stockfish scores differ by more than the thresholds in the script), and positions whose piece
  placement (the first FEN field) was already seen, processing the newest files first so the newest copy is the one kept.
  (The plain `v6` script also counts positions in check and best-move captures; the `-dd` script I read does not.)
- **`2tb7p`, `16tb7p`, `12tb7p`**: `tb7p` = rescored with Syzygy tablebases up to 7 pieces (`rescorer ... --syzygy-paths=345p:6p:7p`,
  best move and best score taken from the rescoring). **What the leading number (2, 12, 16) means is not documented in
  any script I found** (open).
- **`no-db` / `db003`**: rescored without / with Lc0's "deblunder" (Q blunder threshold 0.10, width 0.03).
- Positions with castling flags in non-standard (Chess960/DFRC) games are filtered out (`filter_plain.py`).

## 2. The material scale in akimbo: search only, not training (this corrects Block D)

Read in `jw1912/akimbo`. `Position::scale()` (`eval * (700 + material/32) / 1024`) was introduced by `98ccad42f3`
("Replace Output Buckets with Material Scaling", SPRT +4.34 +/- 3.12 Elo vs the previous 8 output buckets chosen by piece
count) wrapped in `#[cfg(not(feature = "datagen"))]`: **the data-generation build returns the raw evaluation**, so the
labels the network was trained on were never scaled. The commit that introduced the network Luna embeds, `f65305c843`
(#208, 2024-03-27), deletes the datagen code entirely and the README says akimbo "now uses data produced by Leela Chess
Zero". `bullet` has no material-dependent output scaling in its training loop: material appears only as an **output-bucket
selector** (`MaterialCount<N>`, learned output weights per piece-count bucket); `eval_scale` is a single constant.

**So the factor sits on the search side.** A network trained by us can be trained normally on raw labels; the factor is then a
separate setting that must be re-measured with the new network (its 700/1024 floor and its divisor 32 are akimbo's).
The alternative that trains the same idea is `MaterialCount<N>` output buckets. The earlier statement that the factor is
"active during training" was wrong: see the erratum in the engine repository's `BENCHMARKS.md` (2026-09-25).

## 3. The measuring instrument: prepared, **blocked on the download**

The candidate is the Kaggle dataset `christofferbrandt/stockfish-position-evaluations` (one CSV, 40.96 MB, ~453,674 unique
FENs, Stockfish 18 depth 12 in multi-PV 5, `evaluation` = centipawns or `M<n>` from the side to move's point of view, terminal
positions excluded, **CC BY-SA 4.0**). **It could not be downloaded**: Kaggle answers 404 to an anonymous request, there is no
Kaggle credential on this machine and no mirror exists (searched). Nothing was invented in its place.

`pipeline/measure/measure_sf18_evalset.py` is ready and tested: it de-duplicates, excludes mate rows (counted), **verifies the
point of view on the data** (Black-to-move rows with a >= 400 cp material imbalance must agree with "the side to move is
ahead" and disagree with "White is ahead"; it stops otherwise), evaluates every position with each engine/network pair
in a private temporary folder, and reports Spearman rho on the full set, a bootstrap 95% CI, and the standard deviation of rho
over random subsets at each size (so resolution is measured, not assumed). Two engines are measured per network:
`v3.1.6` (raw output, as every earlier figure) and `v3.1.7` (with the material scale). **Test on a stand-in built from the old 2,000-position
set**: it reproduces the recorded 0.8522 (embedded, raw), 0.7005 (gen3) and 0.8518 (embedded, scaled) to four decimals.

To run once the CSV is on disk: `measure_sf18_evalset.py --csv <file> --out-dir <dir> --engine raw=<v3.1.6 exe> --engine
scaled=<v3.1.7 exe> --net embedded= --net gen1=nets/luna_gen1.nnue --net gen2=... --net gen3=...`. About 2,000 positions per
second per engine: a full pass of 450k positions is under 4 minutes per (engine, network) pair.

## Left out of this round, as instructed

The tool chain (bullet against the Python pipeline), the king buckets, downloading the large dataset, and any change to the old
11-million dataset, the CCRL PGN or the Lc0 files.
