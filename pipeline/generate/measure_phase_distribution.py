"""
Measures the distribution by game phase (by piece count) over one or
more positions.txt files (extract_positions.py format: FEN<TAB>...).
To be measured on the first shards, BEFORE launching the rest of the
generation.

Usage:
  python measure_phase_distribution.py shards/raw/shard_00001_positions.txt shards/raw/shard_00002_positions.txt
"""
import sys


def piece_count(fen):
    board_field = fen.split(" ")[0]
    return sum(1 for ch in board_field if ch.isalpha())


def bucket(n):
    if n <= 8:
        return "endgame (<=8 pezzi)"
    if n <= 12:
        return "endgame ampio (9-12 pezzi)"
    if n <= 20:
        return "mediogioco (13-20 pezzi)"
    return "apertura/primo mediogioco (>20 pezzi)"


def main():
    if len(sys.argv) < 2:
        print("Uso: python measure_phase_distribution.py <positions.txt> [altri...]")
        sys.exit(1)

    counts = {}
    total = 0
    for path in sys.argv[1:]:
        with open(path, "r", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                fen = line.split("\t")[0]
                b = bucket(piece_count(fen))
                counts[b] = counts.get(b, 0) + 1
                total += 1

    print(f"Totale posizioni: {total:,}\n")
    order = ["endgame (<=8 pezzi)", "endgame ampio (9-12 pezzi)",
             "mediogioco (13-20 pezzi)", "apertura/primo mediogioco (>20 pezzi)"]
    for b in order:
        n = counts.get(b, 0)
        pct = (n / total * 100) if total else 0.0
        print(f"  {b:42s} {n:8,}  ({pct:5.1f}%)")

    endgame_total = counts.get("endgame (<=8 pezzi)", 0) + counts.get("endgame ampio (9-12 pezzi)", 0)
    endgame_pct = (endgame_total / total * 100) if total else 0.0
    print(f"\n  TOTALE FINALE (<=12 pezzi): {endgame_total:,} ({endgame_pct:.1f}%)")
    if endgame_pct < 20:
        print("  [ATTENZIONE] Sotto la soglia 20-25% attesa dal documento — rivedere la quota prima di generare il resto.")
    else:
        print("  [OK] Dentro o sopra il 20-25% atteso.")


if __name__ == "__main__":
    main()
