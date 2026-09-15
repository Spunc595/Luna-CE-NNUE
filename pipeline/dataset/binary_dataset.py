"""
Lettore del formato binario prodotto da convert_to_binary.py. Dataset a
accesso casuale su array numpy memory-mapped (nessun parsing, nessuna
chess.Board() per riga): il collate ricostruisce il formato "ragged"
(indici+offset) che EmbeddingBag si aspetta con operazioni vettoriali
(maschera booleana + cumsum), non un ciclo Python per posizione.
"""
import numpy as np
import torch
from torch.utils.data import Dataset


class BinaryHalfKADataset(Dataset):
    def __init__(self, prefix: str):
        self.us = np.load(prefix + ".us.npy", mmap_mode="r")
        self.them = np.load(prefix + ".them.npy", mmap_mode="r")
        self.targets = np.load(prefix + ".targets.npy", mmap_mode="r")
        assert len(self.us) == len(self.them) == len(self.targets)

    def __len__(self):
        return len(self.targets)

    def __getitem__(self, idx):
        return self.us[idx], self.them[idx], self.targets[idx]


def binary_collate_fn(batch):
    us_batch = np.stack([b[0] for b in batch])
    them_batch = np.stack([b[1] for b in batch])
    targets = torch.from_numpy(np.array([b[2] for b in batch], dtype=np.float32))

    us_t = torch.from_numpy(us_batch.astype(np.int64))
    them_t = torch.from_numpy(them_batch.astype(np.int64))

    def to_ragged(padded):
        mask = padded >= 0
        counts = mask.sum(dim=1)
        offsets = torch.cat([torch.zeros(1, dtype=torch.long), counts.cumsum(0)[:-1]])
        flat = padded[mask]
        return flat, offsets

    us_flat, us_off = to_ragged(us_t)
    them_flat, them_off = to_ragged(them_t)
    return us_flat, us_off, them_flat, them_off, targets
