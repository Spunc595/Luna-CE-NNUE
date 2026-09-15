# Network licensing

**`luna_gen1.nnue`, `luna_gen2.nnue`** — trained from scratch by Daniele
Marpino on his own pipeline (`pipeline/train/`), on data generated
entirely by Luna's own search/evaluation (see `LINEAGE.md` and
`COMPLIANCE.md`). They are the engine author's own work, not derived from
third-party networks. **Licensed GPLv3**, same as the engine itself and
this repository (see `LICENSE`) — a coherent choice: same author, same
project, same license.

**This is not the network embedded by default in Luna's binary**
(`resources/net.bin` in the engine repository, akimbo by Jamie Whiting,
MIT — see the engine's README). That network doesn't live in this
repository: only the self-produced networks from the gen1/gen2/...
bootstrap chain live here.

## Checksums

`luna_genN.nnue.sha256` next to each file, computed locally at commit
time — see `checksums/genN/README.md` for the checksum status of that
generation's full dataset (some still TODO).
