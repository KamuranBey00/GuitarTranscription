set -e
P=".venv/Scripts/python.exe -W ignore -m"
R=docs/results/gv
F="--init tabcrnn_deep2.pt --epochs 15 --lr 1e-4 --onset-soft 0.3 --gs-pitch-weight 1.0 --short-frames 5 --short-weight 2.0 --repeat-weight 3 --pitch-weight 2 --offset-weight 1 --valley-weight 5 --frag-weight 3 --oversample 3 --deep 2 --pitch-onset-weight 1 --new-lr-mult 3 --save-epochs"
$P scripts.data.build_synth_gaps > $R/synth_1b.log 2>&1
$P scripts.train.train_onset $F --degrade-root data/cache/synth --degrade-p 0.5 --ckpt tabcrnn_s1b_l.pt > $R/train_1b_synth.log 2>&1
$P scripts.train.train_onset $F --seed 2 --ckpt tabcrnn_g1s2_l.pt > $R/train_1b_control_seed2.log 2>&1
C=""; for p in s1b_l g1s2_l; do for e in $(seq 1 15); do C="$C tabcrnn_${p}_ep$e.pt"; done; done
$P scripts.eval.gv.compare_ckpts $C 2>&1 | grep -v -i "warn\|n_fft" > $R/compare_1b.log
echo chain-done
