"""
Costruisce il file di aperture per UNO shard della generazione 2, con
CONSUMO SENZA REINSERIMENTO (gen2.md, punto 2: "garantisce riuso <=1x per
costruzione invece di sperarci"): ogni pool viene mescolato UNA VOLTA sola
(seed fisso, alla prima chiamata) e poi consumato in sequenza tramite un
cursore persistito su disco (data/*_offset.txt) — ogni posizione di
apertura usata al massimo una volta in tutta la run, indipendentemente da
quanti shard la consumano.

Uso (chiamato una volta per shard, in ordine):
  python build_shard_openings_gen2.py --normal-pool data/normal_openings.epd \
      --endgame-pool data/endgame_positions.epd --count 5000 --endgame-frac 0.30 \
      --out shards/raw/gen2_shard_00001_openings.epd
"""
import argparse
import os
import random


def load_or_shuffle_pool(path, seed):
    """Se non esiste ancora <path>.shuffled, mescola <path> una volta (seed
    fisso) e lo scrive come <path>.shuffled — tutte le chiamate successive
    (per ogni shard) leggono lo STESSO ordine mescolato, garantendo che il
    cursore di offset sia coerente run dopo run."""
    shuffled_path = path + ".shuffled"
    if os.path.exists(shuffled_path):
        with open(shuffled_path, "r", encoding="utf-8") as f:
            return [l.strip() for l in f if l.strip()]
    with open(path, "r", encoding="utf-8") as f:
        lines = [l.strip() for l in f if l.strip()]
    rng = random.Random(seed)
    rng.shuffle(lines)
    with open(shuffled_path, "w", encoding="utf-8") as f:
        for l in lines:
            f.write(l + "\n")
    return lines


def consume(pool, offset_path, n):
    """Legge il cursore corrente, prende le prossime N righe, avanza e
    persiste il cursore. Fallisce rumorosamente (non wrap-around silenzioso)
    se il pool si esaurisce: significa che e' stato dimensionato troppo
    piccolo per il numero di partite pianificato."""
    offset = 0
    if os.path.exists(offset_path):
        with open(offset_path, "r") as f:
            offset = int(f.read().strip() or "0")
    end = offset + n
    if end > len(pool):
        raise SystemExit(
            f"[ERRORE FATALE] pool esaurito: servono {n} posizioni da offset {offset} "
            f"ma il pool ne ha solo {len(pool)}. Dimensiona il pool piu' grande prima di "
            f"continuare — nessun wrap-around automatico (rientrerebbe nel riuso che "
            f"questo script esiste per evitare)."
        )
    slice_ = pool[offset:end]
    with open(offset_path, "w") as f:
        f.write(str(end))
    return slice_


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--normal-pool", required=True)
    ap.add_argument("--endgame-pool", required=True)
    ap.add_argument("--count", type=int, required=True)
    ap.add_argument("--endgame-frac", type=float, default=0.30)
    ap.add_argument("--shuffle-seed", type=int, default=1)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    normal_pool = load_or_shuffle_pool(args.normal_pool, args.shuffle_seed)
    endgame_pool = load_or_shuffle_pool(args.endgame_pool, args.shuffle_seed + 1)

    n_endgame = round(args.count * args.endgame_frac)
    n_normal = args.count - n_endgame

    normal_offset_path = args.normal_pool + ".offset"
    endgame_offset_path = args.endgame_pool + ".offset"

    chosen_normal = consume(normal_pool, normal_offset_path, n_normal)
    chosen_endgame = consume(endgame_pool, endgame_offset_path, n_endgame)

    combined = chosen_endgame + chosen_normal
    # Shuffle SOLO dell'ordine all'interno del file di questo shard (quale
    # partita la usa prima), non ri-mescola i pool sorgente: l'assegnazione
    # posizione->shard resta quella del cursore, deterministica e senza
    # reinserimento.
    random.Random(args.shuffle_seed + 1000).shuffle(combined)

    with open(args.out, "w") as f:
        for line in combined:
            f.write(line + "\n")

    print(f"[FATTO] {args.out}: {len(combined)} aperture ({len(chosen_endgame)} finale, {len(chosen_normal)} normali, senza reinserimento)")
    print(f"ENDGAME_LINES={len(chosen_endgame)}")


if __name__ == "__main__":
    main()
