"""Resumable HTTP range streamer: writes the bytes of URL to stdout; on any error re-requests from the last byte written.
usage: python3 dl.py URL [URL ...]   (files are streamed one after the other; each is fetched whole)
Exit 1 if 30 consecutive attempts make no progress. Progress/retries go to stderr."""
import sys
import time
import urllib.request

out = sys.stdout.buffer
for url in sys.argv[1:]:
    head = urllib.request.Request(url, method="HEAD")
    size = int(urllib.request.urlopen(head, timeout=60).headers["Content-Length"])
    pos, fails, total_retries = 0, 0, 0
    while pos < size:
        before = pos
        try:
            req = urllib.request.Request(url, headers={"Range": f"bytes={pos}-{size - 1}"})
            with urllib.request.urlopen(req, timeout=60) as r:
                while True:
                    b = r.read(1 << 20)
                    if not b:
                        break
                    out.write(b)
                    pos += len(b)
        except Exception as e:  # network drop, expired redirect, timeout: resume from `pos`
            total_retries += 1
            print(f"[dl] {url[-40:]} at {pos}/{size}: {type(e).__name__} {e}; retry {total_retries}", file=sys.stderr, flush=True)
        if pos == before:
            fails += 1
            if fails >= 30:
                sys.exit(f"[dl] no progress after 30 attempts at {pos}/{size}")
            time.sleep(5)
        else:
            fails = 0
    out.flush()
    print(f"[dl] {url[-40:]} complete: {size} bytes, {total_retries} retries", file=sys.stderr, flush=True)
