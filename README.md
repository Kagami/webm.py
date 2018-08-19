# webm.py

Cross-platform command-line WebM converter.

## Features

* No Python dependencies, single source file
* Supports encoding to VP8, VP9 and AV1, with Opus or Vorbis
* 2-pass encoding, user-friendly defaults, flexible set of options
* Provides graphical [interactive mode](#interactive-mode) to cut/crop input video with mpv
* Can burn subtitles, fit to limit, use external audio track and many more

## Requirements

* [Python](https://www.python.org/downloads/) 2.7+ or 3.2+
* [FFmpeg](https://ffmpeg.org/download.html) 2+ compiled with libvpx and libopus
* [mpv](http://mpv.io/installation/) 0.17+ compiled with Lua support, *for interactive mode only*

Make sure to set `Add to PATH` option in Python for Windows installer.

FFmpeg and mpv executables must be in `PATH` or set their location with
`WEBM_FFMPEG` and `WEBM_MPV` environment variables.

## Installation

```bash
pip install webm
```

Or just save https://raw.githubusercontent.com/Kagami/webm.py/master/webm.py
and put in your `PATH`.

### Windows, Python 2 and non-ASCII filenames

Unicode filenames won't work on Windows with Python 2 due to Python bugs. Use
Python 3 if you can but if not an option set `PYTHONIOENCODING` environment
variable to `utf-8` and run:

```bash
pip install subprocessww
```

## Usage

Show help:

```bash
webm -h
```

Examples:

```bash
# Fit video to default limit
webm -i in.mkv

# Fit video to 6 MiB
webm -i in.mkv -l 6

# Set video bitrate to 600k
webm -i in.mkv -vb 600

# Constrained quality
webm -i in.mkv -crf 20

# Constant quality
webm -i in.mkv -crf 20 -vb 0

# Encode with AV1
webm -i in.mkv -av1

# Encode with VP8 & Vorbis
webm -i in.mkv -vp8
```

### Interactive mode

Pass `-p` flag to interactively select cut frargment and crop area with mpv.
Show help for interactive mode:

```bash
webm -hi
```

## Related links

[webm.py wiki](https://github.com/Kagami/webm.py/wiki) contains some encoding
tricks and links to documentation on WebM/VPx.

## License

webm.py is licensed under [CC0](COPYING).
