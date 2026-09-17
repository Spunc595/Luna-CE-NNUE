"""
HalfKA NNUE model for Luna, matching src/nnue.rs's architecture:

  (768 x 4 king buckets) x 2 perspectives -> 1024 hidden (SCReLU) -> 1

Trained in a NORMALIZED float domain (accumulator clamped to [0,1], not
[0,QA]) so the model's output lands directly in real centipawn scale
during training — gradients stay well-scaled for a normal learning rate.
Quantization into nnue.rs's actual int16 "QA/QB units" happens only at
export time (see export.py), by multiplying through by QA/QB/QAB — NOT
during training. (An earlier version trained directly in quantized units
by dividing by QA/QAB inside forward(); that suppressed gradients by a
factor of SCALE/QAB =~ 0.0245 and made training practically not converge
within a reasonable number of epochs — don't reintroduce that.)
"""
import torch
import torch.nn as nn

NUM_BUCKETS = 4
HIDDEN = 1024
NUM_FEATURES = 768 * NUM_BUCKETS  # 3072 rows in the shared feature table

QA = 255
QB = 64
QAB = QA * QB
SCALE = 400


class LunaHalfKA(nn.Module):
    def __init__(self):
        super().__init__()
        # One shared feature-weight table (both perspectives read from
        # it, at different row indices) — matches nnue.rs's single
        # `feature_weights: Vec<i16>` of NUM_FEATURES rows, just not yet
        # scaled/quantized into that integer domain (see export.py).
        self.feature_weights = nn.EmbeddingBag(NUM_FEATURES, HIDDEN, mode="sum")
        self.feature_bias = nn.Parameter(torch.zeros(HIDDEN))
        # output_weights[0] pairs with the side-to-move's own half,
        # [1] with the opponent's — matches nnue.rs exactly.
        self.output_weights = nn.Parameter(torch.zeros(2, HIDDEN))
        self.output_bias = nn.Parameter(torch.zeros(1))

        # Standard NNUE-trainer init scale for a normalized [0,1]-clamped
        # accumulator: small enough that early accumulator values mostly
        # land inside the clamp's non-saturated region rather than
        # pegged at 0 or 1 (which would zero out gradients from the
        # start), not so small that the initial output is negligible.
        nn.init.uniform_(self.feature_weights.weight, -0.2, 0.2)

        # output_weights much smaller: with +-0.2 and ~2048 summed terms
        # (2 x HIDDEN) the initial output has a spread of roughly
        # ~450cp -> sigmoid(K*pred) spread over nearly all of [0,1] and
        # uncorrelated with the targets, initial MSE ~0.22 against a
        # target variance of ~0.087: the network starts worse than a
        # constant and spends the first epochs just recovering, instead
        # of learning from a base close to the mean. +-0.01 brings the
        # initial prediction near 0.5 (output_bias stays 0, never
        # touched by a separate init), so the gradient works on useful
        # signal right away. feature_weights is NOT touched: the problem
        # is the output amplitude multiplied by SCALE, not the
        # accumulator.
        nn.init.uniform_(self.output_weights, -0.01, 0.01)
        nn.init.zeros_(self.output_bias)

    def accumulate(self, indices: torch.Tensor, offsets: torch.Tensor) -> torch.Tensor:
        """indices/offsets: standard EmbeddingBag ragged-batch encoding
        of each position's active feature rows for ONE perspective."""
        return self.feature_weights(indices, offsets) + self.feature_bias

    def forward(self, us_idx, us_off, them_idx, them_off):
        us_acc = self.accumulate(us_idx, us_off)
        them_acc = self.accumulate(them_idx, them_off)

        # SCReLU on the NORMALIZED accumulator: clamp(x, 0, 1)^2 — the
        # "1" here is what QA=255 will become once feature_weights are
        # multiplied up at export time; the shape of the nonlinearity
        # (and therefore what the network learns) is identical either
        # way, only the training-time scale differs.
        us_screlu = us_acc.clamp(0, 1).pow(2)
        them_screlu = them_acc.clamp(0, 1).pow(2)

        sum_ = (us_screlu * self.output_weights[0]).sum(dim=1) \
             + (them_screlu * self.output_weights[1]).sum(dim=1)
        # SCALE calibrates this normalized-domain sum directly to
        # centipawns for training purposes; the QA/QB/QAB quantization
        # scaling is applied only when exporting to net.bin, not here.
        return sum_ * SCALE + self.output_bias * SCALE
