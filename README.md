# webm.py

Just another bikeshed to encode webm VP9 videos. Nothing interesting here.

## Requirements

* [Python](https://www.python.org/downloads/) 2.7+ or 3.2+
* [FFmpeg](https://ffmpeg.org/download.html) 2+ compiled with libvpx and libopus
* [mpv](http://mpv.io/installation/) 0.8+ compiled with Lua support, *for interactive mode only*

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

Or with pip:
```bash
[sudo] pip install webm
```

## Usage

**NOTE:** Windows users may want to add Python executable to the `PATH`. See <https://docs.python.org/3/using/windows.html#excursus-setting-environment-variables> for details. Otherwise just type the full path to your `python.exe` location instead of `python`.

Show help:
```bash
python webm.py -h
```

Examples:
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

### Interactive mode

Pass `-p` flag to interactively select cut frargment/crop area with mpv. Demo:

[![](https://i.imgur.com/JIogF33.png)](https://i.imgur.com/GjDWq3X.png)

## License

webm.py - encode webm videos

Written in 2015 by Kagami Hiiragi <kagami@genshiken.org>

To the extent possible under law, the author(s) have dedicated all copyright and related and neighboring rights to this software to the public domain worldwide. This software is distributed without any warranty.

You should have received a copy of the CC0 Public Domain Dedication along with this software. If not, see <http://creativecommons.org/publicdomain/zero/1.0/>.
