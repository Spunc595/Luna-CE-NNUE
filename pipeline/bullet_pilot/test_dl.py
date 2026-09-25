"""Tests for dl.py against a local HTTP server with Range support and fault injection.

  python test_dl.py

1. reader closes early (today's case)        -> ONE 'READER CLOSED' line, zero 'NETWORK ERROR', exit 0, clean stderr
2. the OLD script (dl_v1_defective.py) on the same case -> retries/'Broken pipe' as a NETWORK problem: proves test 1 can see the defect
3. a REAL network cut (server drops mid-body) -> 'NETWORK ERROR' lines, resume from the last byte, byte-identical result,
                                                 'DONE' line, no 'READER CLOSED'
4. plain full transfer                        -> 'DONE' with the byte count, zero retries
"""
import hashlib
import http.server
import os
import subprocess
import sys
import threading
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.urandom(6 * 1024 * 1024 + 123)
STATE = {"drops": 0, "requests": 0}


class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _range(self):
        r = self.headers.get("Range")
        return int(r.split("=")[1].split("-")[0]) if r else 0

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Length", str(len(DATA)))
        self.end_headers()

    def do_GET(self):
        start = self._range()
        body = DATA[start:]
        STATE["requests"] += 1
        self.send_response(206 if start else 200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if STATE["drops"] > 0:                       # a real cut: promise the whole body, send 40% and hang up
            STATE["drops"] -= 1
            self.wfile.write(body[: int(len(body) * 0.4)])
            self.wfile.flush()
            self.connection.close()
            return
        try:
            self.wfile.write(body)
        except OSError:
            pass


def run(script, url, reader_bytes=None, timeout=60, env_extra=None):
    """Runs a script with its stdout piped to us. If reader_bytes is set, read that many bytes and CLOSE the pipe."""
    env = dict(os.environ, DL_RETRY_SLEEP="0.2", **(env_extra or {}))
    p = subprocess.Popen([sys.executable, os.path.join(HERE, script), url], stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    if reader_bytes is not None:
        got = p.stdout.read(reader_bytes)
        p.stdout.close()
        try:
            _, e = p.communicate(timeout=timeout)
            err = e.decode()
        except subprocess.TimeoutExpired:
            p.kill()
            _, e = p.communicate()
            err = "(killed after timeout)" + chr(10) + e.decode()
        return p.returncode, got, err
    got = p.stdout.read()
    err = p.stderr.read().decode()
    p.wait()
    return p.returncode, got, err


class DL(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        cls.url = f"http://127.0.0.1:{cls.srv.server_address[1]}/f.bin"
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def setUp(self):
        STATE["drops"] = 0

    def test1_reader_closes_early_is_a_clean_end(self):
        rc, got, err = run("dl.py", self.url, reader_bytes=1000)
        print("\n--- test 1 log ---\n" + err)
        self.assertEqual(rc, 0)
        self.assertEqual(got, DATA[:1000])
        self.assertEqual(err.count("READER CLOSED"), 1)
        self.assertEqual(err.count("NETWORK ERROR"), 0)
        self.assertNotIn("retry", err.replace("no retry", ""))
        self.assertNotIn("Traceback", err)
        self.assertNotIn("ignored", err)
        self.assertEqual(len([line for line in err.splitlines() if line.strip()]), 1, "the log must be exactly the one closing line")

    def test2_old_script_shows_the_defect_on_the_same_case(self):
        rc, got, err = run("dl_v1_defective.py", self.url, reader_bytes=1000, timeout=8, env_extra={})
        print("\n--- test 2 (old script) log ---\n" + err[:600])
        self.assertGreaterEqual(err.count("retry"), 2, "the old script must retry a closed pipe as if it were the network")

    def test3_real_network_cut_is_reported_as_network_and_retried(self):
        STATE["drops"] = 2
        rc, got, err = run("dl.py", self.url)
        print("\n--- test 3 log ---\n" + err)
        self.assertEqual(rc, 0)
        self.assertEqual(hashlib.sha256(got).hexdigest(), hashlib.sha256(DATA).hexdigest(), "resume must be byte-exact")
        self.assertGreaterEqual(err.count("NETWORK ERROR"), 2)
        self.assertEqual(err.count("READER CLOSED"), 0)
        self.assertIn(f"DONE: 1 file(s), {len(DATA)} bytes transferred, 2 network retries", err)

    def test4_plain_transfer_ends_with_a_positive_line(self):
        rc, got, err = run("dl.py", self.url)
        print("\n--- test 4 log ---\n" + err)
        self.assertEqual(rc, 0)
        self.assertEqual(got, DATA)
        self.assertEqual(err.count("NETWORK ERROR"), 0)
        self.assertIn(f"DONE: 1 file(s), {len(DATA)} bytes transferred, 0 network retries", err)


if __name__ == "__main__":
    unittest.main(verbosity=2)
