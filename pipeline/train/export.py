"""
Esporta un checkpoint allenato (LunaHalfKA) nel formato binario esatto
che src/nnue.rs si aspetta: un dump raw, little-endian, senza header, di

  feature_weights (768*4*1024 i16)
  feature_bias    (1024 i16)
  output_weights  (2*1024 i16)
  output_bias     (1 i16)
  62 byte di padding finale (allineamento a 64 byte, mai letti)

Uso:
  python export.py --checkpoint checkpoint.pt --out net.bin
"""
import argparse
import array
import struct
import sys
import torch

sys.stdout.reconfigure(encoding="utf-8")  # evita crash su console Windows con le emoji sotto

from model import LunaHalfKA, NUM_FEATURES, HIDDEN, QA, QB, QAB


def to_i16_clamped(tensor: torch.Tensor, scale: float) -> torch.Tensor:
    """Moltiplica per il fattore di quantizzazione (QA per i pesi
    dell'accumulatore/bias, QB per i pesi di output, QAB per il bias di
    output — vedi la derivazione in model.py) e arrotonda a i16. Il
    modello è allenato in un dominio normalizzato float (vedi model.py);
    questa è l'UNICA conversione verso le unità intere che nnue.rs legge."""
    rounded = torch.round(tensor * scale)
    clamped = torch.clamp(rounded, -32768, 32767)
    return clamped.to(torch.int16)


def i16_tensor_to_le_bytes(tensor: torch.Tensor) -> bytes:
    """Converte un tensore int16 in byte little-endian, senza dipendere
    da numpy (non sempre disponibile nell'ambiente di allenamento)."""
    a = array.array("h", tensor.flatten().tolist())
    if sys.byteorder != "little":
        a.byteswap()
    return a.tobytes()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--out", default="net.bin")
    ap.add_argument("--alpha", type=float, default=1.0,
                     help="riscalatura post-training (verificaexport.md sez. successiva): "
                          "W->W/alpha, b->b/alpha, v->v*alpha^2. Esatta solo dove il clamp "
                          "SCReLU non morde (clamp(acc,0,1)==clamp(acc/alpha,0,1)) — le unita' "
                          "gia' clampate a 0 restano invarianti per costruzione, quelle vicine "
                          "al bordo superiore possono cambiare stato; verificare sempre con "
                          "verify_roundtrip.py, non fidarsi della sola algebra.")
    args = ap.parse_args()

    model = LunaHalfKA()
    ckpt = torch.load(args.checkpoint, map_location="cpu")
    # I checkpoint di train.py sono un dict (pesi + stato ottimizzatore/
    # scheduler + epoca); un vecchio state_dict "nudo" resta comunque
    # caricabile per compatibilita' con checkpoint precedenti a questo fix.
    state_dict = ckpt["model"] if isinstance(ckpt, dict) and "model" in ckpt else ckpt
    model.load_state_dict(state_dict)
    model.eval()

    alpha = args.alpha
    feature_weights_f = model.feature_weights.weight.detach() / alpha
    feature_bias_f = model.feature_bias.detach() / alpha
    output_weights_f = model.output_weights.detach() * (alpha ** 2)
    # output_bias non passa per il clamp SCReLU (si somma dopo): resta invariato.
    output_bias_f = model.output_bias.detach()

    feature_weights = to_i16_clamped(feature_weights_f, QA)  # (NUM_FEATURES, HIDDEN)
    feature_bias = to_i16_clamped(feature_bias_f, QA)        # (HIDDEN,)
    output_weights = to_i16_clamped(output_weights_f, QB)    # (2, HIDDEN)
    output_bias = to_i16_clamped(output_bias_f, QAB)         # (1,)

    assert feature_weights.shape == (NUM_FEATURES, HIDDEN)
    assert feature_bias.shape == (HIDDEN,)
    assert output_weights.shape == (2, HIDDEN)

    with open(args.out, "wb") as f:
        # feature_weights: row-major, riga per riga (768*4 righe di HIDDEN valori)
        f.write(i16_tensor_to_le_bytes(feature_weights))
        f.write(i16_tensor_to_le_bytes(feature_bias))
        f.write(i16_tensor_to_le_bytes(output_weights[0]))
        f.write(i16_tensor_to_le_bytes(output_weights[1]))
        f.write(struct.pack("<h", int(output_bias.item())))
        f.write(b"\x00" * 62)  # padding finale, mai letto da nnue.rs

    expected_size = NUM_FEATURES * HIDDEN * 2 + HIDDEN * 2 + 2 * HIDDEN * 2 + 2 + 62
    import os
    actual_size = os.path.getsize(args.out)
    status = "✅" if actual_size == expected_size else "❌ DIMENSIONE ERRATA"
    print(f"{status} {args.out}: {actual_size} byte (atteso: {expected_size})")

    # Controllo di sanità sui valori: se molti pesi sono clampati a
    # +/-32767 vuol dire che l'allenamento non è rimasto nel dominio
    # int16 previsto — segnale di qualcosa da rivedere in model.py/train.py.
    saturated = (feature_weights.abs() == 32767).float().mean().item()
    if saturated > 0.01:
        print(f"⚠️  {saturated*100:.1f}% dei pesi feature sono saturati a +/-32767 — controlla la scala di allenamento")

    # output_bias_i16 = ob_float * QAB (16320): satura a i16 quando
    # |ob_float| >= 32767/16320 ~= 2.008 (~803cp di bias costante).
    # Improbabile ma export.py lo clamperebbe in silenzio se succedesse —
    # controllato esplicitamente (verificaexport.md sez. 2.2).
    if abs(int(output_bias.item())) >= 32767:
        print("⚠️  output_bias saturato a i16 — |ob_float| >= 2.008, controlla il training")

    # Gate di sicurezza SIMD (vedi nnue.rs, MAX_SAFE_OUTPUT_WEIGHT): sopra
    # 128 i kernel AVX2/NEON troncano il prodotto intermedio a 16 bit e
    # calcolano valutazioni sbagliate in silenzio. Il motore rifiuta gia'
    # la rete da solo al caricamento, ma e' meglio saperlo qui.
    MAX_SAFE_OUTPUT_WEIGHT = 128
    max_output_weight = output_weights.abs().max().item()
    gate_status = "✅" if max_output_weight <= MAX_SAFE_OUTPUT_WEIGHT else "❌ OLTRE IL LIMITE SIMD-SAFE"
    print(f"{gate_status} max |output_weight| = {max_output_weight} (limite: {MAX_SAFE_OUTPUT_WEIGHT})")


if __name__ == "__main__":
    main()
