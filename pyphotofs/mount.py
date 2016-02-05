#!/usr/bin/env python

from iphoto import *
from iphotofuse import iPhoto_FUSE_FS



import os
import atexit, shutil
from threading import Lock
from platform import system
import time
import datetime

from errno import ENOENT
from stat import S_IFDIR
from sys import argv, exit

import plistlib

from fuse import FUSE, FuseOSError, Operations, LoggingMixIn, fuse_get_context

from pyphotofs.iphoto import iPhotoLibrary


def strip_end(text, suffix):
    if not text.endswith(suffix):
        return text
    return text[:len(text)-len(suffix)]



def remove_mount(mount):
    try:
        shutil.rmtree(mount)
    except:
        pass
    # except OSError, e:
    #     print e


if __name__ == '__main__':

    if len(argv) <2:
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

    #libraryPath = '/Users/rob/Pictures/iPhoto Libraries/2014-2018 Colorado.photolibrary'


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
        #fuse = FUSE(iPhoto_FUSE_FS(iPhotoLibrary(libraryPath)), mount, ro=True)
        fuse = FUSE(iPhoto_FUSE_FS(iPhotoLibrary(libraryPath)), mount, foreground=True, ro=True)
    except:#Exception, e:
        # print e
        exit(1)
        
