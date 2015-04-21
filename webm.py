#!/usr/bin/env python

"""
convert videos to webm format using FFmpeg

features:
  - encodes input video to webm container with VP9 and Opus
  - uses two-pass encode with the settings recommended by the developers
  - fits output file to the given size limit
  - allows to select video/audio streams and external audio track
  - can burn subtitles into the video
  - flexible set of options and ability to pass raw flags to FFmpeg
  - interactive mode to cut/crop input video with mpv

dependencies:
  - Python 2.7+ or 3.2+ (using: {pythonv})
  - FFmpeg 2+ compiled with libvpx and libopus (using: {ffmpegv})
  - mpv 0.8+ compiled with Lua support, optional (using: {mpvv})

encoding modes:
  - by default bitrate calculated to fit the output video to limit
  - you may specify custom bitrate to use
  - -crf option enables constrained quality mode
  - -crf and -vb 0 enable constant quality mode

examples:
  (use `{stitle}' instead of `python {title}' if you installed it from pip)
  - fit video to default limit: python {title} -i in.mkv
  - fit video to 6 MiB:         python {title} -i in.mkv -l 6
  - set video bitrate to 600k:  python {title} -i in.mkv -vb 600
  - constrained quality:        python {title} -i in.mkv -crf 20
  - CQ with custom limit:       python {title} -i in.mkv -crf 20 -l 6
  - CQ with custom bitrate:     python {title} -i in.mkv -crf 20 -vb 600
  - constant quality:           python {title} -i in.mkv -crf 20 -vb 0

use custom location of FFmpeg executable:
  - *nix:    FFMPEG=/opt/ffmpeg/ffmpeg python {title} -i in.mkv
  - Windows: set FFMPEG=C:\\ffmpeg.exe & python {title} -i in.mkv
"""

# TODO:
#     * Shift audio/subtitles by given amount of time
#     * Fit audio to limit
#     * Optionally use mkvmerge for muxing
#     * Best quality mode

# Since there is no way to wrap future imports in try/except, we use
# hack with comment. See <http://stackoverflow.com/q/388069> for
# details.
from __future__ import absolute_import  # Install Python 2.7+ or 3.2+
from __future__ import division  # Install Python 2.7+ or 3.2+
from __future__ import print_function  # Install Python 2.7+ or 3.2+
from __future__ import unicode_literals  # Install Python 2.7+ or 3.2+

import os
import re
import sys
import math
import time
import locale
import tempfile
import traceback
import subprocess


__title__ = 'webm.py'
__stitle__ = 'webm'
__version__ = '0.3.2'
__license__ = 'CC0'


_PY2 = sys.version_info[0] == 2
_TEXT_TYPE = unicode if _PY2 else str
_NUM_TYPES = (int, long, float) if _PY2 else (int, float)


# We can't use e.g. ``sys.stdout.encoding`` because user can redirect
# the output so in Python2 it would return ``None``. Seems like
# ``getpreferredencoding`` is the best remaining method.
OS_ENCODING = locale.getpreferredencoding() or 'utf-8'


FFMPEG_PATH = os.getenv('FFMPEG', 'ffmpeg')
# XXX: This probably may fail on non UTF-8 locales.
# Python 3 uses ``getfilesystemencoding`` to decode environment
# variables: <https://docs.python.org/3/library/os.html#os.getenv>.
if _PY2: FFMPEG_PATH = FFMPEG_PATH.decode(OS_ENCODING)


MPV_PATH = os.getenv('MPV', 'mpv')
if _PY2: MPV_PATH = MPV_PATH.decode(OS_ENCODING)


# Option ``options.tt`` can take the following values:
# - ``None`` by default
# - ``_FullFakeDuration`` if user skipped the value of -tt
# - value of -tt option
class _FullFakeDuration: pass


def _ffmpeg(args, check_code=True, debug=False):
    args = [FFMPEG_PATH] + args
    if debug:
        print('='*50 + '\n' + ' '.join(args) + '\n' + '='*50, file=sys.stderr)
    try:
        p = subprocess.Popen(args)
    except Exception as exc:
        raise Exception('Failed to run FFmpeg ({})'.format(exc))
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
                stderr=subprocess.PIPE)
    except Exception as exc:
        raise Exception('Failed to run FFmpeg ({})'.format(exc))
    out, err = p.communicate()
    if check_code and p.returncode != 0:
        raise Exception('FFmpeg exited with error')
    out = out.decode(OS_ENCODING)
    err = err.decode(OS_ENCODING)
    return {'stdout': out, 'stderr': err, 'code': p.returncode}


def _mpv_output(args, check_code=True, catch_stdout=True, debug=False):
    args = [MPV_PATH] + args
    if debug:
        print('='*50 + '\n' + ' '.join(args) + '\n' + '='*50, file=sys.stderr)
    kwargs = {'stdout': subprocess.PIPE} if catch_stdout else {}
    try:
        p = subprocess.Popen(args, stderr=subprocess.PIPE, **kwargs)
    except Exception as exc:
        raise Exception('Failed to run mpv ({})'.format(exc))
    out, err = p.communicate()
    if check_code and p.returncode != 0:
        raise Exception('mpv exited with error')
    if catch_stdout:
        out = out.decode(OS_ENCODING)
    err = err.decode(OS_ENCODING)
    return {'stdout': out, 'stderr': err, 'code': p.returncode}


def check_dependencies():
    pythonv = '{}.{}.{}'.format(*sys.version_info)
    if ((sys.version_info[0] == 2 and sys.version_info[1] < 7) or
            (sys.version_info[0] == 3 and sys.version_info[1] < 2) or
            # Just in case... Also don't restrict <= 3, script may
            # probably work on Python 4+ too.
            sys.version_info[0] < 2):
        raise Exception(
            'Python version must be 2.7+ or 3.2+, using: {}'.format(pythonv))

    ffverout = _ffmpeg_output(['-version'])['stdout']
    try:
        line = ffverout.split('\n', 1)[0]
        ffmpegv = re.match(r'ffmpeg version (\S+)', line).group(1)
    except Exception:
        raise Exception('Cannot parse FFmpeg version')
    # NOTE: Checking only for '^x.y.z', possible non-numeric symbols
    # after 'z' don't matter.
    if re.match(r'\d+\.\d+\.\d+', ffmpegv):
        if int(ffmpegv.split('.', 1)[0]) < 2:
            raise Exception('FFmpeg version must be 2+, '
                            'using: {}'.format(ffmpegv))
    else:
        # Most probably version from git. Do nothing.
        pass

    codecout = _ffmpeg_output(['-codecs'])['stdout']
    if not re.search(r'encoders:.*\blibvpx-vp9\b', codecout):
        raise Exception(
            'FFmpeg is not compiled with libvpx (libvpx-vp9) support')
    if not re.search(r'encoders:.*\blibopus\b', codecout):
        raise Exception('FFmpeg is not compiled with libopus support')

    mpvv = 'no'
    need_mpv = '-p' in sys.argv[1:]
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
                raise Exception('Cannot parse mpv version')
        else:
            # NOTE: Checking only for '^x.y.z', possible non-numeric symbols
            # after 'z' don't matter.
            if need_mpv and re.match(r'\d+\.\d+\.\d+', mpvv):
                major, minor, _ = mpvv.split('.', 2)
                if int(major) == 0 and int(minor) < 8:
                    raise Exception('mpv version must be 0.8+, '
                                    'using: {}'.format(ffmpegv))
            else:
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


def process_options(verinfo):
    import argparse
    doc = __doc__.format(stitle=__stitle__, title=__title__, **verinfo)

    parser = argparse.ArgumentParser(
        prog=__title__,
        description=doc,
        formatter_class=argparse.RawTextHelpFormatter)
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
        '-tt', metavar='fakeduration', nargs='?', const=_FullFakeDuration,
        help='use given fake duration to calculate the bitrate\n'
             'duration may be either in seconds or in "hh:mm:ss[.xxx]" form\n'
             'skip value to use the full duration of video\n'
             '-tt, -tot and -vb are mutually exclusive')
    parser.add_argument(
        '-tot', metavar='fakeposition',
        help='use given fake ending time to calculate the bitrate\n'
             'position may be either in seconds or in "hh:mm:ss[.xxx]" form')
    parser.add_argument(
        '-ow', metavar='width', type=int,
        help='output width, e.g. 1280\n'
             'when overriding either the default width or height, the output\n'
             'will be scaled to the correct aspect ratio, but not when you\n'
             'override both.')
    parser.add_argument(
        '-oh', metavar='height', type=int,
        help='output height, e.g. 720')
    parser.add_argument(
        '-sws', metavar='algo', default='lanczos',
        help='scaling algorithm (default: %(default)s)')
    parser.add_argument(
        '-l', metavar='size', type=float,
        help='filesize limit in mebibytes (default: 8)\n'
             '-l and -vb are mutually exclusive')
    parser.add_argument(
        '-vb', metavar='bitrate', type=int,
        help='video bitrate in kbits')
    parser.add_argument(
        '-crf', metavar='crf', type=int,
        help='set the quality level (0..63)')
    parser.add_argument(
        '-qmin', metavar='qmin', type=int,
        help='set minimum (best) quality level (0..63)')
    parser.add_argument(
        '-qmax', metavar='qmax', type=int,
        help='set maximum (worst) quality level (0..63)')
    parser.add_argument(
        '-vs', metavar='videostream', type=int,
        help='video stream number to use (default: best)')
    parser.add_argument(
        '-vf', metavar='videofilters',
        help='additional video filters to use')
    parser.add_argument(
        '-vfi', metavar='videofilters',
        help='insert video filters at the start of filter chain')
    parser.add_argument(
        '-an', action='store_true',
        help='do not include audio to the output file\n'
             'you cannot use -an with -ab, -aa, -as, -af options')
    parser.add_argument(
        '-ab', metavar='bitrate', type=int,
        help='audio bitrate in kbits (default: 64)')
    parser.add_argument(
        '-aa', metavar='audiofile',
        help='add (use) external audio file\n'
             'if specified, its first stream will be muxed into resulting\n'
             'file unless -as is also given')
    parser.add_argument(
        '-as', metavar='audiostream', type=int,
        help='audio stream number to use (default: best/suitable)')
    parser.add_argument(
        '-af', metavar='audiofilters',
        help='audio filters to use')
    parser.add_argument(
        '-sa', metavar='subfile', const=True, nargs='?',
        help='add (burn) subtitles to the video\n'
             'will use subtitles from the given file or from the input video\n'
             'if filename is omitted')
    parser.add_argument(
        '-si', metavar='subindex', type=int,
        help='subtitle index to use (default: first/suitable)\n'
             "note: it's not the global stream number, but the index of\n"
             'subtitle stream across other subtitles; see ffmpeg-filters(1)\n'
             'for details')
    parser.add_argument(
        '-p', action='store_true',
        help='run player (mpv) in interactive mode to cut and crop video\n'
             'you cannot use -p with -ss, -t, -to options')
    parser.add_argument(
        '-poo', metavar='mpvopts',
        help='additional raw player (mpv) options\n'
             "example: -poo='--no-config' (equal sign is mandatory)")
    parser.add_argument(
        '-mn', action='store_true',
        help='strip metadata from the output file')
    parser.add_argument(
        '-oo', metavar='ffmpegopts',
        help='additional raw FFmpeg options\n'
             "example: -oo='-aspect 16:9' (equal sign is mandatory)")
    parser.add_argument(
        '-ooi', metavar='ffmpegopts',
        help='raw FFmpeg options to insert before first input\n'
             "example: -ooi='-loop 1' (equal sign is mandatory)")
    parser.add_argument(
        '-cn', action='store_true',
        help='skip any dependency/version checkings\n'
             'advanced option, use at your own risk')

    args = sys.argv[1:]
    if _PY2:
        # Convert command line arguments to unicode.
        # See: <http://stackoverflow.com/q/4012571>,
        # <https://bugs.python.org/issue2128> for details.
        args = [arg.decode(OS_ENCODING) for arg in args]
    options = parser.parse_args(args)
    # Additional input options validation.
    # NOTE: We ensure only minimal checkings here to not restrict the
    # possible weird uses. E.g. ow, oh, vs, as, si can be zero or
    # negative.
    if options.outfile is None:
        if options.infile[-5:] == '.webm':
            # Don't overwrite input file.
            # NOTE: Input file can be in other directory or -ss/-t/-to
            # is specified so default output name will be different but
            # for now we don't bother checking this.
            parser.error('specify output file please')
    elif _is_same_paths(options.infile, options.outfile):
        parser.error('specify another output file please')
    if options.t is not None and options.to is not None:
        parser.error('-t and -to are mutually exclusive')
    if ((options.tt is not None and options.vb is not None) or
            (options.tot is not None and options.vb is not None) or
            (options.tt is not None and options.tot is not None)):
        parser.error('-tt, -tot and -vb are mutually exclusive')
    if options.vb is None:
        if options.l is None:
            options.l = 8
        elif options.l <= 0:
            parser.error('Bad limit value')
    else:
        if options.l is not None:
            parser.error('-l and -vb are mutually exclusive')
        if options.vb < 0:
            parser.error('invalid video bitrate')
        options.l = None
    if options.crf is not None and (options.crf < 0 or options.crf > 63):
        parser.error('quality level must be in 0..63 range')
    if options.qmin is not None and (options.qmin < 0 or options.qmin > 63):
        parser.error('quality level must be in 0..63 range')
    if options.qmax is not None and (options.qmax < 0 or options.qmax > 63):
        parser.error('quality level must be in 0..63 range')
    if options.qmin is not None and options.qmax is not None:
        if options.qmin > options.qmax:
            parser.error('minimum quality level greater than maximum level')
    if (options.crf is not None and
            (options.qmin is not None or options.qmax is not None)):
        qmin = 0 if options.qmin is None else options.qmin
        qmax = 63 if options.qmax is None else options.qmax
        if not qmin <= options.crf <= qmax:
            parser.error('qmin <= crf <= qmax relation violated')
    if options.an:
        if (options.ab is not None or
                options.aa is not None or
                getattr(options, 'as') is not None or
                options.af is not None):
            parser.error('you cannot use -an with -ab, -aa, -as, af')
        # No audio, i.e. its bitrate is zero.
        options.ab = 0
    else:
        if options.ab is None:
            options.ab = 64
        elif options.ab < 1:
            # NOTE: We use audio bitrate in ``_calc_video_bitrate`` so
            # it should be defined. Can audio bitrate be zero? Can video
            # and audio bitrates be float? Plese send bugreport if you
            # have some problems with that.
            parser.error('invalid audio bitrate')
    if options.p:
        if (options.ss is not None or
                options.t is not None or
                options.to is not None):
            parser.error('you cannot use -p with -ss, -t, -to options')
    return options


def _parse_time(time):
    if isinstance(time, _NUM_TYPES):
        return time
    # [hh]:[mm]:[ss[.xxx]]
    m = re.match(r'(?:(\d+):)?(?:(\d+)+:)?(\d+(?:\.\d+)?)$', time)
    if not m:
        raise Exception('Invalid time {}'.format(time))
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


def _get_mpv_log_prefix(path):
    """
    Analogue of ``script_name_from_filename`` from
    ``mpv/player/scripting.c``
    """
    name = os.path.basename(path)
    name = os.path.splitext(name)[0]
    name = re.sub(r'[^A-Za-z0-9]', '_', name)
    return name


def _doc_to_help(doc):
    doc = doc.strip()
    lines = doc.split('\n')
    lines = [line.strip() for line in lines]
    return '\n'.join(lines)


def run_interactive_mode(options):
    """
    Running interactive mode.

    Press "c" first time to mark the start of the fragment.
    Press it again to mark the end of the fragment.
    Press "KP1" after "c" to define the fragment from
    the start to the marked time.
    Press "KP3" after "c" to define the fragment from
    the marked time to the end of the video.

    Select crop area with the mouse and adijust it precisely with
    KP4/KP8/KP6/KP2 (move crop area left/up/right/down) and
    KP7/KP9/-/+ (decrease/increase width/height).
    Press KP_ENTER when you finished with crop.

    Once you defined cut fragment and/or crop are, close the
    player and let the script do all hard work for calculating
    the bitrate and encoding.
    """
    # NOTE: mpv ignores Lua scripts without suffix.
    luafh, luafile = tempfile.mkstemp(suffix='.lua')
    options.luafile = luafile
    try:
        os.write(luafh, MPV_SCRIPT)
    finally:
        os.close(luafh)

    # Disabling OSC since it conflicts with interactive mode.
    args = ['--no-osc', '--script', luafile]
    script_log_prefix = _get_mpv_log_prefix(luafile)
    args += ['--msg-level', 'all=no,{}=warn'.format(script_log_prefix)]
    if options.poo is not None:
        args += options.poo.split()
    args += [options.infile]
    print(_doc_to_help(run_interactive_mode.__doc__), file=sys.stderr)

    # We let the user to see stderr output and catch stdout by ourself.
    out = _mpv_output(args, debug=True, catch_stdout=False)['stderr']
    cut = None
    crop = None
    for line in reversed(out.split()):
        if not cut:
            cutm = re.match(
                r'cut=(-1|\d+(?:\.\d+)?):(-1|\d+(?:\.\d+)?)$',
                line)
            if cutm:
                cut = cutm.groups()
                if crop:
                    break
                continue
        if not crop:
            cropm = re.match(r'(crop=(\d+):(\d+):(\d+):(\d+))$', line)
            if cropm:
                crop = cropm.groups()
                if cut:
                    break

    # NOTE: We don't mind checking cut ranges and crop values because:
    # 1) It should be already checked in Lua script
    # 2) We will check some of them anyway in ``_get_durations``
    print('='*50, file=sys.stderr)
    if cut:
        # ``-1`` is a special value and defines start/end of the file.
        shift = '0' if cut[0] == '-1' else _timestamp(float(cut[0]))
        endpos = 'EOF' if cut[1] == '-1' else _timestamp(float(cut[1]))
        print('[CUT] {} - {}'.format(shift, endpos), file=sys.stderr)
    if crop:
        print('[CROP] x1={}, y1={}, width={}, height={}'.format(
                crop[3], crop[4], crop[1], crop[2]),
              file=sys.stderr)

    if cut or crop:
        try:
            ok = input('Continue with that settings? Y/n ')
        except EOFError:
            sys.exit(1)
        if ok == '' or ok.lower() == 'y':
            if cut:
                if cut[0] != '-1':
                    options.ss = cut[0]
                if cut[1] != '-1':
                    options.to = cut[1]
            if crop:
                options.vfi = crop[0] if options.vfi is None \
                    else '{},{}'.format(options.vfi, crop[0])
        else:
            sys.exit(1)
    else:
        print("You haven't defined neither cut nor crop.", file=sys.stderr)
        try:
            ok = input('Encode input video intact? y/N ')
        except EOFError:
            sys.exit(1)
        if ok == '' or ok.lower() != 'y':
            sys.exit(1)


def _get_durations(options):
    out = _ffmpeg_output(
        ['-hide_banner', '-i', options.infile],
        check_code=False)['stderr']
    try:
        dur = re.search(r'\bDuration: ([^,]+)', out).group(1)
    except Exception:
        raise Exception('Failed to parse duration of input file')
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
            raise Exception('Duration must not be zero')
        if shift + outduration > induration:
            raise Exception('End position too far in the future')
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
        outduration = induration

    # Validate fake ranges.
    if options.tt is not None:
        if options.tt is _FullFakeDuration:
            foutduration = induration
        else:
            foutduration = _parse_time(options.tt)
            if foutduration == 0:
                raise Exception('Duration must not be zero')
            elif foutduration > induration:
                raise Exception('End position too far in the future')
    elif options.tot is not None:
        fendpos = _parse_time(options.tot)
        foutduration = fendpos - shift
        if fendpos > induration:
            raise Exception(
                'End position {} too far in the future '
                '(input has only {} duration)'.format(options.tot, dur))
        if fendpos <= shift:
            raise Exception(
                'End position is less or equal than the input seek')
    else:
        foutduration = outduration

    return {
        'induration': induration,
        'outduration': outduration,
        'foutduration': foutduration,
    }


def _get_output_filename(options):
    name = os.path.basename(options.infile)
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


def _round(x, d=0):
    """
    round function from Python2. See
    <http://python3porting.com/differences.html#rounding-behavior> for
    details.
    """
    p = 10 ** d
    return float(math.floor((x * p) + math.copysign(0.5, x)))/p


def _calc_video_bitrate(options):
    if options.tt is not None or options.tot is not None:
        outduration = options.foutduration
    else:
        outduration = options.outduration
    # mebibytes * 1024 * 8 = kbits
    bitrate = int(_round(options.l * 8192 / outduration - options.ab))
    if bitrate < 1:
        # Prevent failing to constant/CQ mode because of too low
        # limit/long duration/big audio bitrate.
        raise Exception('Unable to calculate video bitrate')
    return bitrate


def _encode(options, firstpass):
    passn = '1' if firstpass else '2'
    logfile = options.logfile[:-6]
    vb = '{}k'.format(options.vb) if options.vb else '0'
    ab = '{}k'.format(options.ab) if options.ab else '0'
    threads = _TEXT_TYPE(options.threads)
    speed = '4' if firstpass else '1'
    outfile = os.devnull if firstpass else options.outfile

    # Input.
    args = ['-hide_banner']
    if options.ss is not None:
        args += ['-ss', options.ss]
    if options.ooi is not None:
        args += options.ooi.split()
    args += ['-i', options.infile]
    if options.aa is not None:
        args += ['-i', options.aa]
    if options.t is not None or options.to is not None:
        args += ['-t', _TEXT_TYPE(options.outduration)]

    # Streams.
    if (options.vs is not None or
            getattr(options, 'as') is not None or
            options.aa is not None):
        vstream = 0 if options.vs is None else options.vs
        args += ['-map', '0:{}'.format(vstream)]
        ainput = 0 if options.aa is None else 1
        astream = getattr(options, 'as')
        if astream is None:
            astream = 1 if options.aa is None else 0
        args += ['-map', '{}:{}'.format(ainput, astream)]
    if options.mn:
        args += ['-map_metadata', '-1']

    # Video.
    args += [
        '-sn',
        '-pass', passn, '-passlogfile', logfile,
        '-c:v', 'libvpx-vp9', '-b:v', vb,
        '-threads', threads, '-speed', speed,
        '-tile-columns', '6', '-frame-parallel', '1',
        '-auto-alt-ref', '1', '-lag-in-frames', '25',
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
    if options.ow is not None or options.oh is not None:
        scale='scale='
        scale += '-1' if options.ow is None else _TEXT_TYPE(options.ow)
        scale += ':'
        scale += '-1' if options.oh is None else _TEXT_TYPE(options.oh)
        vfilters += [scale]
        args += ['-sws_flags', options.sws]
    if options.sa is not None:
        if options.ss is not None:
            vfilters += ['setpts=PTS+{}/TB'.format(_parse_time(options.ss))]
        subtitles = 'subtitles='
        subfile = options.infile if options.sa is True else options.sa
        # This escaping should be sufficient for FFmpeg filter argument
        # (see ffmpeg-utils(1), "Quotes and escaping").
        subfile = subfile.replace('\\', '\\\\')
        subfile = subfile.replace("'", "\\'")
        subtitles += "'{}'".format(subfile)
        if options.si is not None:
            subtitles += ':si={}'.format(options.si)
        vfilters += [subtitles]
        if options.ss is not None:
            vfilters += ['setpts=PTS-STARTPTS']
    if options.vf is not None:
        vfilters += [options.vf]
    if vfilters:
        args += ['-vf', ','.join(vfilters)]

    # Audio.
    if firstpass or options.an:
        args += ['-an']
    else:
        args += ['-c:a', 'libopus', '-b:a', ab, '-ac', '2']
        if options.af is not None:
            args += ['-af', options.af]

    # Misc.
    if options.oo is not None:
        args += options.oo.split()

    # Output.
    args += ['-f', 'webm', '-y', outfile]

    _ffmpeg(args, debug=True)


def encode(options):
    import multiprocessing
    options.__dict__.update(_get_durations(options))
    if options.outfile is None:
        options.outfile = _get_output_filename(options)
    if options.vb is None:
        options.vb = _calc_video_bitrate(options)
    options.threads = multiprocessing.cpu_count()
    options.logfile = tempfile.mkstemp(suffix='-0.log')[1]
    _encode(options, firstpass=True)
    _encode(options, firstpass=False)


def print_stats(options, start):
    print('='*50, file=sys.stderr)
    print('Output file: {}'.format(options.outfile), file=sys.stderr)
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
        limit = int(_round(options.l * 1024 * 1024))
        if size > limit:
            sizeinfo += ', OVERWEIGHT: {} B'.format(size - limit)
        elif size < limit:
            sizeinfo += ', underweight: {} B'.format(limit - size)
    print(sizeinfo, file=sys.stderr)
    runtime = _timestamp(time.time() - start)
    print('Overall time spent: {}'.format(runtime), file=sys.stderr)


def _is_verbose(options):
    default = '-v' in sys.argv[1:]
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
        if '-cn' not in sys.argv[1:]:
            verinfo = check_dependencies()
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
        print(err, file=sys.stderr)
        sys.exit(1)
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
local sw, sh = 0, 0
-- NOTE: That's not a real values, but a scaled ones. You need to
-- multiple them to sw/sh before returning back to user.
local width, height = 0, 0
-- x2 can be less than x1, y2 can be less than y1.
local crop_x1, crop_y1, crop_x2, crop_y2 = 0, 0, 0, 0
local move_x, move_y = 0, 0

function log2user(str)
    io.stdout:write(str .. "\n")
    mp.osd_message(str, 2)
end

function log2webm(str)
    io.stderr:write(str .. "\n")
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

function crop_drag_start()
    local x, y = mp.get_mouse_pos()
    if crop_active then
        if math.min(crop_x1, crop_x2) <= x and
                math.min(crop_y1, crop_y2) <= y and
                x <= math.max(crop_x1, crop_x2) and
                y <= math.max(crop_y1, crop_y2) then
            crop_moving = true
            move_x, move_y = x, y
        else
            crop_resizing = true
            crop_x1, crop_y1 = x, y
            crop_x2, crop_y2 = x, y
            clear_scr()
        end
    else
        -- Reinit values on each new crop.
        crop_active = true
        local dwidth = mp.get_property_number("dwidth")
        local dheight = mp.get_property_number("dheight")
        -- Get scale factor.
        local res_x, res_y = mp.get_osd_resolution()
        sw = dwidth / res_x
        sh = dheight / res_y
        -- Scale resolution.
        width = dwidth / sw
        height = dheight / sh

        -- Start resizing by default.
        crop_resizing = true
        crop_x1, crop_y1 = x, y
        crop_x2, crop_y2 = x, y
    end
end

function crop_drag_end()
    crop_resizing = false
    crop_moving = false
end

function crop_drag()
    if crop_resizing then
        crop_x2, crop_y2 = mp.get_mouse_pos()
        if crop_x2 < 0 then crop_x2 = 0 end
        if crop_x2 >= width then crop_x2 = width end
        if crop_y2 < 0 then crop_y2 = 0 end
        if crop_y2 >= height then crop_y2 = height end
        render_crop_rect()
    elseif crop_moving then
        x, y = mp.get_mouse_pos()
        local delta_x, delta_y = x - move_x, y - move_y
        move_x, move_y = x, y
        if math.min(crop_x1, crop_x2) + delta_x >= 0 and
                math.max(crop_x1, crop_x2) + delta_x <= width then
            crop_x1 = crop_x1 + delta_x
            crop_x2 = crop_x2 + delta_x
        end
        if math.min(crop_y1, crop_y2) + delta_y >= 0 and
                math.max(crop_y1, crop_y2) + delta_y <= height then
            crop_y1 = crop_y1 + delta_y
            crop_y2 = crop_y2 + delta_y
        end
        render_crop_rect()
    end
end

function crop()
    if not crop_active then
        log2user("Crop region is empty")
        return
    end
    local crop_x = math.floor(sw * math.min(crop_x1, crop_x2))
    local crop_y = math.floor(sh * math.min(crop_y1, crop_y2))
    local crop_w = math.floor(sw * math.abs(crop_x2 - crop_x1))
    local crop_h = math.floor(sh * math.abs(crop_y2 - crop_y1))
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
    if crop_active and math.min(crop_x1, crop_x2) >= crop_x_step then
        crop_x1 = crop_x1 - crop_x_step
        crop_x2 = crop_x2 - crop_x_step
        render_crop_rect()
    end
end

function crop_x_inc()
    if crop_active and math.max(crop_x1, crop_x2) <= width - crop_x_step then
        crop_x1 = crop_x1 + crop_x_step
        crop_x2 = crop_x2 + crop_x_step
        render_crop_rect()
    end
end

function crop_y_dec()
    if crop_active and math.min(crop_y1, crop_y2) >= crop_y_step then
        crop_y1 = crop_y1 - crop_y_step
        crop_y2 = crop_y2 - crop_y_step
        render_crop_rect()
    end
end

function crop_y_inc()
    if crop_active and math.max(crop_y1, crop_y2) <= height - crop_y_step then
        crop_y1 = crop_y1 + crop_y_step
        crop_y2 = crop_y2 + crop_y_step
        render_crop_rect()
    end
end

mp.add_key_binding("c", "webm_cut", cut)
mp.add_key_binding("KP1", "webm_cut_from_start", cut_from_start)
mp.add_key_binding("KP3", "webm_cut_to_end", cut_to_end)

-- XXX: Don't know how to make `mp.add_key_binding` work with dragging.
mp.set_key_bindings({{"mouse_btn0", crop_drag_end, crop_drag_start}}, "webm")
mp.enable_key_bindings("webm")
local rp = {repeatable = true}
mp.add_key_binding("mouse_move", "webm_crop_drag", crop_drag, rp)
mp.add_key_binding("KP7", "webm_cropw_dec", crop_width_dec, rp)
mp.add_key_binding("KP9", "webm_cropw_inc", crop_width_inc, rp)
mp.add_key_binding("-", "webm_croph_dec", crop_height_dec, rp)
mp.add_key_binding("+", "webm_croph_inc", crop_height_inc, rp)
mp.add_key_binding("KP4", "webm_cropx_dec", crop_x_dec, rp)
mp.add_key_binding("KP6", "webm_cropx_inc", crop_x_inc, rp)
mp.add_key_binding("KP8", "webm_cropy_dec", crop_y_dec, rp)
mp.add_key_binding("KP2", "webm_cropy_inc", crop_y_inc, rp)
mp.add_key_binding("KP_ENTER", "webm_crop", crop, rp)
"""


if __name__ == '__main__':
    main()
