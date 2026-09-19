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


I16_MAX = 32767
I16_MIN = -32768
MAX_ACTIVE_FEATURES = 32  # one feature per piece, at most 32 pieces on the board


def quantize_i16(tensor: torch.Tensor, scale: float):
    """Multiplies by the quantization factor (QA for accumulator/bias
    weights, QB for output weights, QAB for the output bias — see the
    derivation in model.py) and rounds to i16. The model is trained in a
    normalized float domain (see model.py); this is the ONLY conversion
    toward the integer units that nnue.rs reads.

    Returns (int16 tensor, number of saturated elements). An element counts
    as saturated if the rounded value REACHES either end of the i16 range
    (>= 32767 or <= -32768), i.e. if clamping altered it or it sits exactly on
    the clamp: the exported value is then not the checkpoint's value."""
    rounded = torch.round(tensor * scale)
    saturated = int(((rounded >= I16_MAX) | (rounded <= I16_MIN)).sum().item())
    clamped = torch.clamp(rounded, I16_MIN, I16_MAX)
    return clamped.to(torch.int16), saturated


def accumulator_bounds(feature_weights: torch.Tensor, feature_bias: torch.Tensor,
                       max_active: int = MAX_ACTIVE_FEATURES):
    """Worst-case i16 accumulator value per neuron, for any position.

    The engine's accumulator for neuron j is feature_bias[j] plus the weights
    of the active features of one perspective; a position has at most
    `max_active` of them (32 pieces). The upper bound is therefore the bias
    plus the `max_active` largest POSITIVE weights of column j (negative
    weights can only lower it); the lower bound is the bias plus the
    `max_active` most negative weights. Computed in int32 so the bound itself
    cannot overflow. This ignores which feature sets can co-occur, so it is a
    true upper limit, not a tight one.

    Returns (upper[HIDDEN], lower[HIDDEN]) as int32 tensors."""
    w = feature_weights.to(torch.int32)            # (NUM_FEATURES, HIDDEN)
    bias = feature_bias.to(torch.int32)            # (HIDDEN,)
    top = torch.topk(w, max_active, dim=0).values.clamp(min=0).sum(dim=0)
    bottom = torch.topk(w, max_active, dim=0, largest=False).values.clamp(max=0).sum(dim=0)
    return bias + top, bias + bottom


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
                     help="post-training rescaling: "
                          "W->W/alpha, b->b/alpha, v->v*alpha^2. Exact only where the SCReLU clamp "
                          "does not bite (clamp(acc,0,1)==clamp(acc/alpha,0,1)) — units "
                          "already clamped to 0 stay invariant by construction, those near "
                          "the upper edge can change state; always verify with "
                          "verify_roundtrip.py, do not trust the algebra alone.")
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

    feature_weights, sat_fw = quantize_i16(feature_weights_f, QA)  # (NUM_FEATURES, HIDDEN)
    feature_bias, sat_fb = quantize_i16(feature_bias_f, QA)        # (HIDDEN,)
    output_weights, sat_ow = quantize_i16(output_weights_f, QB)    # (2, HIDDEN)
    output_bias, sat_ob = quantize_i16(output_bias_f, QAB)         # (1,)

    assert feature_weights.shape == (NUM_FEATURES, HIDDEN)
    assert feature_bias.shape == (HIDDEN,)
    assert output_weights.shape == (2, HIDDEN)

    # EXPORT GATE, before a single byte is written: a candidate network whose
    # exported values differ from the checkpoint's (saturation) must not be
    # exportable silently. Zero saturated elements on ALL FOUR tensors, or the
    # export is refused with a non-zero exit code and no file is created.
    print("quantization saturation (elements reaching the i16 limits): "
          f"feature_weights={sat_fw} feature_bias={sat_fb} output_weights={sat_ow} output_bias={sat_ob}")
    problems = []
    for name, count in (("feature_weights", sat_fw), ("feature_bias", sat_fb),
                        ("output_weights", sat_ow), ("output_bias", sat_ob)):
        if count:
            problems.append(f"{name}: {count} element(s) saturate at the i16 limits")

    # ACCUMULATOR GATE: the accumulator is stored in i16 and summed without
    # overflow checks, so for EVERY neuron the worst-case sum (bias plus the 32
    # largest positive weights of its column, and the downward analogue) must
    # stay inside the i16 range. Saturation of single weights is checked above;
    # this checks their SUM.
    upper, lower = accumulator_bounds(feature_weights, feature_bias)
    acc_max, acc_min = int(upper.max().item()), int(lower.min().item())
    margin_up, margin_down = I16_MAX - acc_max, acc_min - I16_MIN
    print(f"max |feature_weight| = {int(feature_weights.abs().to(torch.int32).max().item())}, "
          f"max |feature_bias| = {int(feature_bias.abs().to(torch.int32).max().item())}")
    print(f"accumulator worst case (32 features): max = {acc_max:+d}, min = {acc_min:+d}; "
          f"margin to i16 limits: up {margin_up} ({I16_MAX / max(acc_max, 1):.1f}x), "
          f"down {margin_down} ({-I16_MIN / max(-acc_min, 1):.1f}x)")
    if margin_up < 0:
        n = int((upper > I16_MAX).sum().item())
        problems.append(f"accumulator upper bound {acc_max} exceeds {I16_MAX} ({n} neuron(s))")
    if margin_down < 0:
        n = int((lower < I16_MIN).sum().item())
        problems.append(f"accumulator lower bound {acc_min} is below {I16_MIN} ({n} neuron(s))")

    # SIMD GATE (nnue.rs, MAX_SAFE_OUTPUT_WEIGHT): above 128 the AVX2/NEON
    # kernels truncate the intermediate product to 16 bits and silently compute
    # wrong evaluations (255 * 128 = 32640 still fits in i16; 255 * 129 does not
    # in the worst case). The engine refuses such a net at load time; refusing
    # it here means it is never produced.
    MAX_SAFE_OUTPUT_WEIGHT = 128
    max_output_weight = int(output_weights.to(torch.int32).abs().max().item())
    print(f"max |output_weight| = {max_output_weight} (SIMD-safe limit: {MAX_SAFE_OUTPUT_WEIGHT})")
    if max_output_weight > MAX_SAFE_OUTPUT_WEIGHT:
        problems.append(f"output weight {max_output_weight} exceeds the SIMD-safe limit {MAX_SAFE_OUTPUT_WEIGHT}")

    if problems:
        print("EXPORT REFUSED (no file written): " + "; ".join(problems), file=sys.stderr)
        sys.exit(1)

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
    status = "✅" if actual_size == expected_size else "❌ WRONG SIZE"
    print(f"{status} {args.out}: {actual_size} bytes (expected: {expected_size})")


if __name__ == "__main__":
    main()
