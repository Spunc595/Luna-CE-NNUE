"""
Verifica di unicita' sui primi N shard della generazione 2 (gen2.md, punto
2: "deve stare sopra il 95%. Se non ci sta, il problema non era il riuso
e va capito prima di generare il resto.").

Uso:
  python check_uniqueness_gen2.py --shards-dir shards/backed_up --num-shards 5
"""
import argparse
import hashlib
import os


def dedup_key_hash(fen: str) -> int:
    parts = fen.split(" ")
    key = " ".join(parts[:4])
    return int.from_bytes(hashlib.blake2b(key.encode(), digest_size=8).digest(), "big")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shards-dir", required=True)
    ap.add_argument("--num-shards", type=int, default=5)
    args = ap.parse_args()

    seen = set()
    total_raw = 0
    total_unique = 0

    for i in range(1, args.num_shards + 1):
        sid = f"gen2_shard_{i:05d}"
        pos_path = os.path.join(args.shards_dir, f"{sid}_positions.txt")
        if not os.path.exists(pos_path):
            print(f"  [SALTO] {sid}: mancante")
            continue
        shard_raw = 0
        shard_unique = 0
        with open(pos_path, "r", errors="ignore") as f:
            for line in f:
                parts = line.rstrip("\n").split("\t")
                if len(parts) != 4:
                    continue
                fen = parts[0]
                h = dedup_key_hash(fen)
                shard_raw += 1
                if h not in seen:
                    seen.add(h)
                    shard_unique += 1
        total_raw += shard_raw
        total_unique += shard_unique
        print(f"  {sid}: grezze={shard_raw:,}  uniche={shard_unique:,}  ({shard_unique/shard_raw*100:.1f}%)")

    pct = (total_unique / total_raw * 100) if total_raw else 0.0
    print(f"\nTOTALE ({args.num_shards} shard): grezze={total_raw:,}  uniche={total_unique:,}  ({pct:.1f}%)")
    if pct >= 95:
        print("[OK] Sopra la soglia 95% attesa.")
    else:
        print("[ATTENZIONE] SOTTO la soglia 95% attesa — il problema non era (solo) il riuso, fermarsi e capire prima di generare il resto.")


if __name__ == "__main__":
    main()
