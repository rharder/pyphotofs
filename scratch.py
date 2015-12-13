#!/usr/bin/env python

from __future__ import print_function

import atexit
import traceback

import sys
from platform import system

import shutil

from fuse import FUSE

from iphoto import *
from iphotofuse import *

def main():
    lib_path = "/Users/rob/Pictures/iPhoto Library.photolibrary"
    ipl = iPhotoLibrary(lib_path)
    print(ipl)
    for a in ipl.albums:
        print('\t', a)
        for img in a.images:
            print('\t\t', img)
            pass

    for r in ipl.rolls:
        print('\t', r)
        for img in r.images:
            print('\t\t', img)
            pass

    argv = [sys.argv[0], lib_path, '-./mount']
    mount(argv, foreground=True)
    # with open('./mount/iPhoto Library/Albums/Photos/lion square.png') as f:
    #     data = f.read()
    # print(len(data))


def strip_end(text, suffix):
    if not text.endswith(suffix):
        return text
    return text[:len(text) - len(suffix)]


def remove_mount(mount):
    try:
        shutil.rmtree(mount)
    except OSError, e:
        print(e)
        traceback.print_exc(file=sys.stderr)


def mount(argv, foreground=False):

    if len(argv) < 2:
        print('usage: %s iphotolibrary [mountpoint]' % argv[0])
        print("""
            If mountpoint is not specified or a dash -, a mount point will be made
            at the host system's default location (or best guess)
            such as /Volumes on a Mac or /media on most other systems.

            If mountpoint begins with a dash, then a mount point will be created
            automatically within the folder specified after the dash, eg,
            mount_iphotofs ~/Pictures/iPhotoLibrary.photolibrary -.
        """)
        exit(1)

    # libraryPath = '/Users/rob/Pictures/iPhoto Libraries/2014-2018 Colorado.photolibrary'


    # If dash (-) is passed as mountpoint or mountpoint is not
    # specified then it will make a mount point based on the
    # name of the iPhoto library.
    libraryPath = argv[1]
    if len(argv) > 2:
        mount = argv[2]
    else:
        mount = None

    if libraryPath.endswith('/'):
        libraryPath = libraryPath[:-1]
    base = strip_end(os.path.basename(libraryPath), '.photolibrary')

    if system() == 'Darwin':
        preferredMountLocation = '/Volumes'
    elif system() == 'Linux':
        preferredMountLocation = '/media'
    elif system() == 'FreeBSD':
        preferredMountLocation = '/mnt'
    else:
        preferredMountLocation = '/media'

    # Use the default location like /Volumes
    # and make the mount folder to be the library name
    if mount is None or mount == '-':
        mount = os.path.join(preferredMountLocation, base)
        try:
            os.makedirs(mount)
        except OSError:
            if not os.path.isdir(mount):
                raise
        # print(mount, os.listdir(mount))
        # Be sure to remove the mount point we just created
        # and remember that the current directory gets changed
        # so we want to register the absolute path
        atexit.register(remove_mount, os.path.abspath(mount))

    # Make the mount location the library name but
    # put it in the location designated
    elif mount.startswith('-'):
        mount = os.path.join(mount[1:], base)
        try:
            os.makedirs(mount)
        except OSError:
            if not os.path.isdir(mount):
                raise
        # Be sure to remove the mount point we just created
        # and remember that the current directory gets changed
        # so we want to register the absolute path
        atexit.register(remove_mount, os.path.abspath(mount))

    try:
        # fuse = FUSE(iPhoto_FUSE_FS(iPhotoLibrary(libraryPath)), mount, ro=True)
        fuse = FUSE(iPhoto_FUSE_FS(iPhotoLibrary(os.path.abspath(libraryPath)), verbose=False),
                    mount, nothreads=True, foreground=foreground, ro=True, allow_other=True)
    except Exception, e:
        print(e)
        traceback.print_exc(file=sys.stderr)
        exit(1)



if __name__ == "__main__":
    main()