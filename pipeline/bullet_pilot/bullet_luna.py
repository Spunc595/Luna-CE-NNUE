"""bullet (Chess768hm, no buckets, (768->1024)x2->1) checkpoint -> Luna net.bin, plus an independent reference inference.

convert(): the conversion, including the mirror-direction permutation (`mirror_fix`). The reference (`Reference`) is written
from bullet's Chess768hm definition only and never reads Luna's code or the converted file: it is the independent side of
the round-trip. `mirror_fix=False` exists ONLY so the test can prove that the round-trip fails without the permutation.
"""
import numpy as np

QA, QB, HIDDEN, NB = 255, 64, 1024, 4
I16MAX, I16MIN = 32767, -32768
RAW_FLOATS = 768 * HIDDEN + HIDDEN + 2 * HIDDEN + 1


class GateError(Exception):
    pass


def convert(raw_f32, mirror_fix=True):
    """raw_f32: flat f32 array (l0w[768][1024] feature-major, l0b, l1w[2][1024] = stm|ntm, l1b). Returns net.bin bytes,
    or raises GateError (nothing is clamped silently)."""
    raw = np.asarray(raw_f32, dtype="<f4")
    assert raw.size == RAW_FLOATS, raw.size
    l0w = raw[:768 * HIDDEN].reshape(768, HIDDEN)
    if mirror_fix:
        # bullet's Chess768hm flips (sq ^ 7) when the king is on files a-d (`our_ksq & 4 == 0`) -> king on e-h; Luna flips
        # when the king is on e-h -> king on a-d. They differ by one file flip: Luna row (pt, sq) = bullet row (pt, sq ^ 7).
        l0w = l0w.reshape(12, 64, HIDDEN)[:, np.arange(64) ^ 7, :].reshape(768, HIDDEN)
    l0b = raw[768 * HIDDEN:769 * HIDDEN]
    l1w = raw[769 * HIDDEN:771 * HIDDEN].reshape(2, HIDDEN)
    l1b = raw[-1:]
    q = lambda a, s: np.round(a.astype(np.float64) * s)
    fw, fb, ow, ob = q(l0w, QA), q(l0b, QA), q(l1w, QB), q(l1b, QA * QB)
    problems = []
    for n, a in (("feature_weights", fw), ("feature_bias", fb), ("output_weights", ow), ("output_bias", ob)):
        c = int(((a >= I16MAX) | (a <= I16MIN)).sum())
        if c:
            problems.append(f"{n}: {c} saturated")
    if QA * int(np.abs(ow).max()) > I16MAX:  # SIMD gate
        problems.append("SIMD gate: 255 * max|output weight| > 32767")
    w = fw.astype(np.int64)
    up = fb.astype(np.int64) + np.sort(w, axis=0)[-32:].clip(min=0).sum(axis=0)
    lo = fb.astype(np.int64) + np.sort(w, axis=0)[:32].clip(max=0).sum(axis=0)
    if up.max() > I16MAX or lo.min() < I16MIN:
        problems.append(f"accumulator bound: max {up.max()} min {lo.min()}")
    if problems:
        raise GateError("; ".join(problems))
    out = (np.tile(fw.astype("<i2"), (NB, 1)).tobytes() + fb.astype("<i2").tobytes() + ow.astype("<i2").tobytes()
           + ob.astype("<i2").tobytes() + bytes(62))
    assert len(out) == 6_297_664
    return out


_PT = {c: i for i, c in enumerate("pnbrqk")}


def _features(fen):
    bd, stm = fen.split()[0], fen.split()[1]
    pcs = []  # (0 = side to move's piece / 1 = opponent's, piece type, square in the stm-relative frame)
    for r, row in enumerate(bd.split("/")):
        f = 0
        for ch in row:
            if ch.isdigit():
                f += int(ch)
                continue
            sq = (7 - r) * 8 + f
            if stm == "b":
                sq ^= 56
            pcs.append((0 if ch.isupper() == (stm == "w") else 1, _PT[ch.lower()], sq))
            f += 1
    ks = [s for c, p, s in pcs if p == 5 and c == 0][0]
    kn = [s for c, p, s in pcs if p == 5 and c == 1][0]
    hs, hn = (0 if ks & 4 else 7), (0 if kn & 4 else 7)   # bullet's Chess768hm, verbatim
    return ([[0, 384][c] + 64 * p + (s ^ hs) for c, p, s in pcs],
            [[384, 0][c] + 64 * p + (s ^ hn ^ 56) for c, p, s in pcs])


class Reference:
    def __init__(self, raw_f32):
        raw = np.asarray(raw_f32, dtype="<f4")
        q = lambda a, s: np.round(a.astype(np.float64) * s).astype(np.int64)
        self.W = q(raw[:768 * HIDDEN].reshape(768, HIDDEN), QA)
        self.B = q(raw[768 * HIDDEN:769 * HIDDEN], QA)
        self.OW = q(raw[769 * HIDDEN:771 * HIDDEN].reshape(2, HIDDEN), QB)
        self.OB = int(q(raw[-1:], QA * QB)[0])

    def eval(self, fen):
        s = 0
        for k, idx in enumerate(_features(fen)):
            c = np.clip(self.B + self.W[idx].sum(axis=0), 0, QA)
            s += int((c * c * self.OW[k]).sum())
        out = int(s / QA) + self.OB   # truncation toward zero, like Rust's i32 division
        return max(-15000, min(15000, int(out * 400 / (QA * QB))))


def luna_eval(exe, net_path, fens):
    """Luna's own static `eval` (no search) for each FEN; exe copied into a private folder with the net as luna.nnue."""
    import os
    import shutil
    import subprocess
    import tempfile
    tmp = tempfile.mkdtemp(prefix="luna_rt_")
    try:
        e = os.path.join(tmp, os.path.basename(exe))
        shutil.copy2(exe, e)
        shutil.copy2(net_path, os.path.join(tmp, "luna.nnue"))
        p = subprocess.Popen([e], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1, cwd=tmp,
                             encoding="utf-8", errors="replace")

        def rd(pref):
            while True:
                line = p.stdout.readline()
                if not line:
                    raise RuntimeError("engine ended early")
                if line.startswith(pref):
                    return line

        p.stdin.write("uci\n")
        rd("uciok")
        out = []
        for fen in fens:
            p.stdin.write(f"position fen {fen}\neval\n")
            out.append(int(float(rd("Evaluation:").split()[1])))
        p.stdin.write("quit\n")
        p.wait(timeout=10)
        return out
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def sample_positions(n, seed=7):
    """Seeded random legal positions (both colours to move, kings on every half of the board)."""
    import random
    import chess
    rng = random.Random(seed)
    out = []
    while len(out) < n:
        b = chess.Board()
        for _ in range(rng.randint(6, 90)):
            m = list(b.legal_moves)
            if not m:
                break
            b.push(rng.choice(m))
        if not b.is_game_over() and not b.is_check():
            out.append(b.fen())
    return out


class RoundTripError(Exception):
    pass


def convert_verified(raw_f32, out_path, exe, n=2000, seed=11):
    """The only sanctioned way to produce a net.bin: convert (all gates), then evaluate `n` positions with the independent
    reference and with the engine `exe` loading the converted bytes as luna.nnue, and write `out_path` ONLY if there is not
    one single difference. There is no path from a checkpoint to a file that skips the round-trip."""
    import os
    import tempfile
    data = convert(raw_f32)
    fens = sample_positions(n, seed)
    ref = Reference(raw_f32)
    expected = [ref.eval(f) for f in fens]
    fd, tmp = tempfile.mkstemp(suffix=".nnue")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        got = luna_eval(exe, tmp, fens)
    finally:
        os.unlink(tmp)
    diffs = [i for i, (a, b) in enumerate(zip(expected, got)) if a != b]
    if len(got) != len(fens) or diffs:
        raise RoundTripError(f"round-trip FAILED: {len(diffs)} of {len(fens)} positions differ (first {diffs[:5]}); {out_path} not written")
    with open(out_path, "wb") as f:
        f.write(data)
    return len(fens)
