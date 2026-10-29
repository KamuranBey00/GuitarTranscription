bash data/raw/gv/run_ytdl.sh
.venv/Scripts/python.exe -u -W ignore -m scripts.eval.gv.yt_string_labels > docs/results/gv/yt_string_labels.log 2> data/raw/gv/yt_string_labels.err
touch data/raw/gv/yt2_done
