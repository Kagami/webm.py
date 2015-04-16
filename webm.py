#!/usr/bin/env python

"""
convert videos to webm format using ffmpeg

features:
  - encodes input video to webm container with VP9 and Opus
  - uses two-pass encode with the settings recommended by the developers
  - fits video to the given size

dependencies:
  - Python 2.7+ or 3.2+ (using: {pythonv})
  - FFmpeg 2+ compiled with libvpx and libopus (using: {ffmpegv})
"""

# TODO:
#     * Accept external audio file
#     * Option to disable audio
#     * Stream mapping
#     * Option to strip metadata
#     * CRF/CQ/BQ modes
#     * Burn subtitles
#     * Support for VP8 and Vorbis
#     * Fit audio to limit
#     * Seeking/cropping the video

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
__version__ = '0.0.2'
__license__ = 'CC0'


_PY2 = sys.version_info[0] == 2
_TEXT_TYPE = unicode if _PY2 else str


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
    if re.match(r'\d+\.\d+\.\d+', ffmpegv):
        if int(ffmpegv.split('.', 1)[0]) < 2:
            raise Exception('FFmpeg version must be 2+, '
                            'using: {}'.format(ffmpegv))
    else:
        # Most probably version from git. Don't do anything.
        pass
    codecout = _ffmpeg_output(['-codecs'])['stdout']
    if not re.search(r'encoders:.*\blibvpx-vp9\b', codecout):
        raise Exception(
            'FFmpeg is not compiled with libvpx (libvpx-vp9) support')
    if not re.search(r'encoders:.*\blibopus\b', codecout):
        raise Exception('FFmpeg is not compiled with libopus support')
    return {'pythonv': pythonv, 'ffmpegv': ffmpegv}


def process_options(verinfo):
    import argparse
    class _NoLimit: pass

    doc = __doc__.format(**verinfo)
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
        help='input file')
    parser.add_argument(
        'outfile',
        help='output file')
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
        '-ab', metavar='bitrate', default=64, type=int,
        help='audio bitrate in kbits (default: %(default)s)')
    options = parser.parse_args()
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
    return options


def _parse_time(time):
    # hh:mm:ss[.xxx] -> (hh:(mm)):(ss.xxx)
    m = re.match(r'(?:(\d+):(?:(\d+)+:)?)?(\d+(?:\.\d+)?)$', time)
    if not m:
        raise Exception('Invalid time {}'.format(time))
    hours, minutes, seconds = m.groups()
    duration = float(seconds)
    if minutes:
        minutes = int(minutes)
        duration += minutes * 60
    if hours:
        hours = int(hours)
        if minutes:
            duration += hours * 3600
        else:
            duration += hours * 60
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
        if endpos >= shift:
            raise Exception(
                'End position is bigger or equal than the input shift')
    return induration


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
    return round(options.l * 8192 / outduration - options.ab)


def _encode(options, passn):
    logfile = options.logfile[:-6]
    vb = '{}k'.format(options.vb)
    ab = '{}k'.format(options.ab)
    threads = _TEXT_TYPE(options.threads)
    speed = '4' if passn == 1 else '1'
    outfile = os.devnull if passn == 1 else options.outfile

    # Input.
    args = ['-hide_banner']
    if options.ss is not None:
        args += ['-ss', options.ss]
    args += ['-i', options.infile]
    if options.t is not None:
        args += ['-t', options.t]
    elif options.to is not None:
        args += ['-to', options.to]

    # Video.
    args += [
        '-sn',
        '-pass', _TEXT_TYPE(passn), '-passlogfile', logfile,
        '-c:v', 'libvpx-vp9', '-b:v', vb,
        '-threads', threads, '-speed', speed,
        '-tile-columns', '6', '-frame-parallel', '1',
        '-auto-alt-ref', '1', '-lag-in-frames', '25',
    ]

    # Filters.
    if options.ow is not None or options.oh is not None:
        scale='scale='
        scale += '-1' if options.ow is None else _TEXT_TYPE(options.ow)
        scale += ':'
        scale += '-1' if options.oh is None else _TEXT_TYPE(options.oh)
        args += ['-vf', scale, '-sws_flags', options.sws]

    # Audio.
    if passn == 1:
        args += ['-an']
    else:
        args += ['-c:a', 'libopus', '-b:a', ab, '-ac', '2']

    # Output.
    args += ['-f', 'webm', '-y', outfile]

    _ffmpeg(args, debug=True)


def encode(options):
    import multiprocessing
    options.induration = _get_input_duration(options)
    if options.vb is None:
        options.vb = _calc_target_bitrate(options)
    options.threads = multiprocessing.cpu_count()
    options.logfile = tempfile.mkstemp(suffix='-0.log')[1]
    _encode(options, 1)
    _encode(options, 2)


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
    runtime = round(time.time() - start)
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
