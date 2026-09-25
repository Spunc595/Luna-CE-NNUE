"""Usage: convert_bullet_to_luna.py raw.bin net.bin   (logic and gates live in bullet_luna.py)"""
import sys
import numpy as np
import bullet_luna as bl
try:
    data = bl.convert(np.fromfile(sys.argv[1], dtype="<f4"))
except bl.GateError as e:
    print("REFUSED:", e)
    sys.exit(1)
open(sys.argv[2], "wb").write(data)
print("wrote", sys.argv[2], len(data), "bytes")
