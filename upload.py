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
    # NOTE: On Py3 both of this are unicode strings, on Py2 both are
    # bytes. We can't use unicode_literals in Py2 because sys.argv may
    # contain non-ascii encoded string and python will complain.
    if '-u' in sys.argv[1:]:
        cmd += ' upload'
    doc = pandoc.Document()
    # NOTE: pyandoc accepts bytes and returns bytes. Also it doesn't
    # work with Py3.
    doc.markdown = open('README.md', 'rb').read()
    f = open('README.rst', 'wb')
    f.write(doc.rst)
    f.close()
    os.system(cmd)


if __name__ == '__main__':
    main()
