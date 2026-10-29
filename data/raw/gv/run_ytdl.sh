# Download the selected YouTube videos' audio as 22.05 kHz mono WAV (git-ignored; local research use only).
W="/c/Users/HP/AppData/Local/Temp/claude/c--Users-HP-Desktop-Projects-Graduation-Project/8fafcdd7-423c-4658-b808-9bd098837629/scratchpad/webtools"
FF=$(ls "$W"/imageio_ffmpeg/binaries/ffmpeg-*.exe | head -1)
OUT=data/raw/gv/yt_strings
mkdir -p $OUT
for id in $(.venv/Scripts/python.exe -c "import json; print(' '.join(v['id'] for v in json.load(open('data/raw/gv/yt_selected2.json', encoding='utf-8'))))"); do
  if [ ! -f "$OUT/$id.wav" ]; then
    PYTHONPATH="$W" .venv/Scripts/python.exe -m yt_dlp -q --no-warnings --no-playlist -f bestaudio -x --audio-format wav       --postprocessor-args "ffmpeg:-ac 1 -ar 22050" --ffmpeg-location "$FF" -o "$OUT/$id.%(ext)s" "https://www.youtube.com/watch?v=$id"       || echo "FAILED $id" >> data/raw/gv/ytdl_failed.txt
    sleep 3
  fi
  echo "$id" >> data/raw/gv/progress_ytdl.txt
done
echo download-done
