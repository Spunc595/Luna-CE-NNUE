"""Usage: convert_bullet_to_luna.py raw.bin net.bin --exe luna.exe   (or LUNA_EXE=...)

Gates AND the round-trip (2000 positions, independent reference vs the engine) run inside bullet_luna.convert_verified:
the file is written only if every gate passes and there is zero difference. Exit code 1 otherwise, no file created."""
import argparse
import os
import sys

import numpy as np

import bullet_luna as bl

ap = argparse.ArgumentParser()
ap.add_argument("raw")
ap.add_argument("out")
ap.add_argument("--exe", default=os.environ.get("LUNA_EXE"))
ap.add_argument("--n", type=int, default=2000)
a = ap.parse_args()
if not a.exe or not os.path.exists(a.exe):
    sys.exit("REFUSED: an engine executable is required for the round-trip (--exe or LUNA_EXE)")
try:
    n = bl.convert_verified(np.fromfile(a.raw, dtype="<f4"), a.out, a.exe, a.n)
except (bl.GateError, bl.RoundTripError) as e:
    print("REFUSED:", e)
    sys.exit(1)
print(f"round-trip OK ({n} positions, 0 differences); wrote {a.out}")
