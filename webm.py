#!/usr/bin/env python

"""
convert videos to webm format using ffmpeg

features:
  - encodes input video to webm container with VP9 and Opus
  - uses two-pass encode with the settings recommended by the developers
  - fits output file to the given size limit
  - allows to select video/audio streams and external audio track

dependencies:
  - Python 2.7+ or 3.2+ (using: {pythonv})
  - FFmpeg 2+ compiled with libvpx and libopus (using: {ffmpegv})

encoding modes:
  - by default bitrate calculated to fit the output video to limit
  - you may specify custom bitrate to use
  - -crf option enables constrained quality mode
  - -crf and -vb 0 enable constant quality mode

examples:
  - fit video to default limit:\t./{title} -i in.mkv
  - fit video to 6 MiB:\t\t./{title} -i in.mkv -l 6
  - use custom bitrate:\t\t./{title} -i in.mkv -vb 600k
  - constrained quality:\t./{title} -i in.mkv -crf 20
  - CQ with custom limit:\t./{title} -i in.mkv -crf 20 -l 6
  - CQ with custom bitrate:\t./{title} -i in.mkv -crf 20 -vb 600k
  - constant quality:\t\t./{title} -i in.mkv -crf 20 -vb 0
"""

# TODO:
#     * Burn subtitles
#     * Limit quality
#     * Best quality mode
#     * Fit audio to limit
#     * Option to disable audio
#     * Option to strip metadata
#     * Interactive seeking/cropping with mpv
#     * Optionally use mkvmerge for muxing

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os
import re
import sys
import time
import tempfile
import traceback
import subprocess


__title__ = 'webm.py'
__version__ = '0.0.3'
__license__ = 'CC0'


_PY2 = sys.version_info[0] == 2
_TEXT_TYPE = unicode if _PY2 else str
_NUM_TYPES = (int, long, float) if _PY2 else (int, float)


def _is_verbose(options):
    return getattr(options, 'verbose', False)


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
    out = out.decode(sys.stdout.encoding)
    err = err.decode(sys.stderr.encoding)
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
    doc = __doc__.format(title=__title__, **verinfo)

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
        help='output file, e.g. output.webm\n'
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
        '-tt', metavar='duration',
        help='use given duration to calculate the bitrate\n'
             'duration may be either in seconds or in "hh:mm:ss[.xxx]" form\n'
             'pass zero to use the full duration of video\n'
             '-tt and -vb are mutually exclusive')
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
        '-l', metavar='size', default=_NoLimit, type=int,
        help='filesize limit in mebibytes (default: 8)\n'
             '-l and -vb are mutually exclusive')
    parser.add_argument(
        '-vb', metavar='bitrate', type=int,
        help='video bitrate in kbits')
    parser.add_argument(
        '-crf', metavar='crf', type=int,
        help='set the quality level (0..63)')
    parser.add_argument(
        '-ab', metavar='bitrate', default=64, type=int,
        help='audio bitrate in kbits (default: %(default)s)')
    parser.add_argument(
        '-vs', metavar='videostream', type=int,
        help='video stream number to use (default: best/suitable)')
    parser.add_argument(
        '-as', metavar='audiostream', type=int,
        help='audio stream number to use (default: best/suitable)')
    parser.add_argument(
        '-af', metavar='audiofile',
        help='external audio file to use\n'
             'if specified, its first stream will be muxed into resulting\n'
             'file unless -as is also given')

    args = sys.argv[1:]
    if _PY2:
        # Convert command line arguments to unicode.
        # See: <http://stackoverflow.com/q/4012571>,
        # <https://bugs.python.org/issue2128> for details.
        args = [arg.decode(sys.stdin.encoding) for arg in args]
    options = parser.parse_args(args)
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
    if options.tt is not None and options.vb is not None:
        parser.error('-tt and -vb are mutually exclusive')
    if options.vb is None:
        if options.l is _NoLimit:
            options.l = 8
        elif not options.l:
            parser.error('Bad limit value')
    elif options.l is not _NoLimit:
        parser.error('-l and -vb are mutually exclusive')
    else:
        options.l = 0
    if options.crf is not None and (options.crf < 0 or options.crf > 63):
        parser.error('quality level must be in 0..63 range')
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


def _get_input_duration(options):
    out = _ffmpeg_output(
        ['-hide_banner', '-i', options.infile],
        check_code=False)['stderr']
    try:
        dur = re.search(r'\bDuration: ([^,]+)', out).group(1)
    except Exception:
        raise Exception('Failed to parse duration of input file')
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
        if endpos > induration:
            raise Exception(
                'End position {} too far in the future '
                '(input has only {} duration)'.format(options.to, dur))
        if endpos <= shift:
            raise Exception(
                'End position is less or equal than the input seek')
    return induration


def _get_timestamp(duration):
    idur = int(duration)
    ts = '{:02d}:{:02d}:{:02d}'.format(idur//3600, idur%3600//60, idur%60)
    frac = round(duration % 1, 1)
    if frac >= 0.1:
        ts += _TEXT_TYPE(frac)[1:]
    return ts


def _get_output_filename(options):
    name = os.path.basename(options.infile)
    name = os.path.splitext(name)[0]
    if (options.ss is not None or
            options.t is not None or
            options.to is not None):
        name += '_'
        shift = 0 if options.ss is None else _parse_time(options.ss)
        name += _get_timestamp(shift)
        name += '-'
        if options.t:
            endtime = shift + _parse_time(options.t)
        elif options.to:
            endtime = _parse_time(options.to)
        else:
            endtime = options.induration
        name += _get_timestamp(endtime)
    name += '.webm'
    return name


def _calc_target_bitrate(options):
    if options.tt is not None:
        outduration = _parse_time(options.tt)
        if outduration == 0:
            outduration = options.induration
    elif options.t is not None:
        outduration = _parse_time(options.t)
    elif options.ss is not None:
        if options.to is not None:
            outduration = _parse_time(options.to) - _parse_time(options.ss)
        else:
            outduration = options.induration - _parse_time(options.ss)
    elif options.to is not None:
        outduration = _parse_time(options.to)
    else:
        outduration = options.induration
    # mebibytes * 1024 * 8 = kbits
    return int(round(options.l * 8192 / outduration - options.ab))


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
    if options.af is not None:
        args += ['-i', options.af]
    if options.t is not None:
        args += ['-t', options.t]
    elif options.to is not None:
        args += ['-to', options.to]

    # Streams.
    if (options.vs is not None
            or getattr(options, 'as') is not None
            or options.af is not None):
        vstream = 0 if options.vs is None else options.vs
        args += ['-map', '0:{}'.format(vstream)]
        ainput = 0 if options.af is None else 1
        astream = getattr(options, 'as')
        if astream is None:
            astream = 1 if options.af is None else 0
        args += ['-map', '{}:{}'.format(ainput, astream)]

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

    # Filters.
    if options.ow is not None or options.oh is not None:
        scale='scale='
        scale += '-1' if options.ow is None else _TEXT_TYPE(options.ow)
        scale += ':'
        scale += '-1' if options.oh is None else _TEXT_TYPE(options.oh)
        args += ['-vf', scale, '-sws_flags', options.sws]

    # Audio.
    if firstpass:
        args += ['-an']
    else:
        args += ['-c:a', 'libopus', '-b:a', ab, '-ac', '2']

    # Output.
    args += ['-f', 'webm', '-y', outfile]

    _ffmpeg(args, debug=True)


def encode(options):
    import multiprocessing
    options.induration = _get_input_duration(options)
    if options.outfile is None:
        options.outfile = _get_output_filename(options)
    if options.vb is None:
        options.vb = _calc_target_bitrate(options)
    options.threads = multiprocessing.cpu_count()
    options.logfile = tempfile.mkstemp(suffix='-0.log')[1]
    _encode(options, firstpass=True)
    _encode(options, firstpass=False)


def print_stats(options, start):
    print('='*50, file=sys.stderr)
    print('Output file: {}'.format(options.outfile), file=sys.stderr)
    print('Output bitrate: {}k'.format(options.vb), file=sys.stderr)
    size = os.path.getsize(options.outfile)
    sizeinfo = 'Output file size: {} B'.format(size)
    if size > 1024:
        sizeinfo += ', {:.2f} KiB'.format(size/1024)
    if size > 1024 * 1024:
        sizeinfo += ', {:.2f} MiB'.format(size/1024/1024)
    if options.l:
        limit = options.l * 1024 * 1024
        if size > limit:
            sizeinfo += ', overweight: {} B'.format(size - limit)
        else:
            sizeinfo += ', underweight: {} B'.format(limit - size)
    print(sizeinfo, file=sys.stderr)
    runtime = int(round(time.time() - start))
    if runtime > 60:
        runtime = '{}m{}s'.format(runtime//60, runtime%60)
    else:
        runtime = '{}s'.format(runtime)
    print('Overall time spent: {}'.format(runtime), file=sys.stderr)


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
