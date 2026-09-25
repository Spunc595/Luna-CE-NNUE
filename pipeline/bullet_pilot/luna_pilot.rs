// Luna phase-2 pilot: (768hm -> 1024)x2 -> 1 SCReLU, no buckets, float export (quantised afterwards by our own script
// so that every gate is ours). Env: LP_DATA (comma list of .bin), LP_SB (superbatches), LP_BPS (batches/superbatch),
// LP_BATCH, LP_THREADS, LP_OUT.
use bullet_lib::{
    game::inputs::Chess768hm,
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
    let threads: usize = env("LP_THREADS", 4);
    let sb: usize = env("LP_SB", 10);
    let bps: usize = env("LP_BPS", 100);
    let batch: usize = env("LP_BATCH", 4096);
    let out: String = env("LP_OUT", "checkpoints".to_string());
    let data: Vec<String> = std::env::var("LP_DATA").expect("LP_DATA").split(',').map(String::from).collect();
    let data: Vec<&str> = data.iter().map(|s| s.as_str()).collect();

    let mut trainer = ValueTrainerBuilder::default()
        .use_threads(threads)
        .optimiser(AdamW)
        .loss_fn(|output, target| output.sigmoid().squared_error(target))
        // raw f32 tensors: the quantisation and every gate are done by the conversion script
        .save_format(&[SavedFormat::id("l0w"), SavedFormat::id("l0b"), SavedFormat::id("l1w"), SavedFormat::id("l1b")])
        .inputs(Chess768hm)
        .dual_perspective()
        .build(|builder, stm, ntm| {
            let l0 = builder.new_affine("l0", 768, HIDDEN);
            let l1 = builder.new_affine("l1", 2 * HIDDEN, 1);
            let a = l0.forward(stm).screlu();
            let b = l0.forward(ntm).screlu();
            l1.forward(a.concat(b))
        });

    let loader = DirectSequentialDataLoader::new(&data);
    let schedule = TrainingSchedule {
        net_id: "luna_pilot".to_string(),
        eval_scale: 400.0,
        steps: TrainingSteps { batch_size: batch, batches_per_superbatch: bps, start_superbatch: 1, end_superbatch: sb },
        wdl_scheduler: wdl::ConstantWDL { value: 0.1 },
        lr_scheduler: lr::CosineDecayLR { initial_lr: 0.0004, final_lr: 0.0004 / 40.0, final_superbatch: sb },
        save_rate: sb,
    };
    let settings = LocalSettings { threads: 2, test_set: None, output_directory: &out, batch_queue_size: 32 };
    trainer.run(&schedule, &settings, &loader);
}
