#!/usr/bin/env python
# Should work with Python 2 or 3
"""
Mounts an iPhoto library as a filesystem.
"""
from __future__ import print_function

from .iphotofuse import *

__author__ = "Robert Harder"
__email__ = "rob@iharder.net"
__copyright__ = "This code is released into the Public Domain"
__version__ = "0.1"
__status__ = "Development"


def main():
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
