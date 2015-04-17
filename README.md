# webm.py

Just another bikeshed to encode webm VP9 videos. Nothing interesting here.

## Requirements

* Python 2.7+ or 3.2+
* FFmpeg 2+ compiled with libvpx and libopus

## Installation

Just save <https://raw.githubusercontent.com/Kagami/webm.py/master/webm.py>

Optionally put it somewhere in your `PATH`:
```bash
mkdir -p ~/.local/bin
wget https://raw.githubusercontent.com/Kagami/webm.py/master/webm.py -O ~/.local/bin/webm
chmod +x ~/.local/bin/webm
export PATH=$PATH:~/.local/bin
webm -h
```

## Usage

**NOTE:** Windows users may want to add Python executable to the `PATH`. See <https://docs.python.org/3/using/windows.html#excursus-setting-environment-variables> for details. Otherwise just type the full path to your `python.exe` location instead of `python`.

Show help:
```bash
python webm.py -h
```

Usage examples:
```bash
# Fit video to default limit
python webm.py -i in.mkv

# Fit video to 6 MiB
python webm.py -i in.mkv -l 6

# Set video bitrate to 600k
python webm.py -i in.mkv -vb 600

# Constrained quality
python webm.py -i in.mkv -crf 20

# CQ with custom limit
python webm.py -i in.mkv -crf 20 -l 6

# CQ with custom bitrate
python webm.py -i in.mkv -crf 20 -vb 600

# Constant quality
python webm.py -i in.mkv -crf 20 -vb 0
```
