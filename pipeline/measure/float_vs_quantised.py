"""Float forward pass (numpy) of a bullet checkpoint vs the quantised Luna evaluation, on the SF18 evaluation set.

Question (hypothesis 3, "the quantisation limit"): does the i16 quantisation (QA 255, QB 64, output clip about +-1.98) cost ranking
quality? Float net = raw.bin (f32) evaluated with bullet's own Chess768hm mapping and float SCReLU clamp(x,0,1)^2, two perspectives,
output * 400 = centipawns (eval_scale 400). Quantised = the outputs Luna itself produced (eval_raw_<label>.txt of
measure_sf18_evalset.py, engine v3.1.6 = raw output, no material scale).

usage: float_vs_quantised.py CSV raw.bin quantised_eval.txt OUT_float_eval.txt
Gate BEFORE believing any Spearman: float and quantised evaluations must be close position by position (median / max |difference| in cp
on the first 2,000 rows and on all rows); if not, this implementation is wrong and the comparison measures the bug."""
import sys

import numpy as np

sys.path.insert(0, __file__.rsplit("measure", 1)[0].replace("\\", "/") + "measure")
sys.path.insert(0, __file__.rsplit("measure", 1)[0].replace("\\", "/") + "bullet_pilot")
from measure_sf18_evalset import load, spearman  # noqa: E402
import bullet_luna as bl  # noqa: E402

csv_path, raw_path, quant_path, out_path = sys.argv[1:5]
H = 1024
cp_rows, _, _ = load(csv_path)
fens = [f for f, _ in cp_rows]
sf = np.array([c for _, c in cp_rows], float)
quant = np.loadtxt(quant_path)
assert len(quant) == len(fens)

raw = np.fromfile(raw_path, dtype="<f4")
W = np.vstack([raw[:768 * H].reshape(768, H), np.zeros((1, H), np.float32)])   # row 768 = zeros (padding)
B = raw[768 * H:769 * H]
OW = raw[769 * H:771 * H].reshape(2, H)
OB = float(raw[-1])

out = np.empty(len(fens), np.float64)
BATCH = 1024
for s in range(0, len(fens), BATCH):
    chunk = fens[s:s + BATCH]
    ia = np.full((len(chunk), 32), 768, np.int64)
    ib = np.full((len(chunk), 32), 768, np.int64)
    for k, fen in enumerate(chunk):
        a, b = bl._features(fen)          # bullet's Chess768hm, verbatim (NOT Luna's mirrored rows: the weights are bullet's)
        ia[k, :len(a)] = a
        ib[k, :len(b)] = b
    tot = np.zeros(len(chunk), np.float64)
    for k, idx in enumerate((ia, ib)):
        acc = B + W[idx].sum(axis=1)                     # float32 (n, 1024)
        act = np.clip(acc, 0.0, 1.0) ** 2                # float SCReLU: clamp at 1, not at QA
        tot += (act @ OW[k]).astype(np.float64)
    out[s:s + len(chunk)] = (tot + OB) * 400.0
    if (s // BATCH) % 50 == 0:
        print(f"{s}/{len(fens)}", file=sys.stderr, flush=True)
np.savetxt(out_path, out, fmt="%.3f")

d = np.abs(out - quant)
for label, sl in (("first 2,000 rows", slice(0, 2000)), ("all rows", slice(None))):
    print(f"GATE float vs quantised, {label}: median |diff| = {np.median(d[sl]):.2f} cp, 95th = {np.percentile(d[sl], 95):.2f} cp, "
          f"max = {d[sl].max():.1f} cp; median |eval| = {np.median(np.abs(quant[sl])):.0f} cp; mean signed (float - quant) = {np.mean((out - quant)[sl]):+.2f} cp")
print(f"Spearman vs SF18: float = {spearman(out, sf):.4f}   quantised = {spearman(quant, sf):.4f}   (n = {len(sf)})")
