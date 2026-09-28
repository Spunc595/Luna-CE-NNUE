// Luna phase-2b pilot: 4 king buckets, horizontally mirrored (ChessBucketsMirrored), (768x4 -> 1024)x2 -> 1 SCReLU.
// BUCKETS32 here MUST match src/nnue.rs's BUCKETS table exactly (verified against the real bullet Rust code and
// against Luna's own transcription, see pipeline/bullet_pilot/bucket_layout_check.py -- do not edit this array
// without re-running that check). Same recipe otherwise as luna_pilot.rs (the no-bucket pilot): S2 data, AdamW,
// eval_scale 400, WDL fraction ramp 0.0 -> 0.1, lr cosine 4e-4 -> peak/40.
// Env: LP_DATA (comma list of .bin), LP_SB, LP_BPS, LP_BATCH, LP_THREADS, LP_OUT, LP_SAVE, LP_RESUME, LP_START.
use bullet_lib::{
    game::inputs::ChessBucketsMirrored,
    nn::optimiser::AdamW,
    trainer::{
        save::SavedFormat,
        schedule::{TrainingSchedule, TrainingSteps, lr, wdl},
        settings::LocalSettings,
    },
    value::{ValueTrainerBuilder, loader::DirectSequentialDataLoader},
};

fn env<T: std::str::FromStr>(k: &str, d: T) -> T {
    std::env::var(k).ok().and_then(|v| v.parse().ok()).unwrap_or(d)
}

fn main() {
    const HIDDEN: usize = 1024;
    // Luna's BUCKETS table (src/nnue.rs), read as bullet's ChessBucketsMirrored 32-entry (rank-major, file a-d folded)
    // table: king a1/b1 -> 0, c1/d1 -> 1, rank2 a-d -> 2, ranks3-8 a-d -> 3.
    const BUCKETS32: [usize; 32] = [0, 0, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3];
    const NUM_BUCKETS: usize = 4; // max(BUCKETS32) + 1

    let threads: usize = env("LP_THREADS", 4);
    let sb: usize = env("LP_SB", 10);
    let bps: usize = env("LP_BPS", 100);
    let batch: usize = env("LP_BATCH", 4096);
    let out: String = env("LP_OUT", "checkpoints".to_string());
    let save: usize = env("LP_SAVE", sb);
    let start_sb: usize = env("LP_START", 1);
    let resume: String = env("LP_RESUME", String::new());
    let data: Vec<String> = std::env::var("LP_DATA").expect("LP_DATA").split(',').map(String::from).collect();
    let data: Vec<&str> = data.iter().map(|s| s.as_str()).collect();

    let mut trainer = ValueTrainerBuilder::default()
        .use_threads(threads)
        .optimiser(AdamW)
        .loss_fn(|output, target| output.sigmoid().squared_error(target))
        .save_format(&[SavedFormat::id("l0w"), SavedFormat::id("l0b"), SavedFormat::id("l1w"), SavedFormat::id("l1b")])
        .inputs(ChessBucketsMirrored::new(BUCKETS32))
        .dual_perspective()
        .build(|builder, stm, ntm| {
            let l0 = builder.new_affine("l0", 768 * NUM_BUCKETS, HIDDEN);
            let l1 = builder.new_affine("l1", 2 * HIDDEN, 1);
            let a = l0.forward(stm).screlu();
            let b = l0.forward(ntm).screlu();
            l1.forward(a.concat(b))
        });

    if !resume.is_empty() {
        trainer.load_from_checkpoint(&resume);
    }
    let loader = DirectSequentialDataLoader::new(&data);
    let schedule = TrainingSchedule {
        net_id: "luna_pilot_buckets".to_string(),
        eval_scale: 400.0,
        steps: TrainingSteps { batch_size: batch, batches_per_superbatch: bps, start_superbatch: start_sb, end_superbatch: sb },
        wdl_scheduler: wdl::CosineDecayWDL { start: 0.0, end: 0.1, final_superbatch: sb },
        lr_scheduler: lr::CosineDecayLR { initial_lr: 0.0004, final_lr: 0.0004 / 40.0, final_superbatch: sb },
        save_rate: save,
    };
    let settings = LocalSettings { threads: 2, test_set: None, output_directory: &out, batch_queue_size: 32 };
    trainer.run(&schedule, &settings, &loader);
}
