# webm.py

Just another bikeshed to encode webm VP9 videos. Nothing interesting here.

## Requirements

* Python 2.7+ or 3.2+
* FFmpeg 2+ compiled with libvpx and libopus

## Installation

Just download <https://raw.githubusercontent.com/Kagami/webm.py/master/webm.py>.

Optionally put it somewhere in your `PATH`:
```bash
mkdir -p ~/.local/bin
wget https://raw.githubusercontent.com/Kagami/webm.py/master/webm.py -O ~/.local/bin/webm
chmod +x ~/.local/bin/webm
```

## Usage

**NOTE:** Windows users may want to add python executable to the `PATH`. See <https://docs.python.org/3/using/windows.html#excursus-setting-environment-variables> for details. Otherwise just type the full path to `python.exe` location.

Show help:
```bash
$ python webm.py -h
```

Usage examples
```bash
# Fit video to default limit:
% python {title} -i in.mkv

# Fit video to 6 MiB:
% python {title} -i in.mkv -l 6

# Set video bitrate to 600k:
% python {title} -i in.mkv -vb 600

# Constrained quality:
% python {title} -i in.mkv -crf 20

# CQ with custom limit:
% python {title} -i in.mkv -crf 20 -l 6

# CQ with custom bitrate:
% python {title} -i in.mkv -crf 20 -vb 600

# Constant quality:
% python {title} -i in.mkv -crf 20 -vb 0
```
