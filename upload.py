#!/usr/bin/env python

"""
Auto-generate README in reST format and upload package to PyPI.
All credit goes to <https://coderwall.com/p/qawuyq>.
"""

import os
import sys

import pandoc


pandoc.core.PANDOC_PATH = 'pandoc'


def main():
    cmd = 'python setup.py sdist'
    if '-u' in sys.argv:
        cmd += ' upload'
    doc = pandoc.Document()
    # NOTE: pyandoc accepts bytes and return bytes. It doesn't work with
    # Py3 though.
    doc.markdown = open('README.md', 'rb').read()
    f = open('README.rst', 'wb')
    f.write(doc.rst)
    f.close()
    os.system(cmd)


if __name__ == '__main__':
    main()
