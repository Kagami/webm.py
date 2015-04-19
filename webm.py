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

dependencies:
  - Python 2.7+ or 3.2+ (using: {pythonv})
  - FFmpeg 2+ compiled with libvpx and libopus (using: {ffmpegv})

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
"""

# TODO:
#     * Option to disable audio
#     * Interactive seeking/cropping with mpv
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


__stitle__ = 'webm'
__title__ = 'webm.py'
__version__ = '0.1.2'
__license__ = 'CC0'


_PY2 = sys.version_info[0] == 2
_TEXT_TYPE = unicode if _PY2 else str
_NUM_TYPES = (int, long, float) if _PY2 else (int, float)
# We can't use ``sys.stdin.encoding``/``sys.stdout.encoding`` because
# user can redirect the output so in Python2 it would return ``None``.
# Seems like ``getpreferredencoding`` is the best remaining method.
_OS_ENCODING = locale.getpreferredencoding() or 'utf-8'


def _ffmpeg(args, check_code=True, debug=False):
    args = ['ffmpeg'] + args
    if debug:
        print('='*50 + '\n' + ' '.join(args) + '\n' + '='*50, file=sys.stderr)
    p = subprocess.Popen(args)
    p.communicate()
    if check_code and p.returncode != 0:
        raise Exception('FFmpeg exited with error')
    return {'code': p.returncode}


def _ffmpeg_output(args, check_code=True, debug=False):
    args = ['ffmpeg'] + args
    if debug:
        print('='*50 + '\n' + ' '.join(args) + '\n' + '='*50, file=sys.stderr)
    p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()
    if check_code and p.returncode != 0:
        raise Exception('FFmpeg exited with error')
    out = out.decode(_OS_ENCODING)
    err = err.decode(_OS_ENCODING)
    return {'stdout': out, 'stderr': err, 'code': p.returncode}


def check_dependencies():
    pythonv = '{}.{}.{}'.format(*sys.version_info)
    if ((sys.version_info[0] == 2 and sys.version_info[1] < 7) or
            (sys.version_info[0] == 3 and sys.version_info[1] < 2)):
        raise Exception(
            'Python version must be 2.7+ or 3.2+, using: {}'.format(pythonv))
    verout = _ffmpeg_output(['-version'])['stdout']
    try:
        line = verout.split('\n', 1)[0]
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
    return {'pythonv': pythonv, 'ffmpegv': ffmpegv}


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
    class _NoLimit: pass
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
        '-tt', metavar='fakeduration',
        help='use given fake duration to calculate the bitrate\n'
             'duration may be either in seconds or in "hh:mm:ss[.xxx]" form\n'
             'pass zero to use the full duration of video\n'
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
        '-l', metavar='size', default=_NoLimit, type=float,
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
        '-ab', metavar='bitrate', default=64, type=int,
        help='audio bitrate in kbits (default: %(default)s)')
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
        '-nm', action='store_true',
        help='strip metadata from the output file')
    parser.add_argument(
        '-oo', metavar='ffmpegopts',
        help='additional raw FFmpeg options\n'
             "example: -oo='-aspect 16:9' (equal sign is mandatory)")

    args = sys.argv[1:]
    if _PY2:
        # Convert command line arguments to unicode.
        # See: <http://stackoverflow.com/q/4012571>,
        # <https://bugs.python.org/issue2128> for details.
        args = [arg.decode(_OS_ENCODING) for arg in args]
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
            parser.error('Specify output file please')
    elif _is_same_paths(options.infile, options.outfile):
        parser.error('Specify another output file please')
    if options.t is not None and options.to is not None:
        parser.error('-t and -to are mutually exclusive')
    if ((options.tt is not None and options.vb is not None) or
            (options.tot is not None and options.vb is not None) or
            (options.tt is not None and options.tot is not None)):
        parser.error('-tt, -tot and -vb are mutually exclusive')
    if options.vb is None:
        if options.l is _NoLimit:
            options.l = 8
        elif options.l <= 0:
            parser.error('Bad limit value')
    else:
        if options.l is not _NoLimit:
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
    # NOTE: We use audio bitrate in ``_calc_video_bitrate`` so it should be
    # defined. Can audio bitrate be zero? Can video and audio bitrates
    # be float? Plese send bugreport if you have some problems with
    # that.
    if options.ab < 1:
        parser.error('invalid audio bitrate')
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
        foutduration = _parse_time(options.tt)
        if foutduration == 0:
            foutduration = induration
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


def _round(x, d=0):
    """
    round function from Python2. See
    <http://python3porting.com/differences.html#rounding-behavior> for
    details.
    """
    p = 10 ** d
    return float(math.floor((x * p) + math.copysign(0.5, x)))/p


def _timestamp(duration):
    idur = int(duration)
    ts = '{:02d}:{:02d}:{:02d}'.format(idur//3600, idur%3600//60, idur%60)
    frac = duration % 1
    if frac >= 0.1:
        ts += _TEXT_TYPE(frac)[1:3]
    return ts


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


def _calc_video_bitrate(options):
    if options.tt is not None or options.tot is not None:
        outduration = options.foutduration
    else:
        outduration = options.outduration
    # mebibytes * 1024 * 8 = kbits
    return int(_round(options.l * 8192 / outduration - options.ab))


def _encode(options, firstpass):
    passn = '1' if firstpass else '2'
    logfile = options.logfile[:-6]
    vb = '{}k'.format(options.vb) if options.vb else '0'
    ab = '{}k'.format(options.ab)
    threads = _TEXT_TYPE(options.threads)
    speed = '4' if firstpass else '1'
    outfile = os.devnull if firstpass else options.outfile

    # Input.
    args = ['-hide_banner']
    if options.ss is not None:
        args += ['-ss', options.ss]
    args += ['-i', options.infile]
    if options.aa is not None:
        args += ['-i', options.aa]
    if options.t is not None or options.to is not None:
        args += ['-t', _TEXT_TYPE(options.outduration)]

    # Streams.
    if (options.vs is not None
            or getattr(options, 'as') is not None
            or options.aa is not None):
        vstream = 0 if options.vs is None else options.vs
        args += ['-map', '0:{}'.format(vstream)]
        ainput = 0 if options.aa is None else 1
        astream = getattr(options, 'as')
        if astream is None:
            astream = 1 if options.aa is None else 0
        args += ['-map', '{}:{}'.format(ainput, astream)]
    if options.nm:
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
    if firstpass:
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
    except Exception as exc:
        if _is_verbose(options):
            exc = '\n\n' + traceback.format_exc()[:-1]
        print('Error during cleanup: {}'.format(exc), file=sys.stderr)


def main():
    start = time.time()
    options = None
    try:
        verinfo = check_dependencies()
        options = process_options(verinfo)
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


if __name__ == '__main__':
    main()
