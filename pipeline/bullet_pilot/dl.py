"""Resumable HTTP range streamer: writes the bytes of URL to stdout; on a NETWORK error re-requests from the last byte written.
usage: python3 dl.py URL [URL ...]   (files are streamed one after the other; each is fetched whole)

Two different events are told apart, with different log lines and different behaviour:
  * READER CLOSED  - the process reading our stdout closed the pipe (it has all it wanted): normal end, ONE line, exit 0, no retry.
  * NETWORK ERROR  - the connection failed or was cut: logged as such, retried from the last byte; exit 1 after 30 attempts
                     without progress.
A successful transfer ends with one positive line ("DONE ..."). Everything goes to stderr; nothing is silenced."""
import errno
import os
import sys
import time
import urllib.request

out = sys.stdout.buffer


def log(msg):
    print(f"[dl] {msg}", file=sys.stderr, flush=True)


def reader_closed(pipe_err):
    """The consumer closed the pipe. True for BrokenPipeError and for an OSError carrying EPIPE."""
    if isinstance(pipe_err, BrokenPipeError) or (isinstance(pipe_err, OSError) and pipe_err.errno == errno.EPIPE):
        return True
    # Windows reports a closed pipe as winerror 232 (ERROR_NO_DATA) / 109 (ERROR_BROKEN_PIPE), sometimes as EINVAL
    return os.name == "nt" and isinstance(pipe_err, OSError) and (getattr(pipe_err, "winerror", None) in (232, 109) or pipe_err.errno == errno.EINVAL)


def finish_reader_closed(total, url, pos, size, i, n):
    log(f"READER CLOSED: the consumer closed the pipe ({total} bytes fully written before the failed write; {url[-40:]}, file {i}/{n}, at {pos}/{size}); "
        f"normal end of the consumer's work, not a network error; exiting 0, no retry")
    # Python would otherwise try to flush stdout at interpreter shutdown and print 'BrokenPipeError ... ignored' by itself:
    # point stdout at /dev/null (the recipe from the Python documentation) so the log stays clean.
    os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
    sys.exit(0)


total, total_retries, urls = 0, 0, sys.argv[1:]
for i, url in enumerate(urls, 1):
    head = urllib.request.Request(url, method="HEAD")
    size = int(urllib.request.urlopen(head, timeout=60).headers["Content-Length"])
    pos, fails = 0, 0
    while pos < size:
        before = pos
        try:
            req = urllib.request.Request(url, headers={"Range": f"bytes={pos}-{size - 1}"})
            with urllib.request.urlopen(req, timeout=60) as r:
                while True:
                    b = r.read(1 << 20)          # a failure HERE is the network
                    if not b:
                        break
                    try:
                        out.write(b)             # a failure HERE is the consumer, never the network
                    except OSError as e:
                        if reader_closed(e):
                            finish_reader_closed(total, url, pos, size, i, len(urls))
                        log(f"WRITE ERROR on stdout (not the network): {type(e).__name__} {e}")
                        sys.exit(2)
                    pos += len(b)
                    total += len(b)
                if pos < size:   # http.client.read(amt) returns b'' on a premature close instead of raising: make it an error
                    raise ConnectionError(f"server closed the stream early ({pos} of {size} bytes)")
        except Exception as e:                   # network drop, expired redirect, timeout: resume from `pos`
            total_retries += 1
            log(f"NETWORK ERROR {url[-40:]} at {pos}/{size}: {type(e).__name__} {e}; retry {total_retries} from byte {pos}")
        if pos == before:
            fails += 1
            if fails >= 30:
                log(f"GAVE UP: no progress after 30 attempts at {pos}/{size}")
                sys.exit(1)
            time.sleep(float(os.environ.get("DL_RETRY_SLEEP", "5")))
        else:
            fails = 0
    try:
        out.flush()
    except OSError as e:
        if reader_closed(e):
            finish_reader_closed(total, url, pos, size, i, len(urls))
        log(f"WRITE ERROR on stdout (not the network): {type(e).__name__} {e}")
        sys.exit(2)
    log(f"file {i}/{len(urls)} complete: {size} bytes, {total_retries} network retries so far")
log(f"DONE: {len(urls)} file(s), {total} bytes transferred, {total_retries} network retries")
