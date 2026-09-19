"""
Tests for what annotate_incremental_gen4_oracle.py adds: failed FENs recorded in a
separate file, counts in the manifest, and the rejection threshold. The engine is
replaced by a stub (annotate_batch), so this checks the bookkeeping, not the search.

  python test_annotate_gen4.py
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import annotate_incremental_gen4_oracle as A  # noqa: E402

START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
FENS = [
    START,
    "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
    "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
    "rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 1 2",
    "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3",
    "r1bqkbnr/pppp1ppp/2n5/1B2p3/4P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3",
    "r1bqkbnr/1ppp1ppp/p1n5/1B2p3/4P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 0 4",
    "r1bqkbnr/1ppp1ppp/p1n5/4p3/B3P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 1 4",
    "r1bqkb1r/1ppp1ppp/p1n2n2/4p3/B3P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 2 5",
    "r1bqkb1r/1ppp1ppp/p1n2n2/4p3/B3P3/5N2/PPPP1PPP/RNBQ1RK1 b kq - 3 5",
]


def make_shard(d, sid="gen4_shard_00001"):
    shards, out = os.path.join(d, "shards"), os.path.join(d, "out")
    os.makedirs(shards)
    os.makedirs(out)
    with open(os.path.join(shards, f"{sid}_positions.txt"), "w", newline="\n") as f:
        for i, fen in enumerate(FENS):
            f.write(f"{fen}\t1-0\t{1 if i < 5 else 2}\t0\n")
    with open(os.path.join(shards, f"{sid}.manifest.json"), "w") as f:
        json.dump({"shard_id": sid, "engine_commit": "abc"}, f)
    return shards, out, sid


def stub(failing):
    def annotate_batch(fens, luna_path, workers, nodes, tmp_dir, **kw):
        return {fen: ((None, None) if fen in failing else (25, "e2e4")) for fen in fens}
    return annotate_batch


class Gen4Bookkeeping(unittest.TestCase):
    def test_failures_are_recorded_counted_and_kept_out_of_the_dataset(self):
        with tempfile.TemporaryDirectory() as d:
            shards, out, sid = make_shard(d)
            failing = {FENS[3], FENS[7]}
            A.annotate_batch = stub(failing)
            seen = set()
            new_hashes, counts = A.process_shard(sid, shards, out, "luna", 1, 1000, seen, 0.5)
            self.assertEqual(counts["n_input"], 10)
            self.assertEqual(counts["n_failed"], 2)
            self.assertEqual(counts["n_written"], 8)
            self.assertEqual(counts["n_dup"], 0)
            self.assertEqual(counts["n_new"] + counts["n_force"] + counts["n_dup"], counts["n_input"])
            written = [l.split("\t")[0] for l in open(os.path.join(out, f"{sid}_annotated.tsv")).read().splitlines()]
            self.assertEqual(set(written), set(FENS) - failing)
            fl = open(os.path.join(out, "failed_fens", f"{sid}_failed.tsv")).read().splitlines()
            self.assertEqual({l.split("\t")[0] for l in fl}, failing)
            self.assertEqual({int(l.split("\t")[1]) for l in fl}, {3, 7})
            # failed hashes are NOT in global_seen, so a later shard may still annotate them
            self.assertEqual(len(new_hashes), 8)

    def test_manifest_gets_the_counts(self):
        with tempfile.TemporaryDirectory() as d:
            shards, out, sid = make_shard(d)
            A.annotate_batch = stub({FENS[3]})
            _, counts = A.process_shard(sid, shards, out, "luna", 1, 1000, set(), 0.5)
            A.patch_manifest_with_annotation_commit(shards, sid, 1000, counts)
            m = json.load(open(os.path.join(shards, f"{sid}.manifest.json")))
            for k in ("n_input", "n_new", "n_dup", "n_force", "n_written", "n_failed"):
                self.assertIn("annotation_" + k, m)
            self.assertEqual(m["annotation_n_failed"], 1)

    def test_no_failure_leaves_no_failed_file(self):
        with tempfile.TemporaryDirectory() as d:
            shards, out, sid = make_shard(d)
            A.annotate_batch = stub(set())
            _, counts = A.process_shard(sid, shards, out, "luna", 1, 1000, set(), 0.001)
            self.assertEqual(counts["n_failed"], 0)
            self.assertFalse(os.path.exists(os.path.join(out, "failed_fens")))

    def test_over_the_limit_the_shard_is_not_written_but_the_failures_are_saved(self):
        with tempfile.TemporaryDirectory() as d:
            shards, out, sid = make_shard(d)
            A.annotate_batch = stub({FENS[1], FENS[2], FENS[3]})   # 3 of 10 = 30 %
            with self.assertRaises(RuntimeError) as cm:
                A.process_shard(sid, shards, out, "luna", 1, 1000, set(), 0.001)
            self.assertIn("NOT written", str(cm.exception))
            self.assertFalse(os.path.exists(os.path.join(out, f"{sid}_annotated.tsv")))
            fl = open(os.path.join(out, "failed_fens", f"{sid}_failed.tsv")).read().splitlines()
            self.assertEqual(len(fl), 3)

    def test_exactly_at_the_limit_is_accepted(self):
        with tempfile.TemporaryDirectory() as d:
            shards, out, sid = make_shard(d)
            A.annotate_batch = stub({FENS[1]})                     # 1 of 10 = 10 %
            _, counts = A.process_shard(sid, shards, out, "luna", 1, 1000, set(), 0.1)
            self.assertEqual(counts["n_failed"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
