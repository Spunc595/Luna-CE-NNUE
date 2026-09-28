// Prints, for each FEN given on stdin (one per line), the (stm_row, ntm_row) that bullet's REAL
// ChessBucketsMirrored::map_features produces for every piece on the board, using bulletformat's own
// FEN parser (ChessBoard::from_str) -- not a reimplementation.
// Output, one line per piece: FEN <idx> white=<0|1> pt=<0..5> sq=<0..63> stm_row=<n> ntm_row=<n>
// `white`/`sq` are bulletformat's OWN stm-relative encoding (bit3 of the piece byte / the square after its internal
// normalization), NOT the raw absolute FEN values -- printed so the Python side can replicate the SAME normalization
// independently (via ChessBoard::from_str's documented rule: for black to move, every square and every piece colour
// bit is flipped) rather than trust this probe blindly.
use std::io::{self, BufRead};
use std::str::FromStr;

use bullet_lib::game::inputs::{ChessBucketsMirrored, SparseInputType};
use bulletformat::ChessBoard;

fn main() {
    let buckets32: [usize; 32] = [0, 0, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3];
    let input = ChessBucketsMirrored::new(buckets32);

    let stdin = io::stdin();
    for (fen_idx, line) in stdin.lock().lines().enumerate() {
        let fen = line.unwrap();
        if fen.trim().is_empty() {
            continue;
        }
        let packed = format!("{} | 0 | 0.5", fen.trim());
        let board = ChessBoard::from_str(&packed).unwrap_or_else(|e| panic!("bad fen {fen}: {e}"));

        println!("KSQ {fen_idx} our_ksq={} opp_ksq={}", board.our_ksq(), board.opp_ksq());

        let mut rows = Vec::new();
        input.map_features(&board, |stm, ntm| rows.push((stm, ntm)));

        for ((piece, sq), (stm_row, ntm_row)) in board.into_iter().zip(rows.into_iter()) {
            let white = piece & 8 == 0;
            let pt = piece & 7;
            println!("FEN {fen_idx} white={} pt={} sq={} stm_row={} ntm_row={}", white as u8, pt, sq, stm_row, ntm_row);
        }
    }
}
