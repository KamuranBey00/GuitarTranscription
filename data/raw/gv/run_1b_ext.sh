# External checks for the stage-1 candidates, all with the product decoding (tabcrnn_deep2.cal.json).
P=".venv/Scripts/python.exe -u -W ignore -m"
R=docs/results/gv/ext
mkdir -p $R
CAL=tabcrnn_deep2.cal.json
for m in deep2 g1e13 g1s2e15 s1be8; do
  A="--ckpt tabcrnn_$m.pt --cal $CAL"
  [ -f data/raw/gv/done_ext_${m}_b ] || { $P scripts.eval.gv.test_b_resynth $R/test_b_$m.csv $A --libs mg_soft_nylon rjs_lofi_nylon mdm_classical custom_classical_sf2 > $R/test_b_$m.log 2>&1 && touch data/raw/gv/done_ext_${m}_b; }
  [ -f data/raw/gv/done_ext_${m}_e ] || { $P scripts.eval.gv.test_e_real_vs_tab docs/results/gv/pairs_commons2.tsv $R/test_e_$m.csv $A > $R/test_e_$m.log 2>&1 && $P scripts.eval.gv.test_e_real_vs_tab docs/results/gv/pairs_youtube.tsv $R/test_f_$m.csv $A > $R/test_f_$m.log 2>&1 && touch data/raw/gv/done_ext_${m}_e; }
  [ -f data/raw/gv/done_ext_${m}_o ] || { $P scripts.eval.gv.own_recordings $A > $R/own_$m.log 2>&1 && touch data/raw/gv/done_ext_${m}_o; }
done
echo chain-done
