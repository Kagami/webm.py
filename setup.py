#!/usr/bin/env python

from setuptools import setup

from webm import __version__


long_description = open('README.md', 'rb').read().decode('utf-8')


setup(
    # https://setuptools.readthedocs.io/en/latest/setuptools.html
    name='webm',
    version=__version__,
    author='Kagami Hiiragi',
    author_email='kagami@genshiken.org',
    url='https://github.com/Kagami/webm.py',
    description='Cross-platform command-line WebM converter',
    long_description=long_description,
    long_description_content_type='text/markdown',
    license='CC0',
    py_modules=['webm'],
    entry_points={
        'console_scripts': [
            'webm = webm:main',
        ],
    },
    classifiers=[
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'License :: CC0 1.0 Universal (CC0 1.0) Public Domain Dedication',
        'Operating System :: OS Independent',
        'Development Status :: 4 - Beta',
        'Intended Audience :: End Users/Desktop',
    ],
)
