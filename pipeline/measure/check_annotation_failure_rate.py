"""
Dataset-level gate on annotation failures, from the counts the gen4 annotator
writes into every shard manifest (annotation_n_new, annotation_n_force,
annotation_n_failed). Exit 1 if the failure rate over the whole generation,
failed / (new + force), exceeds --max-failed-rate, or if any manifest lacks the
counts (a generation annotated without them cannot be checked, and is refused).
The limit has no default on purpose (it is a declared decision, see LINEAGE.md).

Usage:
  python check_annotation_failure_rate.py --manifests-dir DIR --pattern 'gen4_shard_*.manifest.json' \
      --max-failed-rate 0.001
"""
import argparse
import glob
import json
import os
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifests-dir", required=True)
    ap.add_argument("--pattern", default="*.manifest.json")
    ap.add_argument("--max-failed-rate", type=float, required=True)
    args = ap.parse_args()

    paths = sorted(glob.glob(os.path.join(args.manifests_dir, args.pattern)))
    if not paths:
        sys.exit("no manifests found")
    sent = failed = 0
    missing = []
    for p in paths:
        with open(p, encoding="utf-8") as f:
            m = json.load(f)
        try:
            sent += m["annotation_n_new"] + m["annotation_n_force"]
            failed += m["annotation_n_failed"]
        except KeyError:
            missing.append(os.path.basename(p))
    if missing:
        print(f"REFUSED: {len(missing)} manifest(s) without annotation counts, e.g. {missing[:3]}", file=sys.stderr)
        sys.exit(1)
    rate = failed / sent if sent else 0.0
    print(f"{len(paths)} shards, {sent:,} annotations attempted, {failed:,} failed ({rate:.4%}); "
          f"limit {args.max_failed_rate:.4%}")
    if rate > args.max_failed_rate:
        print("REFUSED: failure rate above the declared limit; the annotation is not to be used for training",
              file=sys.stderr)
        sys.exit(1)
    print("OK")


if __name__ == "__main__":
    main()
