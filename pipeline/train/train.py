"""
Trains Luna's HalfKA network (768x4 king-bucket x2 perspectives -> 1024
hidden -> 1) on TSV or binary datasets.

Input formats (dataset.py reads ONLY the 5-column layout):
  * 5-column TSV (fen, eval_cp, bestmove, wdl_mover, nodes): what the gen1-gen3
    datasets use. Produced by extract_positions.py -> annotate_incremental_gen*
    (the WDL correction of truncated games lives inside the annotator) ->
    pipeline/dataset/build_training_dataset_gen*.py (per-game train/val split,
    seed 42, val fraction 0.025).
  * binary (--format binary): convert_to_binary.py output of the above.

The older 6-column chain (fen, result, game_id, eval_cp, is_mate, bestmove:
extract_positions.py -> annotate_positions.py -> resolve_truncated_wdl.py ->
split_train_val.py) is published in pipeline/dataset/ for the record; its
output is NOT readable by this train.py as it stands.

Usage:
  python train.py --train train.tsv --val val.tsv --epochs 3 --out checkpoint.pt

A GPU is used if found; all published networks (gen1-gen3) were trained
on CPU, see LINEAGE.md. After
training, use export.py to produce a net.bin compatible with
src/nnue.rs.
"""
import argparse
import csv
import math
import os
import sys
import time

import chess
import torch
from torch.utils.data import DataLoader

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)  # emoji on Windows + readable log
# in real time even when stdout is redirected to a file (nohup ...
# > log 2>&1): without line_buffering, Python buffers in blocks when
# not writing to a terminal, and the three preflight numbers (needed
# for a report RIGHT AWAY, not at the end of the run) stay invisible
# for hours.

from model import LunaHalfKA
from dataset import HalfKADataset, collate_fn, K, TARGET_EVAL_CLAMP_CP
from binary_dataset import BinaryHalfKADataset, binary_collate_fn
from feature_set import active_features

# Classical material values, difference from the side-to-move's point
# of view -- same convention as the targets: needed for preflight, not
# for training.
PIECE_VALUES = {chess.PAWN: 100, chess.KNIGHT: 320, chess.BISHOP: 330,
                 chess.ROOK: 500, chess.QUEEN: 900, chess.KING: 0}

# Threshold for the sanity assert on the freshly-initialized model: a
# properly initialized net starts at ~1.0x the variance (measured: 0.088
# vs 0.087), the broken one (output_weights too large) started at ~2.5x
# (0.22 vs 0.087) -- 1.5x leaves margin for statistical noise without
# letting an initialization regression through.
UNTRAINED_MSE_MAX_RATIO = 1.5

# Clipping limit on weights in the normalized float domain: guarantees
# |weight_i16| = |weight_float * QB| <= 1.98*64 = 126.7 -> nnue.rs's
# SIMD-safe gate (threshold 128) can never trip, instead of discovering
# it after 20 epochs on Colab. The embedded akimbo net
# reaches |weight_i16|=126 (weight_float~1.97): real nets skim the
# limit, they don't skim it closely by accident.
WEIGHT_CLIP = 1.98


LR_MIN = 1e-5  # decays to ~1e-5, not to zero


def make_scheduler(optimizer, epochs):
    # Cosine decay over the whole training duration down to LR_MIN
    # (not to zero): no extra hyperparameter to tune, suits a short run
    # just as well as a long one.
    return torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=max(epochs, 1), eta_min=LR_MIN)


def count_clamped_weights(model):
    # How many weights actually hit the +/-WEIGHT_CLIP clamp: expected
    # zero or close to it. If many did, the clamp is distorting
    # training, not just protecting the SIMD gate.
    with torch.no_grad():
        fw = model.feature_weights.weight
        ow = model.output_weights
        n_fw = (fw.abs() >= WEIGHT_CLIP).sum().item()
        n_ow = (ow.abs() >= WEIGHT_CLIP).sum().item()
    return n_fw, n_ow


def sigmoid_loss(pred_cp, target_prob, loss_fn):
    # pred_cp is forward()'s raw output in centipawns (correct as is,
    # don't touch model.py — see the comment there). target_prob is
    # already in [0,1] (dataset.py). The SAME K transforms the
    # prediction into the same scale as the target before comparing: if
    # the two K's diverged the loss would compare two different spaces.
    pred_prob = torch.sigmoid(K * pred_cp)
    return loss_fn(pred_prob, target_prob)


def make_dataset(paths, fmt, eval_lambda):
    """fmt="tsv": paths sono file .tsv (fen/eval_cp/bestmove/wdl_mover/depth),
    parsati riga per riga -- lento, ma non richiede conversione.
    fmt="binary": paths sono prefissi prodotti da convert_to_binary.py
    (.us.npy/.them.npy/.targets.npy) -- ~11x piu' veloce (misurato:
    6.982 contro 78.193 posizioni/secondo), perche' salta il parsing TSV
    e la costruzione di una
    chess.Board() per ogni riga. Un solo prefisso binario per chiamata
    (a differenza del TSV, che accetta piu' file)."""
    if fmt == "binary":
        assert isinstance(paths, str) or len(paths) == 1, \
            "formato binary: un solo prefisso per volta (converti e concatena a monte se servono piu' shard)"
        prefix = paths if isinstance(paths, str) else paths[0]
        return BinaryHalfKADataset(prefix), binary_collate_fn
    return HalfKADataset(paths, eval_lambda=eval_lambda), collate_fn


def evaluate(model, val_paths, eval_lambda, batch_size, device, loss_fn, fmt="tsv"):
    if not val_paths:
        return None
    model.eval()
    dataset, cfn = make_dataset(val_paths, fmt, eval_lambda)
    loader = DataLoader(dataset, batch_size=batch_size, collate_fn=cfn, num_workers=0)
    total_loss, n_batches = 0.0, 0
    with torch.no_grad():
        for us_idx, us_off, them_idx, them_off, targets in loader:
            us_idx, us_off = us_idx.to(device), us_off.to(device)
            them_idx, them_off = them_idx.to(device), them_off.to(device)
            targets = targets.to(device)
            pred = model(us_idx, us_off, them_idx, them_off)
            total_loss += sigmoid_loss(pred, targets, loss_fn).item()
            n_batches += 1
    model.train()
    return total_loss / max(n_batches, 1)


def _material_diff_mover_pov(fen: str) -> int:
    board = chess.Board(fen)
    white_mat = sum(PIECE_VALUES[p.piece_type] for p in board.piece_map().values() if p.color == chess.WHITE)
    black_mat = sum(PIECE_VALUES[p.piece_type] for p in board.piece_map().values() if p.color == chess.BLACK)
    diff = white_mat - black_mat
    return diff if board.turn == chess.WHITE else -diff


def preflight_checks(model, val_paths, eval_lambda, device):
    """Tre numeri prima di qualunque epoca: varianza dei target
    (predittore costante), MSE del solo
    materiale, MSE del modello appena inizializzato. Avrebbero intercettato
    subito sia il bug us/them (val mai sotto il primo) sia
    l'inizializzazione fuori scala (il terzo a 0.22 invece di ~0.087) senza
    aspettare trenta epoche o una finestra GPU."""
    if not val_paths:
        print("Preflight: nessun validation set, salto i tre numeri.")
        return

    paths = [val_paths] if isinstance(val_paths, str) else list(val_paths)
    targets, material_preds, model_raw_outputs = [], [], []

    model.eval()
    with torch.no_grad():
        for path in paths:
            with open(path, "r", errors="ignore") as f:
                for line in f:
                    parts = line.rstrip("\n").split("\t")
                    if len(parts) != 5:
                        continue
                    fen, eval_cp_str, bestmove, wdl_mover_str, depth = parts

                    eval_cp = max(-TARGET_EVAL_CLAMP_CP, min(TARGET_EVAL_CLAMP_CP, float(eval_cp_str)))
                    eval_wdl = 1.0 / (1.0 + math.exp(-K * eval_cp))
                    wdl_mover = float(wdl_mover_str)
                    target = eval_lambda * eval_wdl + (1.0 - eval_lambda) * wdl_mover
                    targets.append(target)

                    mat = _material_diff_mover_pov(fen)
                    material_preds.append(1.0 / (1.0 + math.exp(-K * mat)))

                    board = chess.Board(fen)
                    white_idx, black_idx = active_features(board)
                    us_idx, them_idx = (white_idx, black_idx) if board.turn == chess.WHITE else (black_idx, white_idx)
                    ui = torch.tensor(us_idx, dtype=torch.long, device=device)
                    ti = torch.tensor(them_idx, dtype=torch.long, device=device)
                    off = torch.tensor([0], dtype=torch.long, device=device)
                    model_raw_outputs.append(model(ui, off, ti, off).item())
    model.train()

    n = len(targets)
    mean_t = sum(targets) / n
    var_t = sum((t - mean_t) ** 2 for t in targets) / n
    mse_material = sum((p - t) ** 2 for p, t in zip(material_preds, targets)) / n
    model_preds = [1.0 / (1.0 + math.exp(-K * r)) for r in model_raw_outputs]
    mse_untrained = sum((p - t) ** 2 for p, t in zip(model_preds, targets)) / n

    print(f"=== Preflight (n={n:,} posizioni di validazione) ===")
    print(f"  1. Varianza target (predittore costante): {var_t:.6f}")
    print(f"  2. MSE del solo materiale:                 {mse_material:.6f}")
    print(f"  3. MSE del modello non addestrato:          {mse_untrained:.6f}")
    print(f"  (per confronto dopo il training: la rete deve finire sotto il punto 2)")

    assert mse_untrained <= var_t * UNTRAINED_MSE_MAX_RATIO, (
        f"STOP: MSE del modello non addestrato ({mse_untrained:.4f}) supera di piu' di "
        f"{UNTRAINED_MSE_MAX_RATIO}x la varianza dei target ({var_t:.4f}) -- "
        f"l'inizializzazione dello strato di uscita e' probabilmente fuori scala. "
        f"Non proseguire: correggi prima di allenare."
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", nargs="+", required=True,
                     help="file .tsv (--format tsv) o un prefisso binario (--format binary)")
    ap.add_argument("--val", nargs="+", default=None,
                     help="file .tsv (--format tsv) o un prefisso binario (--format binary)")
    ap.add_argument("--format", choices=["tsv", "binary"], default="tsv",
                     help="tsv: parsing riga per riga (lento, nessuna conversione richiesta). "
                          "binary: array precalcolati da convert_to_binary.py, ~11x piu' veloce")
    ap.add_argument("--preflight-val", default=None,
                     help="file .tsv per i tre numeri di pre-volo (richiede il FEN, quindi sempre "
                          "TSV anche con --format binary). Default: --val stesso se --format tsv, "
                          "altrimenti nessun preflight.")
    ap.add_argument("--out", default="checkpoint.pt")
    ap.add_argument("--log-csv", default=None,
                     help="CSV train/val loss per epoca (default: <out>.csv)")
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--batch-size", type=int, default=8192)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--eval-lambda", type=float, default=0.7,
                     help="peso della valutazione Stockfish vs risultato partita (1.0 = solo eval)")
    ap.add_argument("--patience", type=int, default=5,
                     help="early stop se la validation loss non migliora per N epoche di fila")
    ap.add_argument("--best-out", default=None,
                     help="checkpoint separato per l'epoca a validation loss migliore "
                          "(default: <out>.best.pt)")
    ap.add_argument("--resume", default=None, help="checkpoint da cui riprendere")
    ap.add_argument("--save-every", type=int, default=300,
                     help="salva un checkpoint anche ogni N batch, non solo a fine epoca")
    ap.add_argument("--snapshot-epochs", default=None,
                     help="lista separata da virgole (es. 1,5,10,20): oltre a --out, salva anche "
                          "una copia <out>.epoch<N>.pt a fine di ciascuna di queste epoche — serve "
                          "per confrontare una curva (es. round-trip Python/motore) invece del solo "
                          "punto finale")
    args = ap.parse_args()
    snapshot_epochs = set(int(x) for x in args.snapshot_epochs.split(",")) if args.snapshot_epochs else set()

    log_csv = args.log_csv or (os.path.splitext(args.out)[0] + ".csv")
    best_out = args.best_out or (os.path.splitext(args.out)[0] + ".best.pt")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}" + ("" if device.type == "cuda" else "  (nessuna GPU trovata: sarà lento)"))

    model = LunaHalfKA().to(device)

    # On the freshly-initialized model, before loading a --resume:
    # ALWAYS measured on the fresh init, not on an already-trained
    # state, so the comparison stays meaningful regardless of how this
    # specific run starts. Always needs a TSV (the FEN is needed for
    # material), even when the actual training uses --format binary.
    preflight_val = args.preflight_val or (args.val if args.format == "tsv" else None)
    preflight_checks(model, preflight_val, args.eval_lambda, device)

    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr)
    scheduler = make_scheduler(optimizer, args.epochs)
    loss_fn = torch.nn.MSELoss()

    best_val_loss = float("inf")
    epochs_without_improvement = 0

    start_epoch = 0
    if args.resume:
        ckpt = torch.load(args.resume, map_location=device)
        model.load_state_dict(ckpt["model"])
        optimizer.load_state_dict(ckpt["optimizer"])
        scheduler.load_state_dict(ckpt["scheduler"])
        start_epoch = ckpt["epoch"] + 1
        print(f"Ripreso da {args.resume} (epoca {start_epoch})")

    train_dataset, train_collate = make_dataset(args.train, args.format, args.eval_lambda)
    print(f"Formato dati: {args.format}"
          + ("  (~11x piu' veloce del TSV)" if args.format == "binary" else ""))

    csv_is_new = not os.path.exists(log_csv)
    with open(log_csv, "a", newline="") as f_csv:
        csv_writer = csv.writer(f_csv)
        if csv_is_new:
            csv_writer.writerow(["epoch", "train_loss", "val_loss", "lr", "seconds",
                                  "clamped_feature_weights", "clamped_output_weights"])

        for epoch in range(start_epoch, args.epochs):
            t0 = time.time()
            loader = DataLoader(train_dataset, batch_size=args.batch_size, collate_fn=train_collate, num_workers=0)
            total_loss, n_batches, n_positions = 0.0, 0, 0

            for us_idx, us_off, them_idx, them_off, targets in loader:
                us_idx, us_off = us_idx.to(device), us_off.to(device)
                them_idx, them_off = them_idx.to(device), them_off.to(device)
                targets = targets.to(device)

                pred = model(us_idx, us_off, them_idx, them_off)
                loss = sigmoid_loss(pred, targets, loss_fn)

                optimizer.zero_grad()
                loss.backward()
                optimizer.step()

                with torch.no_grad():
                    model.output_weights.clamp_(-WEIGHT_CLIP, WEIGHT_CLIP)
                    model.feature_weights.weight.clamp_(-WEIGHT_CLIP, WEIGHT_CLIP)

                total_loss += loss.item()
                n_batches += 1
                n_positions += targets.numel()

                if n_batches % 200 == 0:
                    print(f"  epoca {epoch+1}  batch {n_batches}  posizioni={n_positions:,}  loss={total_loss/n_batches:.4f}")

                if n_batches % args.save_every == 0:
                    save_checkpoint(args.out, model, optimizer, scheduler, epoch)

            train_loss = total_loss / max(n_batches, 1)
            val_loss = evaluate(model, args.val, args.eval_lambda, args.batch_size, device, loss_fn, fmt=args.format)
            n_clamped_fw, n_clamped_ow = count_clamped_weights(model)
            scheduler.step()
            elapsed = time.time() - t0

            # 4 decimals, not 2: with 2, epochs 3/4/5 of a previous run
            # all printed "0.09" and the plateau only showed up from the
            # missing "New best" line.
            val_str = f"{val_loss:.4f}" if val_loss is not None else "n/d"
            print(f"✅ Epoca {epoch+1}/{args.epochs} completata — train_loss={train_loss:.4f}  val_loss={val_str}  "
                  f"lr={scheduler.get_last_lr()[0]:.2e}  {n_positions:,} posizioni  {elapsed:.1f}s  "
                  f"pesi_al_clamp: feature={n_clamped_fw} output={n_clamped_ow}")

            save_checkpoint(args.out, model, optimizer, scheduler, epoch)
            csv_writer.writerow([epoch + 1, train_loss, val_loss, scheduler.get_last_lr()[0], f"{elapsed:.1f}",
                                  n_clamped_fw, n_clamped_ow])
            f_csv.flush()
            print(f"   Checkpoint salvato: {args.out}  |  log: {log_csv}")

            if (epoch + 1) in snapshot_epochs:
                snapshot_path = f"{args.out}.epoch{epoch+1}.pt"
                save_checkpoint(snapshot_path, model, optimizer, scheduler, epoch)
                print(f"   Istantanea epoca {epoch+1}: {snapshot_path}")

            if val_loss is not None:
                if val_loss < best_val_loss:
                    best_val_loss = val_loss
                    epochs_without_improvement = 0
                    save_checkpoint(best_out, model, optimizer, scheduler, epoch)
                    print(f"   Nuovo migliore su validation ({val_loss:.4f}): {best_out}")
                else:
                    epochs_without_improvement += 1
                    if epochs_without_improvement >= args.patience:
                        print(f"\nEarly stop: nessun miglioramento su validation da {args.patience} epoche "
                              f"(migliore: {best_val_loss:.4f})")
                        break

    print(f"\nFatto. Ora esporta con:  python export.py --checkpoint {args.out} --out net.bin")
    print(f"(oppure il checkpoint migliore su validation: python export.py --checkpoint {best_out} --out net.bin)")


def save_checkpoint(path, model, optimizer, scheduler, epoch):
    # Weights + optimizer state + scheduler state + epoch: a resume must
    # restart exactly where it left off (Adam moments and LR included),
    # not just from the weights — a weights-only save is what goes to
    # Google Drive in the real run: here it's the same file, it's the
    # destination (Drive vs the Colab runtime's local disk) that makes
    # the difference, not the format.
    torch.save({
        "model": model.state_dict(),
        "optimizer": optimizer.state_dict(),
        "scheduler": scheduler.state_dict(),
        "epoch": epoch,
    }, path)


if __name__ == "__main__":
    main()
