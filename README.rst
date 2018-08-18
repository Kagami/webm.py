webm.py
=======

Yet another bikeshed to encode WebM videos from CLI.

Features
--------

-  Encodes input video to WebM container with VP9 and Opus
-  Uses 2-pass encoding, has optional VP8/Vorbis and album art modes
-  Fits output file to the size limit by default
-  Allows to select video/audio streams and external audio track
-  Can burn subtitles into the video
-  Flexible set of options and ability to pass raw flags to FFmpeg
-  `Interactive mode <#interactive-mode>`__ to cut/crop input video with
   mpv

Requirements
------------

-  `Python <https://www.python.org/downloads/>`__ 2.7+ or 3.2+
-  `FFmpeg <https://ffmpeg.org/download.html>`__ 2+ compiled with libvpx
   and libopus
-  `mpv <http://mpv.io/installation/>`__ 0.17+ compiled with Lua support,
   *for interactive mode only*

Installation
------------

Just save
https://raw.githubusercontent.com/Kagami/webm.py/master/webm.py

Optionally put it somewhere in your ``PATH``:

.. code:: bash

    [sudo] wget https://github.com/Kagami/webm.py/raw/master/webm.py -O /usr/local/bin/webm
    [sudo] chmod +x /usr/local/bin/webm

Or with pip:

.. code:: bash

    [sudo] pip install webm

Usage
-----

**NOTE:** Windows users may want to add Python executable to the
``PATH``. See
https://docs.python.org/3/using/windows.html#excursus-setting-environment-variables
for details. Otherwise just type the full path to your ``python.exe``
location instead of ``python``.

Use ``webm`` instead of ``python webm.py`` if you installed it with pip.

Show help:

.. code:: bash

    python webm.py -h

Examples:

.. code:: bash

    # Fit video to default limit
    python webm.py -i in.mkv

    # Fit video to 6 MiB
    python webm.py -i in.mkv -l 6

    # Set video bitrate to 600k
    python webm.py -i in.mkv -vb 600

    # Constrained quality
    python webm.py -i in.mkv -crf 20

    # Constant quality
    python webm.py -i in.mkv -crf 20 -vb 0

    # Encode with VP8 & Vorbis
    python webm.py -i in.mkv -vp8

    # Make album art video
    python webm.py -cover -i pic.png -aa song.flac

Interactive mode
~~~~~~~~~~~~~~~~

Pass ``-p`` flag to interactively select cut frargment/crop area with
mpv. Demo:

|image0|

Show help on interactive mode:

.. code:: bash

    python webm.py -hi

Breaking changes policy
-----------------------

Versions from 0.y.0 (inclusively) till 0.y+1.0 (exclusively) keep
backward compatibility of options and settings.

Versions from x.0.0 (inclusively) till x+1.0.0 (exclusively) keep
backward compatibility of options and settings where x > 0.

Raising the minimal required version of dependency is not considered as
breaking change. Adding new required dependency is breaking change.

Related links
-------------

`webm.py wiki <https://github.com/Kagami/webm.py/wiki>`__ contains some
encoding tricks and links to documentation on WebM/VPx.

License
-------

webm.py - encode WebM videos

Written in 2015-2017 by Kagami Hiiragi kagami@genshiken.org

To the extent possible under law, the author(s) have dedicated all
copyright and related and neighboring rights to this software to the
public domain worldwide. This software is distributed without any
warranty.

You should have received a copy of the CC0 Public Domain Dedication
along with this software. If not, see
http://creativecommons.org/publicdomain/zero/1.0/.

.. |image0| image:: https://i.imgur.com/JIogF33.png
   :target: https://i.imgur.com/GjDWq3X.png
