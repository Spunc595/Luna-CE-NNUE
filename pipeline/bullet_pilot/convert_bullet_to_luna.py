"""bullet raw.bin (f32: l0w[768][1024] feature-major, l0b[1024], l1w[2048] = stm|ntm, l1b[1]) -> Luna net.bin.

Trained with Chess768hm (own pieces 0..383, opponents 384..767, then 64*pt+sq; horizontal mirror when the perspective's
own king is on files e-h; Black perspective flips the rank), which is exactly Luna's per-bucket layout. The net has no king
buckets, so the 768 rows are replicated into all 4 Luna buckets. Every gate refuses (exit 1, no file written) instead of
clamping. Usage: convert_bullet_to_luna.py raw.bin net.bin
"""
import sys
import numpy as np

QA, QB, HIDDEN, NB = 255, 64, 1024, 4
I16MAX, I16MIN = 32767, -32768

raw = np.fromfile(sys.argv[1], dtype="<f4")
assert raw.size == 768 * HIDDEN + HIDDEN + 2 * HIDDEN + 1, raw.size
l0w = raw[:768 * HIDDEN].reshape(768, HIDDEN)
# MIRROR DIRECTION: bullet's Chess768hm flips (sq ^ 7) when the king is on files a-d (`our_ksq & 4 == 0`), i.e. it puts
# the king on the e-h half; Luna flips when the king is on e-h, i.e. it puts the king on a-d. The two conventions differ
# by exactly one file flip, so Luna's row (pt, sq) is bullet's row (pt, sq ^ 7).
l0w = l0w.reshape(12, 64, HIDDEN)[:, np.arange(64) ^ 7, :].reshape(768, HIDDEN)
l0b = raw[768 * HIDDEN:768 * HIDDEN + HIDDEN]
l1w = raw[768 * HIDDEN + HIDDEN:768 * HIDDEN + 3 * HIDDEN].reshape(2, HIDDEN)
l1b = raw[-1:]

q = lambda a, s: np.round(a.astype(np.float64) * s)
fw, fb, ow, ob = q(l0w, QA), q(l0b, QA), q(l1w, QB), q(l1b, QA * QB)
problems = []

sat = {n: int(((a >= I16MAX) | (a <= I16MIN)).sum()) for n, a in (("feature_weights", fw), ("feature_bias", fb), ("output_weights", ow), ("output_bias", ob))}
print("saturation (elements reaching i16 limits):", sat)
problems += [f"{n}: {c} saturated" for n, c in sat.items() if c]

# SIMD gate: 255 * |output weight| <= 32767 (AVX2/NEON truncating 16-bit multiply)
max_ow = int(np.abs(ow).max())
print(f"SIMD gate: max |output_weight| = {max_ow}; QA*max = {QA * max_ow} (limit {I16MAX}) -> {'OK' if QA * max_ow <= I16MAX else 'FAIL'}")
if QA * max_ow > I16MAX:
    problems.append("SIMD gate")

# accumulator gate: bias + 32 largest positives (and the mirror image) per neuron, in i16
fw32 = fw.astype(np.int64)
top = np.sort(fw32, axis=0)[-32:].clip(min=0).sum(axis=0)
bot = np.sort(fw32, axis=0)[:32].clip(max=0).sum(axis=0)
up, lo = fb.astype(np.int64) + top, fb.astype(np.int64) + bot
print(f"accumulator worst case: max {up.max():+d}, min {lo.min():+d} (limits {I16MAX:+d}/{I16MIN:+d}); "
      f"max|fw|={int(np.abs(fw).max())} max|fb|={int(np.abs(fb).max())}")
if up.max() > I16MAX or lo.min() < I16MIN:
    problems.append("accumulator bound")

if problems:
    print("REFUSED:", problems)
    sys.exit(1)

full = np.tile(fw.astype("<i2"), (NB, 1))  # bucket b, row 768*b + f
out = (full.tobytes() + fb.astype("<i2").tobytes() + ow.astype("<i2").tobytes() + ob.astype("<i2").tobytes() + bytes(62))
assert len(out) == 6_297_664, len(out)
open(sys.argv[2], "wb").write(out)
print("wrote", sys.argv[2], len(out), "bytes")
