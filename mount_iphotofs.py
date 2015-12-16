#!/usr/bin/env python
# Python 2.7
"""
Mounts an iPhoto library as a filesystem.
"""
from __future__ import print_function

import atexit
import sys
import traceback

import shutil
from platform import system

from fuse import FUSE

from iphotofuse import *

__author__ = "Robert Harder"
__email__ = "rob@iharder.net"
__copyright__ = "This code is released into the Public Domain"
__version__ = "0.1"
__status__ = "Development"

def main():

    lib_path = "/Users/rob/Pictures/iPhoto Library.photolibrary"
    lib_path = "./2007 Levi and Keatra Wedding"
    # plain_lib = iPhotoLibrary(lib_path, verbose=False)
    sys.argv.append(lib_path)
    sys.argv.append('-./mount')

    if len(sys.argv) < 2:
        print('usage: %s iphotolibrary [mountpoint]' % sys.argv[0])
        print("""
            If mountpoint is not specified or a dash -, a mount point will be made
            at the host system's default location (or best guess)
            such as /Volumes on a Mac or /media on most other systems.

            If mountpoint begins with a dash, then a mount point will be created
            automatically within the folder specified after the dash, eg,
            mount_iphotofs ~/Pictures/iPhotoLibrary.photolibrary -.
        """)
        exit(1)

    lib = iPhotoLibrary(sys.argv[1])
    if len(sys.argv) > 2:
        mount = sys.argv[2]
    else:
        mount = None
    mount_iphotofs(lib, mount)


if __name__ == '__main__':
    main()
