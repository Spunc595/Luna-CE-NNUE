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
        return "endgame (<=8 pieces)"
    if n <= 12:
        return "wide endgame (9-12 pieces)"
    if n <= 20:
        return "middlegame (13-20 pieces)"
    return "opening/early middlegame (>20 pieces)"


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

    print(f"Total positions: {total:,}\n")
    order = ["endgame (<=8 pieces)", "wide endgame (9-12 pieces)",
             "middlegame (13-20 pieces)", "opening/early middlegame (>20 pieces)"]
    for b in order:
        n = counts.get(b, 0)
        pct = (n / total * 100) if total else 0.0
        print(f"  {b:42s} {n:8,}  ({pct:5.1f}%)")

    endgame_total = counts.get("endgame (<=8 pieces)", 0) + counts.get("wide endgame (9-12 pieces)", 0)
    endgame_pct = (endgame_total / total * 100) if total else 0.0
    print(f"\n  TOTAL ENDGAME (<=12 pieces): {endgame_total:,} ({endgame_pct:.1f}%)")
    if endgame_pct < 20:
        print("  [WARNING] Below the 20-25% threshold expected by the plan — revisit the share before generating the rest.")
    else:
        print("  [OK] Within or above the expected 20-25%.")


if __name__ == "__main__":
    main()
