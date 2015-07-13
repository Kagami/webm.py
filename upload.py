#!/usr/bin/env python

"""
Auto-generate README in reST format and upload package to PyPI.
All credits go to <https://coderwall.com/p/qawuyq>.
"""

import os
import sys

import pypandoc


def main():
    cmd = 'python setup.py sdist'
    # NOTE: On Py3 both of this are unicode strings, on Py2 both are
    # bytes. We can't use unicode_literals in Py2 because sys.argv may
    # contain non-ascii encoded string and python will complain.
    if '-u' in sys.argv[1:]:
        cmd += ' upload'
    output = pypandoc.convert(
        source='README.md',
        format='markdown_github',
        to='rst',
        outputfile='README.rst')
    assert output == ''
    os.system(cmd)


if __name__ == '__main__':
    main()
