set -e
P=".venv/Scripts/python.exe -W ignore -m"
R=docs/results/gv
for m in g10e10 g1e13; do
  $P scripts.eval.eval_pitch --ckpt tabcrnn_$m.pt --splits gaps_test val val_comp --criterion mix --save-cal checkpoints/tabcrnn_$m.cal.json > $R/cal_1a_$m.log 2>&1
  $P scripts.eval.gv.calibrate_reattack --grid reattack --ckpt tabcrnn_$m.pt --cal tabcrnn_$m.cal.json --write > $R/gates_1a_$m.log 2>&1
  $P scripts.eval.gv.calibrate_reattack --grid fallback --ckpt tabcrnn_$m.pt --cal tabcrnn_$m.cal.json --write >> $R/gates_1a_$m.log 2>&1
  touch data/raw/gv/done_${m}_gates
done
$P scripts.eval.gv.compare_ckpts tabcrnn_deep2.pt tabcrnn_g10e10.pt tabcrnn_g1e13.pt --test --own-cal 2>&1 | grep -v -i "warn\|n_fft" > $R/compare_1a_owncal.log
echo chain-done
