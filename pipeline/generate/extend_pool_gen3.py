"""
Estende in modo sicuro il pool normal_openings.epd SENZA invalidare lo stato
gia' consumato (data/normal_openings.epd.offset + .shuffled), usato dai 5
shard di controllo gia' generati. NON reshuffla il pool esistente: quello
romperebbe la garanzia "senza reinserimento" (una posizione gia' assegnata
a offset [0, cursore) potrebbe ricomparire in [cursore, fine) sotto una
nuova permutazione). Aggiunge solo le righe NUOVE in coda, sia al file
raw sia al file .shuffled (mescolate fra loro con un seed mai usato prima),
lasciando offset e le prime N righe di .shuffled invariate.

Uso:
  python3 extend_pool_gen2.py --base data/normal_openings.epd \
      --extension data/normal_openings_200k.epd data/normal_openings_topup20k.epd \
      --shuffle-seed 101
"""
import argparse
import os
import random


def read_lines(path):
    with open(path, "r", encoding="utf-8") as f:
        return [l.strip() for l in f if l.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--extension", nargs="+", required=True)
    ap.add_argument("--shuffle-seed", type=int, required=True)
    args = ap.parse_args()

    base_lines = read_lines(args.base)
    base_set = set(base_lines)
    shuffled_path = args.base + ".shuffled"
    offset_path = args.base + ".offset"

    if not os.path.exists(shuffled_path):
        raise SystemExit(f"[ERRORE] {shuffled_path} non esiste: nulla e' ancora stato consumato, "
                          f"non serve questo script — basta rigenerare il pool da zero.")
    shuffled_lines = read_lines(shuffled_path)
    if len(shuffled_lines) != len(base_lines):
        raise SystemExit(f"[ERRORE FATALE] {shuffled_path} ({len(shuffled_lines)} righe) non combacia "
                          f"con {args.base} ({len(base_lines)} righe) — stato incoerente, fermo tutto.")

    seen = set(base_set)
    delta = []
    dup_within_base_extension = 0
    for ext_path in args.extension:
        for line in read_lines(ext_path):
            if line in seen:
                dup_within_base_extension += 1
                continue
            seen.add(line)
            delta.append(line)

    if not delta:
        raise SystemExit("[ERRORE] nessuna riga nuova trovata nelle estensioni fornite — controllare gli input.")

    rng = random.Random(args.shuffle_seed)
    delta_shuffled = list(delta)
    rng.shuffle(delta_shuffled)

    offset_before = 0
    if os.path.exists(offset_path):
        with open(offset_path, "r") as f:
            offset_before = int(f.read().strip() or "0")

    with open(args.base, "a", encoding="utf-8") as f:
        for line in delta:
            f.write(line + "\n")
    with open(shuffled_path, "a", encoding="utf-8") as f:
        for line in delta_shuffled:
            f.write(line + "\n")

    new_total = len(base_lines) + len(delta)
    print(f"[FATTO] base prima: {len(base_lines)} righe, delta aggiunto: {len(delta)} righe "
          f"(scartati {dup_within_base_extension} duplicati gia' presenti), nuovo totale: {new_total}")
    print(f"offset invariato: {offset_before} (ancora valido, punta dentro la parte non toccata)")
    print(f"NEW_TOTAL={new_total}")


if __name__ == "__main__":
    main()
