"""
Manifest JSON per shard della GENERAZIONE 2: sia la
valutazione nel self-play SIA le etichette di annotazione vengono dalla
RETE GEN1 (non la classica, non Stockfish, non akimbo) -- il manifesto lo
registra esplicitamente, con la provenienza del checkpoint/rete stessa.

Uso:
  python write_manifest_gen2.py --shard-id gen2_shard_00001 \
      --pgn shards/raw/gen2_shard_00001.pgn \
      --positions shards/raw/gen2_shard_00001_positions.txt \
      --openings shards/raw/gen2_shard_00001_openings.epd \
      --endgame-lines-in-openings 1500 \
      --out shards/raw/gen2_shard_00001.manifest.json
"""
import argparse
import datetime
import json
import os
import subprocess

LUNA_SRC_DIR = os.path.expanduser("~/gen1_classical/luna-src")

GEN1_NET_PROVENANCE = {
    "source": "generation 1 checkpoint (gen1_checkpoint.best.pt), exported to gen1_net.bin",
    "gen1_dataset": "2,135,009 unique positions, 46 shards, classical-PST-eval self-play + "
                    "classical-eval-search (10k nodes) labels",
    "gen1_val_loss_min": 0.013316,
    "gen1_spearman_vs_own_master": 0.9230,
    "gen1_spearman_vs_stockfish": 0.5874,
    "gen2_master_spearman_vs_stockfish_by_nodes": {"10000": 0.8072, "20000": 0.8285, "50000": 0.8413},
    "annotation_nodes_chosen": 20000,
    "annotation_nodes_chosen_rationale": "knee of the curve: still a large gain over 10k, "
                                          "keeps cost/time margin to iterate rather than "
                                          "spending it all on the smaller 50k->20k increment.",
    "gen2_expected_spearman_vs_stockfish": "0.76-0.78 (fixed in advance: "
                                            "would put gen2 on par with gen0 (Stockfish-trained, "
                                            "0.7850) but with fully TCEC-compliant data)",
    "note": "This net is the SELF-PLAY EVALUATION AND ANNOTATION SOURCE for generation 2. "
            "Neither Stockfish nor akimbo are used anywhere in this shard's generation or "
            "labeling — Stockfish appears only in the separate, offline gate measurement "
            "(measure_master_spearman.py) as a measurement tool, never as a label source.",
}

NORMAL_OPENINGS_CONFIG = {
    "generator": "gen_random_openings_gen2.py",
    "plies": 9,
    "eval_limit_cp": 200,
    "filter_depth": 6,
    "filter_eval_source": "gen1 net (UseNNUE=true, external luna.nnue, confirmed loaded via probe)",
    "consumption": "no-replacement (build_shard_openings_gen2.py): pool shuffled once, "
                    "consumed via a persisted global offset cursor — each opening used at "
                    "most once across the whole run, not resampled per shard.",
}

ENDGAME_OPENINGS_CONFIG = {
    "source": "lichess_db_puzzle.csv (database.lichess.org)",
    "extractor": "extract_endgame_openings.py (unchanged from generation 1)",
    "max_pieces": 12,
    "max_material_imbalance_points": 5.0,
    "consumption": "no-replacement, same mechanism as normal_openings above",
}

BASE_CONFIG = {
    "self_play_nodes": 3000,
    "annotation_nodes": 20000,
    "maxmoves": 80,
    "draw": "movenumber=34 movecount=8 score=30",
    "resign": "movecount=8 score=800 twosided=true",
    "extract_step": 4,
    "extract_skip_opening": 11,
    "extract_max_per_game": 38,
    "extract_jitter": "0-3",
    "endgame_opening_quota_target": 0.30,
}


def get_engine_commit():
    try:
        result = subprocess.run(["git", "-C", LUNA_SRC_DIR, "rev-parse", "HEAD"],
                                 capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except Exception:
        return "UNKNOWN"


def get_engine_version(luna_bin):
    try:
        proc = subprocess.run([luna_bin], input="uci\nquit\n", capture_output=True, text=True, timeout=10)
        for line in proc.stdout.splitlines():
            if line.startswith("id name"):
                return line[len("id name "):].strip()
    except Exception:
        pass
    return "UNKNOWN"


def count_lines(path):
    if not path or not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return sum(1 for _ in f)


def count_games_in_pgn(path):
    if not path or not os.path.exists(path):
        return None
    result = subprocess.run(["grep", "-c", "^\\[Event "], input=open(path, "rb").read(),
                             capture_output=True)
    try:
        return int(result.stdout.decode().strip())
    except ValueError:
        return None


def file_size(path):
    return os.path.getsize(path) if path and os.path.exists(path) else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shard-id", required=True)
    ap.add_argument("--pgn", required=True)
    ap.add_argument("--positions", required=True)
    ap.add_argument("--openings", required=True)
    ap.add_argument("--endgame-lines-in-openings", type=int, required=True)
    ap.add_argument("--luna-bin", default=os.path.expanduser("~/gen2_classical/engine/luna"))
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    total_openings = count_lines(args.openings) or 0
    endgame_frac = (args.endgame_lines_in_openings / total_openings) if total_openings else None

    manifest = {
        "shard_id": args.shard_id,
        "generation": 2,
        "dataset": "gen2_classical",
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "compliance_note": "TCEC NNUE guideline: all training data generated by the engine's own "
                            "search/evaluation. Self-play evaluation AND labels both come from "
                            "Luna's own search using the generation-1 net (bootstrap chain: "
                            "classical PST -> gen1 net -> gen2 net -> ...). Stockfish/akimbo never "
                            "used in self-play or labeling, only as an offline measurement tool "
                            "for the gate (see gen1_net_provenance below).",
        "engine_version": get_engine_version(args.luna_bin),
        "engine_commit": get_engine_commit(),
        "self_play_eval_source": f"gen1 net (UCI: UseNNUE=true, external luna.nnue), nodes={BASE_CONFIG['self_play_nodes']}",
        "label_source": f"gen1 net search, nodes={BASE_CONFIG['annotation_nodes']} (annotate_incremental_gen2.py, UseNNUE=true)",
        "gen1_net_provenance": GEN1_NET_PROVENANCE,
        **BASE_CONFIG,
        "normal_openings": NORMAL_OPENINGS_CONFIG,
        "endgame_openings": ENDGAME_OPENINGS_CONFIG,
        "openings_file": args.openings,
        "openings_file_total_lines": total_openings,
        "openings_file_endgame_lines": args.endgame_lines_in_openings,
        "endgame_quota_actual": round(endgame_frac, 4) if endgame_frac is not None else None,
        "games_actual": count_games_in_pgn(args.pgn),
        "positions_extracted": count_lines(args.positions),
        "pgn_file_size_bytes": file_size(args.pgn),
    }

    with open(args.out, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"Manifest scritto: {args.out}")


if __name__ == "__main__":
    main()
