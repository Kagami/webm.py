#!/usr/bin/env python

"""
convert videos to WebM format using FFmpeg

features:
  - encodes input video to WebM container with VP9 and Opus
  - uses 2-pass encoding, has optional VP8/Vorbis and album art modes
  - fits output file to the size limit by default
  - allows to select video/audio streams and external audio track
  - can burn subtitles into the video
  - flexible set of options and ability to pass raw flags to FFmpeg
  - interactive mode to cut/crop input video with mpv

dependencies:
  - Python 2.7+ or 3.2+ (using: {pythonv})
  - FFmpeg 2+ compiled with libvpx and libopus (using: {ffmpegv})
  - mpv 0.17+ compiled with Lua support, optional (using: {mpvv})

encoding modes:
  - by default bitrate calculated to fit the output video to limit
  - you may specify custom bitrate to use
  - -crf option enables constrained quality mode
  - -crf and -vb 0 enable constant quality mode

examples:
  (use `{stitle}' instead of `python {title}' if you installed it with pip)
  - fit video to default limit: python {title} -i in.mkv
  - fit video to 6 MiB:         python {title} -i in.mkv -l 6
  - set video bitrate to 600k:  python {title} -i in.mkv -vb 600
  - constrained quality:        python {title} -i in.mkv -crf 20
  - constant quality:           python {title} -i in.mkv -crf 20 -vb 0
  - encode with VP8 & Vorbis:   python {title} -i in.mkv -vp8
  - make album art video:       python {title} -cover -i pic.png -aa song.flac

use custom location of FFmpeg executable:
  - *nix:    WEBM_FFMPEG=/opt/ffmpeg/ffmpeg python {title} -i in.mkv
  - Windows: set WEBM_FFMPEG=C:\\ffmpeg.exe & python {title} -i in.mkv
similarly you can set custom location of mpv executable with WEBM_MPV
"""

# Since there is no way to wrap future imports in try/except, we use
# hack with comment. See <http://stackoverflow.com/q/388069> for
# details.
from __future__ import division  # Install Python 2.7+ or 3.2+
from __future__ import print_function  # Install Python 2.7+ or 3.2+
from __future__ import unicode_literals  # Install Python 2.7+ or 3.2+

import os
import re
import sys
import time
import shlex
import locale
import tempfile
import traceback
import subprocess


__title__ = 'webm.py'
__stitle__ = 'webm'
__version__ = '0.10.0'
__license__ = 'CC0'


_PY2 = sys.version_info[0] == 2
_TEXT_TYPE = unicode if _PY2 else str
_NUM_TYPES = (int, long, float) if _PY2 else (int, float)
_input = raw_input if _PY2 else input


# We can't use e.g. ``sys.stdout.encoding`` because user can redirect
# the output so in Python2 it would return ``None``. Seems like
# ``getpreferredencoding`` is the best remaining method.
# NOTE: Python 3 uses ``getfilesystemencoding`` in ``os.getenv`` and
# ``getpreferredencoding`` in ``subprocess`` module.
# XXX: We will fail early with ugly traceback on any of this toplevel
# decodes if encoding is wrong.
OS_ENCODING = locale.getpreferredencoding() or 'utf-8'


ARGS = sys.argv[1:]
# In Python2 ``sys.argv`` is a list of bytes. See:
# <http://stackoverflow.com/q/4012571>,
# <https://bugs.python.org/issue2128> for details.
if _PY2: ARGS = [arg.decode(OS_ENCODING) for arg in ARGS]


# Python3 returns unicode here fortunately.
FFMPEG_PATH = os.getenv('WEBM_FFMPEG', 'ffmpeg')
if _PY2: FFMPEG_PATH = FFMPEG_PATH.decode(OS_ENCODING)


MPV_PATH = os.getenv('WEBM_MPV', 'mpv')
if _PY2: MPV_PATH = MPV_PATH.decode(OS_ENCODING)


def _ffmpeg(args, check_code=True, debug=False):
    args = [FFMPEG_PATH] + args
    if debug:
        print('='*50 + '\n' + ' '.join(args) + '\n' + '='*50, file=sys.stderr)
    try:
        p = subprocess.Popen(args)
    except Exception as exc:
        raise Exception('failed to run FFmpeg ({})'.format(exc))
    p.communicate()
    if check_code and p.returncode != 0:
        raise Exception('FFmpeg exited with error')
    return {'code': p.returncode}


def _ffmpeg_output(args, check_code=True, debug=False):
    args = [FFMPEG_PATH] + args
    if debug:
        print('='*50 + '\n' + ' '.join(args) + '\n' + '='*50, file=sys.stderr)
    try:
        p = subprocess.Popen(
                args, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True)
    except Exception as exc:
        raise Exception('failed to run FFmpeg ({})'.format(exc))
    out, err = p.communicate()
    if check_code and p.returncode != 0:
        raise Exception('FFmpeg exited with error')
    if _PY2:
        out = out.decode(OS_ENCODING)
        # XXX: Error might occur if video file has corrupted/wrong
        # encoding of metadata. Note that you need to use py2 in order
        # to get effect of this, ``Popen(universal_newlines=True)`` on
        # py3 always returns unicode.
        err = err.decode(OS_ENCODING, 'ignore')
    return {'stdout': out, 'stderr': err, 'code': p.returncode}


def _mpv_output(args, check_code=True, catch_stdout=True, debug=False):
    args = [MPV_PATH] + args
    if debug:
        print('='*50 + '\n' + ' '.join(args) + '\n' + '='*50, file=sys.stderr)
    kwargs = {'stdout': subprocess.PIPE} if catch_stdout else {}
    try:
        p = subprocess.Popen(
            args, stderr=subprocess.PIPE,
            universal_newlines=True,
            **kwargs)
    except Exception as exc:
        raise Exception('failed to run mpv ({})'.format(exc))
    out, err = p.communicate()
    if check_code and p.returncode != 0:
        raise Exception('mpv exited with error')
    if _PY2:
        if catch_stdout:
            out = out.decode(OS_ENCODING)
        err = err.decode(OS_ENCODING)
    return {'stdout': out, 'stderr': err, 'code': p.returncode}


def check_dependencies():
    pythonv = '{}.{}.{}'.format(*sys.version_info)
    if ((sys.version_info[0] == 2 and sys.version_info[1] < 7) or
            (sys.version_info[0] == 3 and sys.version_info[1] < 2) or
            # Just in case... Also don't restrict <= 3, script might
            # work on Python 4+ too.
            sys.version_info[0] < 2):
        raise Exception(
            'Python version must be 2.7+ or 3.2+, using: {}'.format(pythonv))

    ffverout = _ffmpeg_output(['-version'])['stdout']
    try:
        line = ffverout.split('\n', 1)[0]
        ffmpegv = re.match(r'ffmpeg version (\S+)', line).group(1)
    except Exception:
        raise Exception('cannot parse FFmpeg version')
    # NOTE: Checking only for '^x.y.z', possible non-numeric symbols
    # after 'z' don't matter.
    if re.match(r'\d+\.\d+\.\d+', ffmpegv):
        if int(ffmpegv.split('.', 1)[0]) < 2:
            raise Exception('FFmpeg version must be 2+, '
                            'using: {}'.format(ffmpegv))
    else:
        # Most probably version from git. Do nothing.
        pass

    codecout = _ffmpeg_output(['-hide_banner', '-codecs'])['stdout']
    if not re.search(r'\bencoders:.*\blibvpx\b', codecout):
        raise Exception('FFmpeg is not compiled with libvpx support')
    if not re.search(r'\bencoders:.*\blibvpx-vp9\b', codecout):
        raise Exception('used libvpx has not VP9 support')
    if not re.search(r'\bencoders:.*\blibopus\b', codecout):
        raise Exception('FFmpeg is not compiled with libopus support')
    if ('-vorbis' in ARGS or
            ('-vp8' in ARGS and not '-opus' in ARGS)):
        if not re.search(r'\bencoders:.*\blibvorbis\b', codecout):
            raise Exception('FFmpeg is not compiled with libvorbis support')

    mpvv = 'no'
    need_mpv = '-p' in ARGS
    try:
        mverout = _mpv_output(['--version'])['stdout']
    except Exception:
        if need_mpv:
            raise
    else:
        try:
            mpvv = re.match(r'mpv (\S+)', mverout).group(1)
        except Exception:
            if need_mpv:
                raise Exception('cannot parse mpv version')
        else:
            # NOTE: Checking only for '^x.y.z', possible non-numeric symbols
            # after 'z' don't matter.
            if need_mpv and re.match(r'\d+\.\d+\.\d+', mpvv):
                major, minor, _ = mpvv.split('.', 2)
                if int(major) == 0 and int(minor) < 17:
                    raise Exception('mpv version must be 0.17+, '
                                    'using: {}'.format(mpvv))
            else:
                # Most probably version from git. Do nothing.
                pass

    return {'pythonv': pythonv, 'ffmpegv': ffmpegv, 'mpvv': mpvv}


def _is_same_paths(path1, path2):
    def normalize(path):
        return os.path.normcase(os.path.abspath(path))

    # Resolve relative paths and cases.
    if normalize(path1) == normalize(path2):
        return True
    # Resolve symlinks and hardlinks.
    try:
        return os.stat(path1).st_ino == os.stat(path2).st_ino
    except Exception:
        return False


def _vorbisq2bitrate(q):
    return {
        -1: 45,
         0: 64,
         1: 80,
         2: 96,
         3: 112,
         4: 128,
         5: 160,
         6: 192,
         7: 224,
         8: 256,
         9: 320,
        10: 500,
    }[q]


def _get_main_infile(options):
    return options.infile if options.cover is None else options.aa


def process_options(verinfo):
    import argparse
    doc = __doc__.format(stitle=__stitle__, title=__title__, **verinfo)

    parser = argparse.ArgumentParser(
        prog=__title__,
        description=doc,
        formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument(
        '-hi', '--help-imode', action='store_true',
        help='show help on interactive mode')
    parser.add_argument(
        '-V', '--version',
        action='version',
        version='%(prog)s ' + __version__)
    parser.add_argument(
        '-v', action='store_true', dest='verbose',
        help='Enable verbose mode')
    parser.add_argument(
        '-i', dest='infile', metavar='infile', required=True,
        help='input file, e.g. infile.mkv (required)')
    parser.add_argument(
        'outfile', nargs='?',
        help='output file, e.g. outfile.webm\n'
            'defaults to infile_hh:mm:ss[.x]-hh:mm:ss[.x].webm if you\n'
            'specified a starting/ending time or duration, otherwise\n'
            'defaults to infile.webm')
    parser.add_argument(
        '-ss', metavar='position',
        help='seek in input file to the given position\n'
             'position may be either in seconds or in "hh:mm:ss[.xxx]" form')
    parser.add_argument(
        '-t', metavar='duration',
        help='limit the duration of data read from the input file\n'
             'duration may be a number in seconds, or in "hh:mm:ss[.xxx]" '
             'form\n'
             '-t and -to are mutually exclusive')
    parser.add_argument(
        '-to', metavar='position',
        help='stop writing the output at position\n'
             'position may be either in seconds or in "hh:mm:ss[.xxx]" form')
    parser.add_argument(
        '-l', metavar='limit', type=float,
        help='target filesize limit in mebibytes (default: 8)\n'
             '-l and -vb are mutually exclusive')
    parser.add_argument(
        '-vp8', action='store_true',
        help='use VP8 codec for video, implies -vorbis')
    parser.add_argument(
        '-vw', metavar='width', type=int,
        help='output video width in pixels, e.g. 1280\n'
             'when overriding either the default width or height, the output\n'
             'will be scaled to the correct aspect ratio, but not when you\n'
             'override both.')
    parser.add_argument(
        '-vh', metavar='height', type=int,
        help='output video height, e.g. 720')
    parser.add_argument(
        '-vb', metavar='bitrate', type=float,
        help='target video bitrate in kbits')
    parser.add_argument(
        '-crf', metavar='crf', type=int,
        help='set the video quality level (0..63)')
    parser.add_argument(
        '-qmin', metavar='qmin', type=int,
        help='set minimum (best) video quality level (0..63)')
    parser.add_argument(
        '-qmax', metavar='qmax', type=int,
        help='set maximum (worst) video quality level (0..63)')
    parser.add_argument(
        '-vs', metavar='videostream',
        help='video stream number to use (default: best)\n'
             "that's absolute value obtainable with ffmpeg -i infile")
    parser.add_argument(
        '-vf', metavar='videofilters',
        help='additional video filters to use')
    parser.add_argument(
        '-vfi', metavar='videofilters',
        help='insert video filters at the start of filter chain')
    parser.add_argument(
        '-an', action='store_true',
        help='strip audio from the output file\n'
             'you cannot use -an with -ab, -aq, -aa, -as, -af')
    parser.add_argument(
        '-opus', action='store_true', default=None,
        help='use Opus codec for audio\n'
             'default unless -vp8 or -vorbis are also given')
    parser.add_argument(
        '-vorbis', action='store_false', dest='opus', default=None,
        help='use Vorbis codec for audio\n')
    parser.add_argument(
        '-ab', metavar='bitrate', type=float,
        help='Opus audio bitrate in kbits (default: 64)\n'
             'you cannot use -ab with -vorbis')
    parser.add_argument(
        '-aq', metavar='quality', type=int,
        help='Vorbis audio quality, -1..10 (default: 0)\n'
             'you cannot use -aq with -opus')
    parser.add_argument(
        '-aa', metavar='audiofile',
        help='add (use) external audio file\n'
             'if specified, its first audio stream will be muxed into\n'
             'resulting file unless -as is also given')
    parser.add_argument(
        '-as', metavar='audiostream',
        help='audio stream number to use (default: best)\n'
             "that's absolute value obtainable with ffmpeg -i infile")
    parser.add_argument(
        '-af', metavar='audiofilters',
        help='audio filters to use')
    parser.add_argument(
        '-sa', metavar='subfile', const=True, nargs='?',
        help='add (burn) subtitles to the video\n'
             'will use subtitles from the given file or from the input\n'
             'video if filename is omitted')
    parser.add_argument(
        '-si', metavar='subindex', type=int,
        help='subtitle index to use (default: best)\n'
             "note: it's not the global stream number, but the index of\n"
             'subtitle stream across other subtitles')
    parser.add_argument(
        '-sd', metavar='subdelay', type=float,
        help='delay subtitles by this number of seconds\n'
             'note that subtitles delay in mpv is negated, i.e.\n'
             '--sub-delay=1 in mpv actually shift subtitles backward;\n'
             'you should pass -1 to this option to shift backward')
    parser.add_argument(
        '-sf', metavar='subforcestyle',
        help='override default style of the subtitles')
    parser.add_argument(
        '-p', action='store_true',
        help='run player (mpv) in interactive mode to cut and crop video\n'
             'you cannot use -p with -ss, -t, -to')
    parser.add_argument(
        '-po', metavar='mpvopts',
        help='additional raw player (mpv) options\n'
             "example: -po='--mute' (equal sign is mandatory)")
    parser.add_argument(
        '-cover', metavar='loopopts', const=True, nargs='?',
        help='enable album cover mode, encode song with album art\n'
             'first input should be image, -aa must be provided\n'
             "by default '-r 1 -loop 1' is used to loop the art\n"
             'you cannot use -cover with -sa, -p')
    parser.add_argument(
        '-mt', metavar='metatitle', const=True, nargs='?',
        help='set title of output file (default: title of input video)\n'
             'will use output filename without extension if argument\n'
             'is omitted')
    parser.add_argument(
        '-mc', action='store_true',
        help='add creation time to the output file')
    parser.add_argument(
        '-mn', action='store_true',
        help='strip metadata from the output file\n'
             'you cannot use -mn with -mt, -mc')
    parser.add_argument(
        '-fo', metavar='ffmpegopts',
        help='additional raw FFmpeg options\n'
             "example: -fo='-aspect 16:9' (equal sign is mandatory)")
    parser.add_argument(
        '-foi', metavar='ffmpegopts',
        help='raw FFmpeg options to insert before first input\n'
             "example: -foi='-loop 1' (equal sign is mandatory)")
    parser.add_argument(
        '-foi2', metavar='ffmpegopts',
        help='raw FFmpeg options to insert after first input\n'
             "example: -foi2='-itsoffset 10' (equal sign is mandatory)")
    parser.add_argument(
        '-cn', action='store_true',
        help='skip any dependency/version checkings\n'
             'advanced option, use at your own risk')

    # Additional input options validation.
    # NOTE: We ensure only minimal checkings here to not restrict the
    # possible weird uses. E.g. ow, oh, si can be zero or negative; vs,
    # as can be arbitrary.
    options = parser.parse_args(ARGS)
    if options.t is not None and options.to is not None:
        parser.error('-t and -to are mutually exclusive')
    if options.vb is None:
        if options.l is None:
            options.l = 8
        elif options.l <= 0:
            parser.error('bad limit value')
    else:
        if options.l is not None:
            parser.error('-l and -vb are mutually exclusive')
        if options.vb < 0:
            parser.error('invalid video bitrate')
    if options.crf is not None and not 0 <= options.crf <= 63:
        parser.error('video quality level must be in 0..63 range')
    if options.qmin is not None and not 0 <= options.qmin <= 63:
        parser.error('video quality level must be in 0..63 range')
    if options.qmax is not None and not 0 <= options.qmax <= 63:
        parser.error('video quality level must be in 0..63 range')
    if options.qmin is not None and options.qmax is not None:
        if options.qmin > options.qmax:
            parser.error('minimum quality level greater than maximum level')
    if (options.crf is not None and
            (options.qmin is not None or options.qmax is not None)):
        qmin = 0 if options.qmin is None else options.qmin
        qmax = 63 if options.qmax is None else options.qmax
        if not qmin <= options.crf <= qmax:
            parser.error('qmin <= crf <= qmax relation violated')
    if options.opus is None:
        options.opus = not options.vp8
    if options.an:
        if (options.ab is not None or
                options.aq is not None or
                options.aa is not None or
                getattr(options, 'as') is not None or
                options.af is not None):
            parser.error('you cannot use -an with -ab, -aq, -aa, -as, -af')
        # No audio, i.e. its bitrate is zero.
        options.ab = 0
    else:
        if options.opus:
            if options.aq is not None:
                parser.error('you cannot use -aq with -opus')
            if options.ab is None:
                options.ab = 64
            elif options.ab < 1:
                parser.error('invalid audio bitrate')
        else:
            if options.ab is not None:
                parser.error('you cannot use -ab with -vorbis')
            if options.aq is None:
                options.aq = 0
            elif not -1 <= options.aq <= 10:
                parser.error('vorbis quality level must be in -1..10 range')
            # We need this to calculate the target video bitrate.
            # It's not used to encode the audio track.
            options.ab = _vorbisq2bitrate(options.aq)
    if options.sa is None:
        if options.si is not None or options.sd is not None:
            parser.error('you have not specified -sa')
    if options.p:
        if (options.ss is not None or
                options.t is not None or
                options.to is not None):
            parser.error('you cannot use -p with -ss, -t, -to')
    if options.cover is not None:
        if options.aa is None:
            parser.error('audio file must be provided for cover mode')
        # TODO: Probably we should also restrict most other options.
        if options.sa is not None or options.p:
            parser.error('you cannot use -cover with -sa, -p')
    if options.mn:
        if options.mt is not None or options.mc:
            parser.error('you cannot use -mn with -mt, -mc')
    infile = _get_main_infile(options)
    if options.outfile is None:
        if infile[-5:] == '.webm':
            # Don't overwrite input file.
            # NOTE: Input file can be in other directory or -ss/-t/-to
            # is specified so default output name will be different but
            # for now we don't bother checking this.
            parser.error('specify output file please')
    elif _is_same_paths(infile, options.outfile):
        parser.error('specify another output file please')
    return options


def _parse_time(time):
    if isinstance(time, _NUM_TYPES):
        return time
    if time == 'N/A':
        return sys.maxsize
    # [hh]:[mm]:[ss[.xxx]]
    m = re.match(r'(?:(\d+):)?(?:(\d+)+:)?(\d+(?:\.\d+)?)$', time)
    if not m:
        raise Exception('invalid time {}'.format(time))
    hours, minutes, seconds = m.groups()
    duration = float(seconds)
    if hours is not None:
        if minutes is None:
            # 1:2 -> (1, None, 2)
            duration += int(hours) * 60
        else:
            # 1:2:3 -> (1, 2, 3)
            duration += int(minutes) * 60
            duration += int(hours) * 3600
    return duration


def _timestamp(duration):
    idur = int(duration)
    ts = '{:02d}:{:02d}:{:02d}'.format(idur//3600, idur%3600//60, idur%60)
    frac = duration % 1
    if frac >= 0.1:
        ts += _TEXT_TYPE(frac)[1:3]
    return ts


def _doc2help(doc):
    doc = doc.strip()
    lines = doc.split('\n')
    lines = [line.strip() for line in lines]
    return '\n'.join(lines)


def _split_lua_params(s, delim=':'):
    """
    Deserialize colon-separated values passed from Lua.
    Based on <http://stackoverflow.com/a/18092547>.
    """
    # TODO: Move to JSON intechanging format with mpv 0.9+. See this
    # commit: <https://github.com/mpv-player/mpv/commit/daabbe3>.
    if not s:
        return
    itr = iter(s)
    param = ''
    for ch in itr:
        if ch == '\\':
            try:
                ch2 = next(itr)
            except StopIteration:
                raise Exception('badly escaped string')
            else:
                if ch2 == 'n':
                    param += '\n'
                else:
                    param += ch2
        elif ch == delim:
            yield param
            param = ''
        else:
            param += ch
    yield param


def _pos_int_check(s):
    return re.match(r'-?\d+$', s) is not None


def _diff_dicts(defaults, d2):
    diff = {}
    for k, v in d2.items():
        try:
            if defaults[k] != v:
                diff[k] = v
        except KeyError:
            diff[k] = v
    return diff


def run_interactive_mode(options):
    """
    Press "c" first time to mark the start of the fragment.
    Press it again to mark the end of the fragment.
    Press "KP1" after "c" to define the fragment from
    the start to the marked time.
    Press "KP3" after "c" to define the fragment from
    the marked time to the end of the video.

    Select crop area with the mouse and adijust it precisely with
    KP4/KP8/KP6/KP2 (move crop area left/up/right/down) and
    KP7/KP9/-/+ (decrease/increase width/height).
    Press "a" when you finished with crop.
    Also you can press KP5 to init crop area at the center of video.

    Press "i" to dump info about currently selected video/audio/sub
    tracks and subtitles delay from mpv.
    Caution: it may redefine your appropriate passed options.

    Once you defined cut fragment and/or crop are, close the
    player and let the script do all hard work for calculating
    the bitrate and encoding.
    """
    # NOTE: mpv ignores Lua scripts without suffix.
    luafh, luafile = tempfile.mkstemp(suffix='.lua')
    try:
        options.luafile = luafile
        os.write(luafh, MPV_SCRIPT)
    finally:
        os.close(luafh)

    args = ['--msg-level', 'all=error', '--script', luafile]
    if options.po is not None:
        args += shlex.split(options.po)
    args += [options.infile]
    print('Running interactive mode.\n', file=sys.stderr)
    print("Note: if you keyboard doesn't have keypad keys and you still want\n"
          "to use appropriate actions (they're not mandatory to define the\n"
          'cut or crop area), pass "--help-imode" flag to program to see how.'
          '\n', file=sys.stderr)
    print(_doc2help(run_interactive_mode.__doc__), file=sys.stderr)

    # We let the user to see stderr output and catch stdout by ourself.
    out = _mpv_output(args, debug=True, catch_stdout=False)['stderr']
    cut = None
    crop = None
    # Using the falseness of empty dict to simplify the code.
    info = {}
    for line in reversed(out.split('\n')):
        if not cut:
            cutm = re.match(
                r'cut=(-1|\d+(?:\.\d+)?):(-1|\d+(?:\.\d+)?)$',
                line)
            if cutm:
                cut = [round(float(v), 3) for v in cutm.groups()]
                if crop and info:
                    break
                continue
        if not crop:
            cropm = re.match(r'(crop=(\d+):(\d+):(\d+):(\d+))$', line)
            if cropm:
                crop = cropm.groups()
                if cut and info:
                    break
                continue
        if not info and line.startswith('info='):
            params = list(_split_lua_params(line[5:]))
            if len(params) != 6:
                continue
            vs, as_, audio_file, si, sub_file, sub_delay = params
            if not all(_pos_int_check(s) for s in [vs, as_, si]):
                continue
            if not re.match(r'-?\d+(\.\d+)?$', sub_delay):
                continue
            vs, as_, si = int(vs), int(as_), int(si)
            sub_delay = float(sub_delay)
            info = _diff_dicts({
                'as': -1, 'aa': '',
                'si': -1, 'sa': '', 'sd': 0,
            }, {
                'vs': vs,
                'as': as_, 'aa': audio_file,
                'si': si, 'sa': sub_file, 'sd': sub_delay,
            })
            if info and cut and crop:
                break

    # NOTE: We don't mind checking cut ranges and crop values because:
    # 1) It should be already checked in Lua script
    # 2) We will check some of them anyway in ``_get_input_info``
    print('='*50, file=sys.stderr)
    if cut:
        # ``-1`` is a special value and defines start/end of the file.
        shift = '0' if cut[0] < 0 else _timestamp(cut[0])
        endpos = 'EOF' if cut[1] < 0 else _timestamp(cut[1])
        print('[CUT] {} - {} ({} - {})'.format(shift, endpos, cut[0], cut[1]),
              file=sys.stderr)
    if crop:
        print('[CROP] x1={}, y1={}, width={}, height={}'.format(
                crop[3], crop[4], crop[1], crop[2]),
              file=sys.stderr)
    if info:
        changes = ', '.join('{}={}'.format(k, v) for k, v in info.items())
        print('[DUMP] {}'.format(changes), file=sys.stderr)

    if cut or crop or info:
        try:
            ok = _input('Continue with that settings? Y/n ')
        except EOFError:
            sys.exit(1)
        if ok == '' or ok.lower() == 'y':
            if cut:
                if cut[0] >= 0:
                    options.ss = cut[0]
                if cut[1] >= 0:
                    options.to = cut[1]
            if crop:
                options.vfi = crop[0] if options.vfi is None \
                    else '{},{}'.format(options.vfi, crop[0])
            if 'si' in info and 'sa' not in info:
                info['sa'] = True
            options.__dict__.update(info)
        else:
            sys.exit(1)
    else:
        print("You haven't defined cut/crop or dumped info.", file=sys.stderr)
        try:
            ok = _input('Encode input video intact? y/N ')
        except EOFError:
            sys.exit(1)
        if ok == '' or ok.lower() != 'y':
            sys.exit(1)


def print_interactive_help():
    """
    You can redefine hotkeys by placing this to your input.conf and
    changing the key (first column):

    # This is the defaults:
    c   script_binding webm_cut
    KP1 script_binding webm_cut_from_start
    KP3 script_binding webm_cut_to_end
    a   script_binding webm_crop
    KP5 script_binding webm_crop_init
    KP7 script_binding webm_crop_w_dec
    KP9 script_binding webm_crop_w_inc
    -   script_binding webm_crop_h_dec
    +   script_binding webm_crop_h_inc
    KP4 script_binding webm_crop_x_dec
    KP6 script_binding webm_crop_x_inc
    KP8 script_binding webm_crop_y_dec
    KP2 script_binding webm_crop_y_inc
    i   script_binding webm_dump_info

    You also can change some default options by creating webm.conf in your
    lua-settings directory (see <http://mpv.io/manual/stable/#configuration>):

    # This is the defaults:
    crop_alpha=180  # Transparency of crop area
    crop_x_step=2   # Precision of crop area adjusting from the keyboard
    crop_y_step=2   # Precision of crop area adjusting from the keyboard
    """
    doc = '{}\n\n{}'.format(
        _doc2help(run_interactive_mode.__doc__),
        _doc2help(print_interactive_help.__doc__))
    print(doc, file=sys.stderr)


def _get_input_info(options):
    infile = _get_main_infile(options)
    # NOTE: Better to use ffprobe(1) configurable output like suggested
    # here: <http://stackoverflow.com/a/22243834>, but it brings its own
    # disadvantage: we must be sure target system has `ffprobe`
    # executable too.
    out = _ffmpeg_output(
        ['-hide_banner', '-i', infile],
        check_code=False)['stderr']
    try:
        dur = re.search(r'^\s+Duration: ([^,]+)', out, re.MULTILINE).group(1)
    except Exception:
        raise Exception('failed to parse duration of input file')
    else:
        induration = _parse_time(dur)

    # Validate ranges.
    shift = 0
    if options.ss is not None:
        shift = _parse_time(options.ss)
        if shift > induration:
            raise Exception(
                'Too far input seek {} '
                '(input has only {} duration)'.format(options.ss, dur))
    if options.t is not None:
        outduration = _parse_time(options.t)
        if outduration == 0:
            raise Exception('duration must not be zero')
        if shift + outduration > induration:
            raise Exception('end position too far in the future')
    elif options.to is not None:
        endpos = _parse_time(options.to)
        outduration = endpos - shift
        if endpos > induration:
            raise Exception(
                'End position {} too far in the future '
                '(input has only {} duration)'.format(options.to, dur))
        if endpos <= shift:
            raise Exception(
                'End position is less or equal than the input seek')
    else:
        outduration = induration - shift

    # Metadata.
    intitle = ''
    title = re.search(
        r'^\s*title\s*:\s*(.+)$', out,
        re.MULTILINE|re.IGNORECASE)
    if title:
        intitle = title.group(1)
    album = re.search(
        r'^\s*album\s*:\s*(.+)$', out,
        re.MULTILINE|re.IGNORECASE)
    if album and intitle:
        intitle = '{} - {}'.format(album.group(1), intitle)

    return {
        'induration': induration,
        'outduration': outduration,
        'intitle': intitle,
    }


def _get_output_filename(options):
    infile = _get_main_infile(options)
    name = os.path.basename(infile)
    name = os.path.splitext(name)[0]
    if (options.ss is not None or
            options.t is not None or
            options.to is not None):
        name += '_'
        shift = 0 if options.ss is None else _parse_time(options.ss)
        name += _timestamp(shift)
        name += '-'
        if options.t:
            endpos = shift + _parse_time(options.t)
        elif options.to:
            endpos = _parse_time(options.to)
        else:
            endpos = options.induration
        name += _timestamp(endpos)
    name += '.webm'
    return name


def _calc_video_bitrate(options):
    """
    Calculate video bitrate in kilobits.
    """
    limit_kbits = options.l * 8 * 1024
    vb = limit_kbits / options.outduration - options.ab
    vb = int(vb * 10) / 10
    if vb < 0.1:
        raise Exception(
            '\n\nUnable to calculate video bitrate for the given limit.\n'
            'Either limit is too low, duration of the video is too long\n'
            'or audio bitrate is too high.\n'
            'Consider fixing one of this or just set bitrate manually.')
    return vb


def _escape_ffarg(arg):
    """
    Escape FFmpeg filter argument (see ffmpeg-filters(1), "Notes on
    filtergraph escaping"). Escaping rules are rather mad.

    Known issues: names like :.ass, 1:.ass still don't work. Seems like
    a bug in FFmpeg because _:.ass works ok.
    """
    arg = arg.replace('\\', r'\\')      # \ -> \\
    arg = arg.replace("'",  r"'\\\''")  # ' -> '\\\''
    arg = arg.replace(':',  r'\:')      # : -> \:
    return "'{}'".format(arg)


def _encode(options, firstpass):
    passn = '1' if firstpass else '2'
    logfile = options.logfile[:-6]
    speed = '4' if firstpass else '1'
    vb = '{}k'.format(options.vb) if options.vb else '0'
    outfile = os.devnull if firstpass else options.outfile

    # Input.
    args = ['-hide_banner']
    if options.ss is not None:
        args += ['-ss', _TEXT_TYPE(options.ss)]
    if options.cover is not None:
        if options.cover is True:
            args += ['-r', '1', '-loop', '1']
        else:
            args += shlex.split(options.cover)
    if options.foi is not None:
        args += shlex.split(options.foi)
    args += ['-i', options.infile]
    if options.foi2 is not None:
        args += shlex.split(options.foi2)
    if options.aa is not None:
        args += ['-i', options.aa]
    if (options.t is not None or
            options.to is not None or
            options.cover is not None):
        args += ['-t', _TEXT_TYPE(round(options.outduration, 3))]

    # Streams.
    if (options.vs is not None or
            getattr(options, 'as') is not None or
            options.aa is not None):
        vstream = 'v:0' if options.vs is None else _TEXT_TYPE(options.vs)
        if not vstream.startswith('['):
            vstream = '0:{}'.format(vstream)
        args += ['-map', vstream]
        ainput = 0 if options.aa is None else 1
        astream = getattr(options, 'as')
        astream = 'a:0' if astream is None else _TEXT_TYPE(astream)
        if not astream.startswith('['):
            astream = '{}:{}'.format(ainput, astream)
        args += ['-map', astream]

    # Misc.
    args += ['-pass', passn, '-passlogfile', logfile, '-sn']
    if options.verbose:
        args += ['-loglevel', 'verbose']

    # Video.
    if options.vp8:
        # VP8 is fast enough to use -speed=0 for both passes.
        # TODO: Slices?
        args += ['-c:v', 'libvpx', '-speed', '0']
    else:
        # tile-columns=6 by default but won't harm. See also:
        # <http://permalink.gmane.org/gmane.comp.multimedia.webm.devel/2339>.
        # frame-parallel should be disabled, see:
        # <http://permalink.gmane.org/gmane.comp.multimedia.webm.devel/2359>.
        args += [
            '-c:v', 'libvpx-vp9', '-speed', speed,
            '-tile-columns', '6', '-frame-parallel', '0',
        ]
    args += [
        '-b:v', vb, '-threads', _TEXT_TYPE(options.threads),
        # Enabled for VP9 by default but always force it just in case.
        # TODO: enable_auto_alt_ref might be set to 2 actually:
        # < jimbankoski> auto-alt-ref=2 allows vpx to use multiple alt refs
        # < jimbankoski> and I think actually turns it on by default
        # But ffmpeg's option is boolean and doesn't allow this.
        '-auto-alt-ref', '1', '-lag-in-frames', '25',
        # Default to 128 for both VP8 and VP9 but bigger keyframe interval
        # saves bitrate a bit.
        '-g', '9999',
        # Using other subsamplings require profile>0 which support
        # across various decoders is still poor. User can still redefine
        # this via ``-fo``.
        '-pix_fmt', 'yuv420p',
    ]
    if options.crf is not None:
        args += ['-crf', _TEXT_TYPE(options.crf)]
    if options.qmin is not None:
        args += ['-qmin', _TEXT_TYPE(options.qmin)]
    if options.qmax is not None:
        args += ['-qmax', _TEXT_TYPE(options.qmax)]

    # Video filters.
    vfilters = []
    if options.vfi is not None:
        vfilters += [options.vfi]
    if options.vw is not None or options.vh is not None:
        scale='scale='
        scale += '-1' if options.vw is None else _TEXT_TYPE(options.vw)
        scale += ':'
        scale += '-1' if options.vh is None else _TEXT_TYPE(options.vh)
        vfilters += [scale]
    if options.sa is not None:
        sub_delay = 0
        if options.ss is not None:
            sub_delay += _parse_time(options.ss)
        if options.sd is not None:
            sub_delay += options.sd
        if sub_delay:
            vfilters += ['setpts=PTS+{}/TB'.format(round(sub_delay, 3))]
        subtitles = 'subtitles='
        sub_file = options.infile if options.sa is True else options.sa
        subtitles += _escape_ffarg(sub_file)
        if options.si is not None:
            subtitles += ':si={}'.format(options.si)
        if options.sf is not None:
            subtitles += ':force_style={}'.format(_escape_ffarg(options.sf))
        vfilters += [subtitles]
        if sub_delay:
            vfilters += ['setpts=PTS-STARTPTS']
    if options.vf is not None:
        vfilters += [options.vf]
    if vfilters:
        args += ['-vf', ','.join(vfilters)]

    # Audio.
    if firstpass or options.an:
        args += ['-an']
    else:
        args += ['-ac', '2']
        if options.opus:
            args += ['-c:a', 'libopus', '-b:a', '{}k'.format(options.ab)]
        else:
            args += ['-c:a', 'libvorbis', '-q:a', _TEXT_TYPE(options.aq)]
        if options.af is not None:
            args += ['-af', options.af]

    # Metadata.
    if not firstpass:
        if options.mn:
            args += ['-map_metadata', '-1']
        else:
            if options.mt is not None:
                title = options.mt
                if title is True:
                    title = os.path.basename(options.outfile)
                    title = os.path.splitext(title)[0]
                args += ['-metadata', 'title={}'.format(title)]
            elif options.cover is not None and options.intitle:
                args += ['-metadata', 'title={}'.format(options.intitle)]
            if options.mc:
                ctime = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
                args += ['-metadata', 'creation_time={}'.format(ctime)]

    # Raw options.
    if options.fo is not None:
        args += shlex.split(options.fo)

    # Output.
    args += ['-f', 'webm', '-y', outfile]

    _ffmpeg(args, debug=True)


def encode(options):
    import multiprocessing
    options.__dict__.update(_get_input_info(options))
    if options.outfile is None:
        options.outfile = _get_output_filename(options)
    if options.vb is None:
        options.vb = _calc_video_bitrate(options)
    options.threads = multiprocessing.cpu_count()
    # NOTE: Py3 always returns unicode for the second parameter, Py2
    # returns bytes with bytes suffix/without suffix and unicode with
    # unicode suffix. Since we use unicode_literals and provide suffix,
    # it should always be unicode.
    logfh, options.logfile = tempfile.mkstemp(suffix='-0.log')
    os.close(logfh)
    # NOTE: 2-pass encoding in cover mode might be faster than 1-pass.
    # Though we may add option to use only single pass in future.
    _encode(options, firstpass=True)
    _encode(options, firstpass=False)


def print_stats(options, start):
    print('='*50, file=sys.stderr)
    filename = os.path.basename(options.outfile)
    print("Output filename: {}".format(filename), file=sys.stderr)
    filepath = os.path.abspath(options.outfile)
    filepath = filepath.replace('\\', r'\\').replace("'", r"'\''")
    print("Output filepath: '{}'".format(filepath), file=sys.stderr)
    print('Output duration: {}'.format(_timestamp(options.outduration)),
          file=sys.stderr)
    print('Output video bitrate: {}k'.format(options.vb), file=sys.stderr)
    print('Output audio bitrate: {}k'.format(options.ab), file=sys.stderr)
    size = os.path.getsize(options.outfile)
    sizeinfo = 'Output file size: {} B'.format(size)
    if size >= 1024:
        sizeinfo += ', {:.2f} KiB'.format(size/1024)
    if size >= 1024 * 1024:
        sizeinfo += ', {:.2f} MiB'.format(size/1024/1024)
    if options.l is not None:
        limit = int(options.l * 1024 * 1024)
        if size > limit:
            sizeinfo += ', OVERWEIGHT: {} B'.format(size - limit)
        elif size < limit:
            sizeinfo += ', underweight: {} B'.format(limit - size)
    print(sizeinfo, file=sys.stderr)
    runtime = _timestamp(time.time() - start)
    print('Overall time spent: {}'.format(runtime), file=sys.stderr)


def _is_verbose(options):
    default = '-v' in ARGS
    return getattr(options, 'verbose', default)


def cleanup(options):
    try:
        if hasattr(options, 'logfile'):
            os.remove(options.logfile)
        if hasattr(options, 'luafile'):
            os.remove(options.luafile)
    except Exception as exc:
        if _is_verbose(options):
            exc = '\n\n' + traceback.format_exc()[:-1]
        print('Error during cleanup: {}'.format(exc), file=sys.stderr)


def main():
    verinfo = {'pythonv': '?', 'ffmpegv': '?', 'mpvv': '?'}
    options = None
    try:
        if '-cn' not in ARGS:
            verinfo = check_dependencies()
        if '-hi' in ARGS or '--help-imode' in ARGS:
            print_interactive_help()
            sys.exit()
        options = process_options(verinfo)
        if options.p:
            run_interactive_mode(options)
        start = time.time()
        encode(options)
        print_stats(options, start)
    except Exception as exc:
        if _is_verbose(options):
            exc = '\n\n' + traceback.format_exc()[:-1]
        err = 'Cannot proceed due to the following error: {}'.format(exc)
        sys.exit(err)
    finally:
        cleanup(options)


MPV_SCRIPT = br"""
require "mp.options"
local assdraw = require "mp.assdraw"

local options = {
    crop_alpha = 180,
    crop_x_step = 2,
    crop_y_step = 2,
}
read_options(options, "webm")
local crop_alpha = options.crop_alpha
local crop_x_step = options.crop_x_step
local crop_y_step = options.crop_y_step

local cut_pos = nil
local crop_active = false
local crop_resizing = false
local crop_moving = false
local width, height = 0, 0
-- x2 can be less than x1, y2 can be less than y1.
local crop_x1, crop_y1, crop_x2, crop_y2 = 0, 0, 0, 0
local move_base_x, move_base_y = 0, 0
local move_start_x1, move_start_y1 = 0, 0

function log2user(str)
    io.stdout:write(str .. "\n")
    io.stdout:flush()
    mp.osd_message(str, 2)
end

function log2webm(str)
    io.stderr:write(str .. "\n")
    io.stderr:flush()
end

function timestamp(duration)
    -- We can just use `get_property_osd` instead of this but it would
    -- require to store another value between the function calls.
    local hours = duration / 3600
    local minutes = duration % 3600 / 60
    local seconds = duration % 60
    local ts = string.format("%02d:%02d:%02d", hours, minutes, seconds)
    local frac = duration % 1
    if frac >= 0.1 then
        ts = ts .. string.sub(frac, 2, 3)
    end
    return ts
end

function cut()
    local pos = mp.get_property_number("time-pos")
    if cut_pos ~= nil then
        local shift, endpos = cut_pos, pos
        if shift > endpos then
            shift, endpos = endpos, shift
        end
        if shift == endpos then
            log2user("Cut fragment is empty")
        else
            log2webm(string.format("cut=%f:%f", shift, endpos))
            log2user(string.format(
                "Cut fragment: %s - %s",
                timestamp(shift), timestamp(endpos)))
            mp.commandv("osd-bar", "show_progress")
        end
        cut_pos = nil
    else
        cut_pos = pos
        log2user(string.format("Marked %s as start position", timestamp(pos)))
    end
end

function cut_from_start()
    -- NOTE: 0 is truly value in Lua...
    if cut_pos ~= nil then
        if cut_pos == 0 then
            log2user("Cut fragment is empty")
        else
            log2webm(string.format("cut=-1:%f", cut_pos))
            log2user(string.format(
                "Cut fragment: 0 - %s",
                timestamp(cut_pos)))
            mp.commandv("osd-bar", "show_progress")
        end
        cut_pos = nil
    else
        log2user("End position was't marked")
    end
end

function cut_to_end()
    if cut_pos ~= nil then
        local endpos = mp.get_property_number("length")
        if cut_pos == endpos then
            log2user("Cut fragment is empty")
        else
            log2webm(string.format("cut=%f:-1", cut_pos))
            log2user(string.format(
                "Cut fragment: %s - EOF",
                timestamp(cut_pos)))
            mp.commandv("osd-bar", "show_progress")
        end
        cut_pos = nil
    else
        log2user("Start position was't marked")
    end
end

function render_crop_rect()
    ass = assdraw.ass_new()
    ass:draw_start()
    ass:append(string.format("{\\1a&H%X&}", crop_alpha))
    -- NOTE: This function doesn't mind if x1 > x2.
    ass:rect_cw(crop_x1, crop_y1, crop_x2, crop_y2)
    ass:pos(0, 0)
    ass:draw_stop()
    mp.set_osd_ass(width, height, ass.text)
end

function clear_scr()
    mp.set_osd_ass(width, height, "")
end

function crop_init()
    crop_active = true
    width, height = mp.get_osd_size()
end

function crop_init_at_center()
    if crop_active then
        log2user("Crop is already active")
    else
        crop_init()
        crop_x1 = width * 1/4
        crop_x2 = width * 3/4
        crop_y1 = height * 1/4
        crop_y2 = height * 3/4
        render_crop_rect()
    end
end

function crop_drag_start()
    local x, y = mp.get_mouse_pos()
    if crop_active and
            math.min(crop_x1, crop_x2) <= x and
            math.min(crop_y1, crop_y2) <= y and
            x <= math.max(crop_x1, crop_x2) and
            y <= math.max(crop_y1, crop_y2) then
        crop_moving = true
        move_base_x, move_base_y = x, y
        move_start_x1, move_start_y1 = crop_x1, crop_y1
    else
        crop_init()
        crop_resizing = true
        crop_x1, crop_y1 = x, y
        crop_x2, crop_y2 = x, y
        clear_scr()
    end
end

function crop_drag_end()
    crop_resizing = false
    crop_moving = false
end

function ensure_ranges()
    local cropw = math.abs(crop_x2 - crop_x1)
    if crop_x1 < crop_x2 then
        if crop_x1 < 0 then
            crop_x1 = 0
            crop_x2 = cropw
        elseif crop_x2 > width then
            crop_x1 = width - cropw
            crop_x2 = width
        end
    else
        if crop_x2 < 0 then
            crop_x2 = 0
            crop_x1 = cropw
        elseif crop_x1 > width then
            crop_x2 = width - cropw
            crop_x1 = width
        end
    end
    local croph = math.abs(crop_y2 - crop_y1)
    if crop_y1 < crop_y2 then
        if crop_y1 < 0 then
            crop_y1 = 0
            crop_y2 = croph
        elseif crop_y2 > height then
            crop_y1 = height - croph
            crop_y2 = height
        end
    else
        if crop_y2 < 0 then
            crop_y2 = 0
            crop_y1 = croph
        elseif crop_y1 > height then
            crop_y2 = height - croph
            crop_y1 = height
        end
    end
end

function crop_drag()
    if crop_resizing then
        crop_x2, crop_y2 = mp.get_mouse_pos()
        if crop_x2 < 0 then crop_x2 = 0 end
        if crop_x2 > width then crop_x2 = width end
        if crop_y2 < 0 then crop_y2 = 0 end
        if crop_y2 > height then crop_y2 = height end
        render_crop_rect()
    elseif crop_moving then
        local x, y = mp.get_mouse_pos()
        local delta_x, delta_y = x - move_base_x, y - move_base_y
        local crop_w, crop_h = crop_x2 - crop_x1, crop_y2 - crop_y1
        crop_x1 = move_start_x1 + delta_x
        crop_x2 = crop_x1 + crop_w
        crop_y1 = move_start_y1 + delta_y
        crop_y2 = crop_y1 + crop_h
        ensure_ranges()
        render_crop_rect()
    end
end

function crop()
    if not crop_active then
        log2user("Crop region is empty")
        return
    end
    local crop_x = math.min(crop_x1, crop_x2)
    local crop_y = math.min(crop_y1, crop_y2)
    local crop_w = math.abs(crop_x2 - crop_x1)
    local crop_h = math.abs(crop_y2 - crop_y1)
    if crop_w == 0 or crop_h == 0 then
        log2user("Crop region is empty")
    else
        log2webm(string.format(
            "crop=%d:%d:%d:%d",
            crop_w, crop_h, crop_x, crop_y))
        log2user(string.format(
            "Defined crop area as x1=%d, y1=%d, width=%d, height=%d",
            crop_x, crop_y, crop_w, crop_h))
    end
    clear_scr()
    crop_active = false
end

function crop_width_dec()
    if crop_active then
        crop_x2 = crop_x2 - crop_x_step
        if crop_x2 < 0 then crop_x2 = 0 end
        render_crop_rect()
    end
end

function crop_width_inc()
    if crop_active then
        crop_x2 = crop_x2 + crop_x_step
        if crop_x2 > width then crop_x2 = width end
        render_crop_rect()
    end
end

function crop_height_dec()
    if crop_active then
        crop_y2 = crop_y2 - crop_y_step
        if crop_y2 < 0 then crop_y2 = 0 end
        render_crop_rect()
    end
end

function crop_height_inc()
    if crop_active then
        crop_y2 = crop_y2 + crop_y_step
        if crop_y2 > height then crop_y2 = height end
        render_crop_rect()
    end
end

function crop_x_dec()
    if crop_active then
        crop_x1 = crop_x1 - crop_x_step
        crop_x2 = crop_x2 - crop_x_step
        ensure_ranges()
        render_crop_rect()
    end
end

function crop_x_inc()
    if crop_active then
        crop_x1 = crop_x1 + crop_x_step
        crop_x2 = crop_x2 + crop_x_step
        ensure_ranges()
        render_crop_rect()
    end
end

function crop_y_dec()
    if crop_active then
        crop_y1 = crop_y1 - crop_y_step
        crop_y2 = crop_y2 - crop_y_step
        ensure_ranges()
        render_crop_rect()
    end
end

function crop_y_inc()
    if crop_active then
        crop_y1 = crop_y1 + crop_y_step
        crop_y2 = crop_y2 + crop_y_step
        ensure_ranges()
        render_crop_rect()
    end
end

function get_track(tracks, typ, id)
    if not id then return end
    for i = 1, #tracks do
        local track = tracks[i]
        if track.type == typ and track.id == id then
            return track
        end
    end
end

function get_sub_index(tracks, strack)
    -- In this function we assume that order of subtitle tracks is the
    -- same for both ffmpeg and mpv. i.e.:
    -- 1) for internal sub: si = sid - 1
    -- 2) for external sub: si = index of selected subtitle in that file
    -- This might be not true though.
    if not strack then return end
    if not strack.external then
        return strack.id - 1
    end
    local stracks = {}
    for i = 1, #tracks do
        local track = tracks[i]
        if track["external-filename"] == strack["external-filename"] and
                track.type == "sub" then
            table.insert(stracks, track)
        end
    end
    table.sort(stracks, function(a, b) return a.id < b.id end)
    for i = 1, #stracks do
        if stracks[i].id == strack.id then
            return i - 1
        end
    end
end

function escape_filename(name)
    if name then
        return name:gsub("\\", "\\\\"):gsub(":", "\\:"):gsub("\n", "\\n")
    else
        return ""
    end
end

function dump_info()
    local tracks = mp.get_property_native("track-list")

    local vid = mp.get_property_number("vid")
    local vtrack = get_track(tracks, "video", vid)
    -- Just in case re-check everything; though if vid is defined,
    -- ff-index should be also available actually.
    if not vtrack or not vtrack["ff-index"] then
        log2webm("Cannot find video track, seems like sound file")
        return
    end
    -- At least this value must be available.
    local vs = vtrack["ff-index"]

    local aid = mp.get_property_number("aid")
    local atrack = get_track(tracks, "audio", aid) or {}
    local as = atrack["ff-index"]
    local audio_file = atrack["external-filename"]

    local sid = mp.get_property_number("sid")
    local strack = get_track(tracks, "sub", sid)
    local si = get_sub_index(tracks, strack)
    local sub_file = strack and strack["external-filename"]
    local sub_delay = mp.get_property_number("sub-delay") or 0
    -- NOTE: This is funny but mplayer's/mpv's value of sub delay is
    -- actually negated.
    sub_delay = -sub_delay
    if math.abs(sub_delay) < 0.01 then sub_delay = 0 end  -- Fix fp inaccuracy

    log2webm(string.format(
        "info=%d:%d:%s:%d:%s:%f",
        vs,
        as or -1,
        escape_filename(audio_file),
        si or -1,
        escape_filename(sub_file),
        sub_delay))

    local changes = {}
    function ins(v) table.insert(changes, v) end
    ins("vs=" .. vs)
    if as             then ins("as=" .. as) end
    if audio_file     then ins("aa=" .. audio_file) end
    if si             then ins("si=" .. si) end
    if sub_file       then ins("sa=" .. sub_file) end
    if sub_delay ~= 0 then ins(string.format("sd=%.2f", sub_delay)) end
    log2user("Dumped " .. table.concat(changes, ", "))
end

mp.add_key_binding("c", "webm_cut", cut)
mp.add_key_binding("KP1", "webm_cut_from_start", cut_from_start)
mp.add_key_binding("KP3", "webm_cut_to_end", cut_to_end)

-- XXX: Don't know how to make `mp.add_key_binding` work with dragging.
mp.set_key_bindings({{"mouse_btn0", crop_drag_end, crop_drag_start}}, "webm")
mp.enable_key_bindings("webm")
mp.add_key_binding("mouse_move", "webm_crop_drag", crop_drag)
mp.add_key_binding("KP5", "webm_crop_init", crop_init_at_center)
mp.add_key_binding("a", "webm_crop", crop)
local rp = {repeatable = true}
mp.add_key_binding("KP7", "webm_crop_w_dec", crop_width_dec, rp)
mp.add_key_binding("KP9", "webm_crop_w_inc", crop_width_inc, rp)
mp.add_key_binding("-", "webm_crop_h_dec", crop_height_dec, rp)
mp.add_key_binding("+", "webm_crop_h_inc", crop_height_inc, rp)
mp.add_key_binding("KP4", "webm_crop_x_dec", crop_x_dec, rp)
mp.add_key_binding("KP6", "webm_crop_x_inc", crop_x_inc, rp)
mp.add_key_binding("KP8", "webm_crop_y_dec", crop_y_dec, rp)
mp.add_key_binding("KP2", "webm_crop_y_inc", crop_y_inc, rp)

mp.add_key_binding("i", "webm_dump_info", dump_info)
"""


if __name__ == '__main__':
    main()
