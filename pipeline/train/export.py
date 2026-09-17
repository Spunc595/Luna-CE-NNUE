"""
Exports a trained checkpoint (LunaHalfKA) into the exact binary format
src/nnue.rs expects: a raw, little-endian dump, no header, of

  feature_weights (768*4*1024 i16)
  feature_bias    (1024 i16)
  output_weights  (2*1024 i16)
  output_bias     (1 i16)
  62 bytes of trailing padding (64-byte alignment, never read)

Usage:
  python export.py --checkpoint checkpoint.pt --out net.bin
"""
import argparse
import array
import struct
import sys
import torch

sys.stdout.reconfigure(encoding="utf-8")  # avoids a crash on Windows consoles with the emoji below

from model import LunaHalfKA, NUM_FEATURES, HIDDEN, QA, QB, QAB


def to_i16_clamped(tensor: torch.Tensor, scale: float) -> torch.Tensor:
    """Multiplies by the quantization factor (QA for accumulator/bias
    weights, QB for output weights, QAB for the output bias — see the
    derivation in model.py) and rounds to i16. The model is trained in a
    normalized float domain (see model.py); this is the ONLY conversion
    toward the integer units that nnue.rs reads."""
    rounded = torch.round(tensor * scale)
    clamped = torch.clamp(rounded, -32768, 32767)
    return clamped.to(torch.int16)


def i16_tensor_to_le_bytes(tensor: torch.Tensor) -> bytes:
    """Converts an int16 tensor to little-endian bytes, without depending
    on numpy (not always available in the training environment)."""
    a = array.array("h", tensor.flatten().tolist())
    if sys.byteorder != "little":
        a.byteswap()
    return a.tobytes()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--out", default="net.bin")
    ap.add_argument("--alpha", type=float, default=1.0,
                     help="riscalatura post-training: "
                          "W->W/alpha, b->b/alpha, v->v*alpha^2. Esatta solo dove il clamp "
                          "SCReLU non morde (clamp(acc,0,1)==clamp(acc/alpha,0,1)) — le unita' "
                          "gia' clampate a 0 restano invarianti per costruzione, quelle vicine "
                          "al bordo superiore possono cambiare stato; verificare sempre con "
                          "verify_roundtrip.py, non fidarsi della sola algebra.")
    args = ap.parse_args()

    model = LunaHalfKA()
    ckpt = torch.load(args.checkpoint, map_location="cpu")
    # train.py's checkpoints are a dict (weights + optimizer/scheduler
    # state + epoch); an old "bare" state_dict is still loadable for
    # compatibility with checkpoints predating this fix.
    state_dict = ckpt["model"] if isinstance(ckpt, dict) and "model" in ckpt else ckpt
    model.load_state_dict(state_dict)
    model.eval()

    alpha = args.alpha
    feature_weights_f = model.feature_weights.weight.detach() / alpha
    feature_bias_f = model.feature_bias.detach() / alpha
    output_weights_f = model.output_weights.detach() * (alpha ** 2)
    # output_bias doesn't go through the SCReLU clamp (added afterward): stays unchanged.
    output_bias_f = model.output_bias.detach()

    feature_weights = to_i16_clamped(feature_weights_f, QA)  # (NUM_FEATURES, HIDDEN)
    feature_bias = to_i16_clamped(feature_bias_f, QA)        # (HIDDEN,)
    output_weights = to_i16_clamped(output_weights_f, QB)    # (2, HIDDEN)
    output_bias = to_i16_clamped(output_bias_f, QAB)         # (1,)

    assert feature_weights.shape == (NUM_FEATURES, HIDDEN)
    assert feature_bias.shape == (HIDDEN,)
    assert output_weights.shape == (2, HIDDEN)

    with open(args.out, "wb") as f:
        # feature_weights: row-major, row by row (768*4 rows of HIDDEN values)
        f.write(i16_tensor_to_le_bytes(feature_weights))
        f.write(i16_tensor_to_le_bytes(feature_bias))
        f.write(i16_tensor_to_le_bytes(output_weights[0]))
        f.write(i16_tensor_to_le_bytes(output_weights[1]))
        f.write(struct.pack("<h", int(output_bias.item())))
        f.write(b"\x00" * 62)  # trailing padding, never read by nnue.rs

    expected_size = NUM_FEATURES * HIDDEN * 2 + HIDDEN * 2 + 2 * HIDDEN * 2 + 2 + 62
    import os
    actual_size = os.path.getsize(args.out)
    status = "✅" if actual_size == expected_size else "❌ DIMENSIONE ERRATA"
    print(f"{status} {args.out}: {actual_size} byte (atteso: {expected_size})")

    # Sanity check on the values: if many weights are clamped to
    # +/-32767 it means training didn't stay within the expected int16
    # domain — a signal something needs revisiting in model.py/train.py.
    saturated = (feature_weights.abs() == 32767).float().mean().item()
    if saturated > 0.01:
        print(f"⚠️  {saturated*100:.1f}% dei pesi feature sono saturati a +/-32767 — controlla la scala di allenamento")

    # output_bias_i16 = ob_float * QAB (16320): saturates to i16 when
    # |ob_float| >= 32767/16320 ~= 2.008 (~803cp of constant bias).
    # Unlikely but export.py would silently clamp it if it happened —
    # checked explicitly.
    if abs(int(output_bias.item())) >= 32767:
        print("⚠️  output_bias saturato a i16 — |ob_float| >= 2.008, controlla il training")

    # SIMD safety gate (see nnue.rs, MAX_SAFE_OUTPUT_WEIGHT): above 128
    # the AVX2/NEON kernels truncate the intermediate product to 16 bits
    # and silently compute wrong evaluations. The engine already refuses
    # the net on its own at load time, but better to know here too.
    MAX_SAFE_OUTPUT_WEIGHT = 128
    max_output_weight = output_weights.abs().max().item()
    gate_status = "✅" if max_output_weight <= MAX_SAFE_OUTPUT_WEIGHT else "❌ OLTRE IL LIMITE SIMD-SAFE"
    print(f"{gate_status} max |output_weight| = {max_output_weight} (limite: {MAX_SAFE_OUTPUT_WEIGHT})")


if __name__ == "__main__":
    main()
