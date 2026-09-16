"""
Per-shard manifest JSON for GENERATION 3: both the self-play evaluation
AND the annotation labels come from the GEN2 NETWORK -- the manifest
records this explicitly, with the checkpoint/network provenance. Single
machine (Oracle): "annotation_machine" and "self_play_machine" explicit
from the start (a correction relative to gen2, where the machine field
wasn't written for the original PC-produced shards 1-2).

Usage:
  python write_manifest_gen3.py --shard-id gen3_shard_00001 \
      --pgn shards/raw/gen3_shard_00001.pgn \
      --positions shards/raw/gen3_shard_00001_positions.txt \
      --openings shards/raw/gen3_shard_00001_openings.epd \
      --endgame-lines-in-openings 1500 \
      --out shards/raw/gen3_shard_00001.manifest.json
"""
import argparse
import datetime
import json
import os
import subprocess

LUNA_SRC_DIR = os.path.expanduser("~/gen1_classical/luna-src")
MACHINE_NAME = "oracle"

GEN2_NET_PROVENANCE = {
    "source": "generation 2 checkpoint (gen2_checkpoint.best.pt), exported to gen2_net.bin",
    "gen2_dataset": "2,972,944 unique positions, 53 shards, single continuous Oracle run "
                    "(single global_seen.bin), gen1-net-eval self-play + gen1-net-search "
                    "(20k nodes) labels",
    "gen2_val_loss_min": 0.018874,
    "gen2_spearman_vs_own_master": 0.9508,
    "gen2_spearman_vs_stockfish_static": 0.6790,
    "gen3_master_spearman_vs_stockfish_by_nodes": {},  # patched by hand before launch
    "annotation_nodes_chosen": 20000,
    "annotation_nodes_chosen_rationale": "knee of the curve, same method as generation 2.",
    "gen3_expected_spearman_vs_stockfish": "0.73-0.76 (fixed in advance: trend "
                                            "0.5874 -> 0.6790 is +0.092, expecting a shorter "
                                            "step as gains taper)",
    "note": "This net is the SELF-PLAY EVALUATION AND ANNOTATION SOURCE for generation 3. "
            "Neither Stockfish nor akimbo are used anywhere in this shard's generation or "
            "labeling -- Stockfish appears only in the separate, offline gate measurement "
            "(measure_master_spearman.py / measure_eval_error.py) as a measurement tool, "
            "never as a label source.",
}

NORMAL_OPENINGS_CONFIG = {
    "generator": "gen_random_openings_gen3.py",
    "plies": 9,
    "eval_limit_cp": 200,
    "filter_depth": 6,
    "filter_eval_source": "gen2 net (UseNNUE=true, external luna.nnue, confirmed loaded via probe)",
    "consumption": "no-replacement (build_shard_openings_gen3.py): pool shuffled once, "
                    "consumed via a persisted global offset cursor -- each opening used at "
                    "most once across the whole run, not resampled per shard.",
}

ENDGAME_OPENINGS_CONFIG = {
    "source": "lichess_db_puzzle.csv (database.lichess.org), reused from the gen2 90k pool "
              "(net-independent: raw positions filtered only by piece count/material "
              "imbalance, no engine evaluation involved).",
    "max_pieces": 12,
    "max_material_imbalance_points": 5.0,
    "consumption": "no-replacement, same mechanism as normal_openings above, fresh shuffle "
                    "for this run.",
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
    ap.add_argument("--luna-bin", default=os.path.expanduser("~/gen3_classical/engine/luna"))
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    total_openings = count_lines(args.openings) or 0
    endgame_frac = (args.endgame_lines_in_openings / total_openings) if total_openings else None

    manifest = {
        "shard_id": args.shard_id,
        "generation": 3,
        "dataset": "gen3_classical",
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "self_play_machine": MACHINE_NAME,
        "compliance_note": "TCEC NNUE guideline: all training data generated by the engine's own "
                            "search/evaluation. Self-play evaluation AND labels both come from "
                            "Luna's own search using the generation-2 net (bootstrap chain: "
                            "classical PST -> gen1 net -> gen2 net -> gen3 net -> ...). "
                            "Stockfish/akimbo never used in self-play or labeling, only as an "
                            "offline measurement tool for the gate (see gen2_net_provenance below). "
                            "Single machine (Oracle) for this whole generation -- no cross-machine "
                            "dedup state to reconcile (method rule, not an afterthought).",
        "engine_version": get_engine_version(args.luna_bin),
        "engine_commit": get_engine_commit(),
        "self_play_eval_source": f"gen2 net (UCI: UseNNUE=true, external luna.nnue), nodes={BASE_CONFIG['self_play_nodes']}",
        "label_source": f"gen2 net search, nodes={BASE_CONFIG['annotation_nodes']} (annotate_incremental_gen3_oracle.py, UseNNUE=true)",
        "gen2_net_provenance": GEN2_NET_PROVENANCE,
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
    print(f"Manifest written: {args.out}")


if __name__ == "__main__":
    main()
