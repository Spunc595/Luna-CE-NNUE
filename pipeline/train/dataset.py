"""
Legge il formato TSV a 5 colonne prodotto da annotate_incremental.py (fen,
eval_cp, bestmove, wdl_mover, depth — entrambi eval_cp e wdl_mover gia' dal
punto di vista del lato a muovere) e produce esempi di training HalfKA:
indici di feature attivi per entrambe le prospettive, piu' un target in
SPAZIO PROBABILITA' [0,1] che fonde l'eval Stockfish col risultato di
partita.

Rispetto alla versione precedente (formato a 6 colonne di
resolve_truncated_wdl.py, con "result" assoluto lato bianco), qui non
serve piu' aprire la board per determinare il tratto ai fini
dell'etichetta: annotate_incremental.py ha gia' fatto quella conversione
una volta sola, a monte. board.fen() resta comunque necessario per
active_features() E per riordinare gli indici in "chi muove/avversario"
(vedi sotto) — non solo per l'indicizzazione delle feature.

BUG CORRETTO 2026-09-08 (bugtraining.md): active_features() ritorna
(white_indices, black_indices) — indici dalla prospettiva del bianco e
del nero, non "di chi muove". model.py si aspetta (us_idx, them_idx) con
"us" = lato A MUOVERE (output_weights[0] si accoppia col lato al tratto,
combacia con evaluate_from_accumulator in nnue.rs), mentre il target qui
e' gia' relativo al lato a muovere. train.py chiamava il modello passando
sempre white_idx come "us" — corretto quando tocca al bianco, invertito
quando tocca al nero. Su meta' delle posizioni il modello riceveva gli
indici come se stesse valutando dal punto di vista sbagliato rispetto al
target: gradiente contraddittorio sugli stessi pesi condivisi da meta' dei
dati, il modello collassava su una costante (val loss peggiore della sola
varianza dei target). Fix: riordinare qui, una volta sola, cosi'
train.py riceve sempre (us_idx, them_idx) gia' allineati al target.

Il target resta in [0,1] fino alla loss (train.py applica la stessa
sigmoide K alla predizione del modello, che continua a produrre
centipedine in forward() — vedi model.py).
"""
import math

import chess
import torch
from torch.utils.data import IterableDataset

from feature_set import active_features

# Clamp sull'eval usato per COSTRUIRE IL TARGET (non sui dati su disco, che
# restano quelli annotati): lo 0,61% delle posizioni ha punteggi di matto
# intorno a +-15.000, che sigmoide(K*eval) schiaccia comunque a 0/1 ma senza
# beneficio per il training — bugtraining.md, sez. 4.
TARGET_EVAL_CLAMP_CP = 2000

# Sigmoide in base naturale equivalente a 1/(1+10^(-cp/400)) (convenzione
# Elo-style standard): K = ln(10)/400. Stessa K va usata in train.py per
# trasformare l'output del modello (in cp) nella stessa scala [0,1] prima
# della loss — se le due K divergono la loss confronta due spazi diversi.
K = math.log(10) / 400.0


def _read_rows(paths):
    for path in paths:
        with open(path, "r", errors="ignore") as f:
            for line in f:
                line = line.rstrip("\n")
                if not line:
                    continue
                parts = line.split("\t")
                if len(parts) != 5:
                    continue
                yield parts


class HalfKADataset(IterableDataset):
    def __init__(self, tsv_paths, eval_lambda: float = 0.7):
        # Accetta un path singolo o una lista, cosi' train.py puo' passare
        # piu' shard senza doverli concatenare su disco.
        self.tsv_paths = [tsv_paths] if isinstance(tsv_paths, str) else list(tsv_paths)
        self.eval_lambda = eval_lambda

    def __iter__(self):
        for fen, eval_cp_str, bestmove, wdl_mover_str, depth in _read_rows(self.tsv_paths):
            eval_cp = max(-TARGET_EVAL_CLAMP_CP, min(TARGET_EVAL_CLAMP_CP, float(eval_cp_str)))
            eval_wdl_mover = 1.0 / (1.0 + math.exp(-K * eval_cp))
            wdl_mover = float(wdl_mover_str)

            # Fusione in spazio probabilita', punto di vista del lato a
            # muovere — resta [0,1], nessun ritorno a centipedine qui.
            target = self.eval_lambda * eval_wdl_mover + (1.0 - self.eval_lambda) * wdl_mover

            board = chess.Board(fen)
            white_idx, black_idx = active_features(board)
            # us/them, non bianco/nero fisso: il target sopra e' gia'
            # relativo al lato a muovere, quindi gli indici devono esserlo
            # allo stesso modo, riga per riga.
            if board.turn == chess.WHITE:
                us_idx, them_idx = white_idx, black_idx
            else:
                us_idx, them_idx = black_idx, white_idx
            yield us_idx, them_idx, target


def collate_fn(batch):
    """Impacchetta una lista di (us_idx, them_idx, target) nel formato
    indici+offset che nn.EmbeddingBag si aspetta. "us"/"them" = lato a
    muovere/avversario, non bianco/nero fisso — vedi HalfKADataset.__iter__."""
    us_all, us_offsets = [], [0]
    them_all, them_offsets = [], [0]
    targets = []

    for us_idx, them_idx, target in batch:
        us_all.extend(us_idx)
        us_offsets.append(us_offsets[-1] + len(us_idx))
        them_all.extend(them_idx)
        them_offsets.append(them_offsets[-1] + len(them_idx))
        targets.append(target)

    return (
        torch.tensor(us_all, dtype=torch.long),
        torch.tensor(us_offsets[:-1], dtype=torch.long),
        torch.tensor(them_all, dtype=torch.long),
        torch.tensor(them_offsets[:-1], dtype=torch.long),
        torch.tensor(targets, dtype=torch.float32),
    )
