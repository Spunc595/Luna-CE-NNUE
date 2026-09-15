"""
Errore di valutazione statica in cp contro Stockfish, per un net (doposprt.md,
sez. 1): quanto la rete guida bene la scelta della mossa non e' verificato da
round-trip/simmetria/saturazione (verificano solo che il motore riproduca
fedelmente la rete) -- questo confronta la rete stessa contro la verita' di
riferimento (Stockfish depth 8, gia' presente in val_final.tsv).

Usa UNA sessione persistente per motore (non un sottoprocesso per posizione):
"position fen X" + "eval" per la valutazione statica, "go depth N" +
"bestmove" per la concordanza sulla mossa migliore.

Uso:
  python measure_eval_error.py --val val_final.tsv --n-sample 2000 \
      --engine-a candidate/luna.exe --label-a SelfTrained \
      --engine-b baseline_akimbo_fresh/luna.exe --label-b Akimbo \
      --bestmove-depth 8
"""
import argparse
import random
import statistics
import subprocess


def sample_rows(path, n, seed):
    rows = []
    with open(path, "r", errors="ignore") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) != 5:
                continue
            rows.append(parts)  # fen, eval_cp, bestmove, wdl_mover, depth
    rng = random.Random(seed)
    return rng.sample(rows, min(n, len(rows)))


def query_engine(engine_path, rows, bestmove_depth):
    """Una sessione persistente, ma SINCRONA riga per riga: scrivi un
    comando, leggi la sua risposta, poi il prossimo -- non scrivere tutti
    i comandi in un colpo solo prima di leggere. Con poche posizioni la
    pipe assorbe tutto e sembra funzionare (il test a 20 posizioni e'
    passato); a 2000 il buffer si riempie e si blocca: il processo
    padre e' fermo in scrittura aspettando che il motore consumi, il
    motore e' fermo in scrittura sul proprio stdout aspettando che il
    padre legga -- un classico deadlock bidirezionale sulle pipe, non
    una posizione che manda in crash il motore."""
    proc = subprocess.Popen(
        [engine_path], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        text=True, bufsize=1, encoding="utf-8", errors="replace",
    )

    def send(cmd):
        proc.stdin.write(cmd + "\n")
        proc.stdin.flush()

    def read_until(prefix, timeout=30):
        import time
        t0 = time.time()
        while time.time() - t0 < timeout:
            line = proc.stdout.readline()
            if not line:
                raise RuntimeError(f"motore terminato inaspettatamente aspettando '{prefix}'")
            line = line.strip()
            if line.startswith(prefix):
                return line
        raise TimeoutError(f"timeout aspettando '{prefix}'")

    evals, bestmoves = [], []
    for fen, eval_cp, bestmove, wdl_mover, depth in rows:
        send(f"position fen {fen}")
        send("eval")
        evals.append(float(read_until("Evaluation:").split()[1]))
        if bestmove_depth:
            send(f"go depth {bestmove_depth}")
            bestmoves.append(read_until("bestmove").split()[1])

    send("quit")
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
    return evals, bestmoves


CLAMP = 2000  # stesso TARGET_EVAL_CLAMP_CP usato per costruire il target di training:
              # ~0,6% delle posizioni ha score di matto (+-15000) nel riferimento
              # Stockfish, che un eval STATICO (nessuna ricerca, non "vede" il matto)
              # non puo' avvicinare per costruzione -- non e' imprecisione della
              # rete, e senza il clamp un paio di questi casi dominano l'RMS.


def ranks(values):
    # Rango medio in caso di parita' (standard per Spearman): ordina, assegna
    # posizioni, poi fa la media dei ranghi per i valori uguali.
    order = sorted(range(len(values)), key=lambda i: values[i])
    r = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg_rank = (i + j) / 2 + 1
        for k in range(i, j + 1):
            r[order[k]] = avg_rank
        i = j + 1
    return r


def spearman(a, b):
    ra, rb = ranks(a), ranks(b)
    mean_ra, mean_rb = statistics.mean(ra), statistics.mean(rb)
    cov = sum((x - mean_ra) * (y - mean_rb) for x, y in zip(ra, rb))
    var_a = sum((x - mean_ra) ** 2 for x in ra)
    var_b = sum((y - mean_rb) ** 2 for y in rb)
    return cov / (var_a * var_b) ** 0.5 if var_a > 0 and var_b > 0 else 0.0


def report(label, engine_evals, stockfish_evals, engine_bestmoves, stockfish_bestmoves):
    n_clamped = sum(1 for s in stockfish_evals if abs(s) > CLAMP)
    stockfish_c = [max(-CLAMP, min(CLAMP, s)) for s in stockfish_evals]
    engine_c = [max(-CLAMP, min(CLAMP, e)) for e in engine_evals]
    errors = [e - s for e, s in zip(engine_c, stockfish_c)]
    mae = statistics.mean(abs(e) for e in errors)
    rmse = (statistics.mean(e ** 2 for e in errors)) ** 0.5
    std = statistics.pstdev(errors)
    # Spearman su tutto il campione, SENZA clamp: e' scale/offset-free per
    # costruzione (dipende solo dall'ordinamento), quindi i punteggi di
    # matto non hanno bisogno dello stesso trattamento speciale del MAE/RMS
    # -- un matto vero dovrebbe comunque finire in cima all'ordinamento.
    rho = spearman(engine_evals, stockfish_evals)
    print(f"=== {label} (n={len(errors):,}, {n_clamped} posizioni con |riferimento|>{CLAMP} clampate su MAE/RMS) ===")
    print(f"  errore medio assoluto: {mae:.2f} cp")
    print(f"  RMS:                   {rmse:.2f} cp")
    print(f"  deviazione standard:   {std:.2f} cp")
    print(f"  correlazione di rango (Spearman) vs Stockfish: {rho:.4f}")
    if engine_bestmoves and stockfish_bestmoves:
        agree = sum(1 for a, b in zip(engine_bestmoves, stockfish_bestmoves) if a == b)
        print(f"  concordanza mossa migliore: {agree}/{len(engine_bestmoves)} ({agree/len(engine_bestmoves)*100:.1f}%)")
    print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--val", required=True)
    ap.add_argument("--n-sample", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--engine-a", required=True)
    ap.add_argument("--label-a", default="A")
    ap.add_argument("--engine-b", required=True)
    ap.add_argument("--label-b", default="B")
    ap.add_argument("--bestmove-depth", type=int, default=0,
                     help="0 = salta la concordanza sulla mossa migliore (piu' lento)")
    args = ap.parse_args()

    rows = sample_rows(args.val, args.n_sample, args.seed)
    stockfish_evals = [float(r[1]) for r in rows]
    stockfish_bestmoves = [r[2] for r in rows]

    for engine_path, label in [(args.engine_a, args.label_a), (args.engine_b, args.label_b)]:
        evals, bestmoves = query_engine(engine_path, rows, args.bestmove_depth)
        report(label, evals, stockfish_evals, bestmoves if args.bestmove_depth else None, stockfish_bestmoves)


if __name__ == "__main__":
    main()
