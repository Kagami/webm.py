#!/usr/bin/env python

"""
Auto-generate README in reST format and upload package to PyPI.
All credits goes to <https://coderwall.com/p/qawuyq>.
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
    doc.markdown = open('README.md').read()
    f = open('README.rst', 'wb')
    f.write(doc.rst.encode('utf-8'))
    f.close()
    os.system(cmd)


if __name__ == '__main__':
    main()
