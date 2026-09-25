"""Independent reference inference (numpy, from bullet's Chess768hm definition and the raw.bin quantised by our converter)
vs Luna's own `eval` on N positions of the SF18 CSV. Reference never reads Luna code or net.bin."""
import sys, csv, subprocess, os, shutil, tempfile
import numpy as np
raw = np.fromfile(sys.argv[1], dtype="<f4"); exe = sys.argv[2]; net = sys.argv[3]; N = int(sys.argv[4])
H = 1024
q = lambda a, s: np.round(a.astype(np.float64) * s).astype(np.int64)
W = q(raw[:768*H].reshape(768, H), 255); B = q(raw[768*H:769*H], 255)
OW = q(raw[769*H:771*H].reshape(2, H), 64); OB = int(q(raw[-1:], 255*64)[0])
PT = {c: i for i, c in enumerate("pnbrqk")}
def feats(fen):
    bd, stm = fen.split()[0], fen.split()[1]
    pcs = []  # (relative colour c: 0 = side to move, piece type, square in stm-relative frame)
    for r, row in enumerate(bd.split("/")):
        f = 0
        for ch in row:
            if ch.isdigit(): f += int(ch); continue
            sq = (7 - r) * 8 + f; white = ch.isupper()
            own = white == (stm == "w")
            if stm == "b": sq ^= 56
            pcs.append((0 if own else 1, PT[ch.lower()], sq)); f += 1
    ks = [s for c, p, s in pcs if p == 5 and c == 0][0]; kn = [s for c, p, s in pcs if p == 5 and c == 1][0]
    hs = 0 if (ks & 4) else 7; hn = 0 if (kn & 4) else 7
    a = [[0, 384][c] + 64*p + (s ^ hs) for c, p, s in pcs]
    b = [[384, 0][c] + 64*p + (s ^ hn ^ 56) for c, p, s in pcs]
    return a, b
def ref(fen):
    a, b = feats(fen)
    s = 0
    for k, idx in enumerate((a, b)):
        acc = (B + W[idx].sum(axis=0)); assert acc.min() > -32768 and acc.max() < 32767
        c = np.clip(acc, 0, 255); s += int((c*c*OW[k]).sum())
    out = int(s / 255) + OB          # truncation toward zero, as Rust i32 division
    return max(-15000, min(15000, int(out * 400 / (255*64))))
fens = []
with open(sys.argv[5], newline="") as f:
    for r in csv.DictReader(f):
        fens.append(r["fen"].strip())
        if len(fens) == N: break
tmp = tempfile.mkdtemp(); shutil.copy(exe, tmp + "/luna.exe"); shutil.copy(net, tmp + "/luna.nnue")
p = subprocess.Popen([tmp + "/luna.exe"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, cwd=tmp, bufsize=1, encoding="utf-8", errors="replace")
def rd(pref):
    while True:
        l = p.stdout.readline()
        if l.startswith(pref): return l
p.stdin.write("uci\n"); rd("uciok"); out = []
for fen in fens:
    p.stdin.write(f"position fen {fen}\neval\n"); out.append(int(float(rd("Evaluation:").split()[1])))
p.stdin.write("quit\n"); p.wait()
mine = [ref(f) for f in fens]
d = [abs(a - b) for a, b in zip(mine, out)]
print(f"positions: {len(fens)}, differences (reference vs Luna eval): {sum(x != 0 for x in d)}, max |diff| = {max(d)}")
print("sample ref/luna:", list(zip(mine[:5], out[:5])))
