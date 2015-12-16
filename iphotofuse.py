#!/usr/bin/env python
import atexit
import time
import traceback
from errno import ENOENT
from platform import system
from stat import S_IFDIR
from threading import Lock

import shutil

import sys
from fuse import FuseOSError, Operations, LoggingMixIn, fuse_get_context, FUSE

from iphoto import *


class iPhoto_FUSE_FS(LoggingMixIn, Operations):
    _ck_st_by_path = '_ck_st_by_path'
    _ck_collection_by_name = '_ck_collection_by_name'
    _ck_collection_by_path = '_ck_collection_by_path'
    _ck_folder_listing = '_ck_folder_listing'
    _ck_image_by_path = '_ck_image_by_path'

    _CHMOD = 755

    chmod = os.chmod
    chown = os.chown
    readlink = os.readlink

    # Disable unused operations:
    getxattr = None
    listxattr = None
    opendir = None
    releasedir = None

    def __init__(self, iphoto_lib, verbose=False):
        self._library = iphoto_lib
        """:type: iphoto.iPhotoLibrary"""
        self.rwlock = Lock()
        self.verbose = verbose

    @property
    def cache(self):
        return self._library.cache

    @property
    def library(self):
        """
        Returns the corresponding iPhotoLibrary
        :return: the iPhoto library
        :rtype: iPhotoLibrary
        """
        return self._library

    def add_uid_gid_pid(self, stDict):
        uid, gid, pid = fuse_get_context()
        stDict['st_uid'] = uid
        stDict['st_gid'] = gid
        stDict['st_pid'] = pid
        return stDict

    def open(self, path, flags=0, mode=0):
        if self.verbose:
            print("open: {} (flags={}, mode={}".format(path, flags, mode))

        self.getattr(path)  # Loads info about image to cache
        image = self.cache.get(self._ck_image_by_path, path)
        """:type: iphoto.iPhotoImage"""
        if image is not None:
            return os.open(image.abspath, flags, mode)
        else:
            return None

    def read(self, path, size, offset, fh):
        # If we've already enumerated the enclosing folder, then
        # we have all the data we need to read it.
        # If someone tries to read a file without having first
        # enumerated the folder (such as a file with a fixed,
        # known location), then we need to get some info first.

        if self.verbose:
            print("read: {} (size={}, offset={}".format(path, size, offset))

        image = self.cache.get(self._ck_image_by_path, path)
        """:type: iphoto.iPhotoImage"""
        #        if self._ck_image_by_path in self._cache and path in self._cache[self._ck_image_by_path]:
        if image is not None:
            with self.rwlock:
                os.lseek(fh, offset, 0)
                return os.read(fh, size)
        raise RuntimeError('unexpected path: %r' % path)

    def getattr(self, path, fh=None):
        if self.verbose:
            print("getattr: {}".format(path))

        cache = self.cache
        """:type: iphoto.Cache"""

        st = cache.get(self._ck_st_by_path, path)
        if st is not None:
            return st
        else:

            if path == '/':  # If cache is cleared, '/' stat needs to be specified
                st = dict(st_mode=(S_IFDIR | iPhoto_FUSE_FS._CHMOD), st_nlink=4)  # 4 = . .. Albums Rolls
                return cache.set(self._ck_st_by_path, path, st)

            elif path == '/Albums' or path == '/Rolls':
                nlink = 2 + self._library.num_collections(path[1:])  # And remove leading slash
                now = time.mktime(datetime.datetime.now().timetuple())
                st = self.add_uid_gid_pid(dict(
                    st_mode=(S_IFDIR | iPhoto_FUSE_FS._CHMOD), st_nlink=nlink,
                    st_ctime=now, st_atime=now, st_mtime=now))
                return cache.set(self._ck_st_by_path, path, st)

            elif path.startswith('/Albums/') or path.startswith('/Rolls/'):
                leadingEls, tail = os.path.split(path)  # eg, /Albums and CampingTrip

                # Asking about an album or roll
                if leadingEls == '/Albums' or leadingEls == '/Rolls':  # Asking us about specific album or roll
                    collName = tail
                    if leadingEls == '/Albums':
                        collection = self._library.album(collName)
                    elif leadingEls == '/Rolls':
                        collection = self._library.roll(collName)
                    else:
                        collection = None
                    if collection is not None:
                        nlink = 2 + collection.num_images
                        now = time.mktime(datetime.datetime.now().timetuple())
                        st = self.add_uid_gid_pid(dict(
                            st_mode=(S_IFDIR | iPhoto_FUSE_FS._CHMOD), st_nlink=nlink,
                            st_ctime=now, st_atime=now, st_mtime=now))
                        return cache.set(self._ck_st_by_path, path, st)

                # Asking about an image
                else:
                    imgName = tail
                    collType, collName = os.path.split(leadingEls)
                    image = None
                    """:type: iphoto.iPhotoImage"""

                    if collType == '/Albums':
                        image = self._library.album(collName).image_by_filename(imgName)
                        """:type: iphoto.iPhotoImage"""

                    elif collType == '/Rolls':
                        image = self._library.roll(collName).image_by_filename(imgName)
                        """:type: iphoto.iPhotoImage"""

                    if image is not None:
                        st = os.lstat(image.abspath)
                        st = self.add_uid_gid_pid(
                            dict((key, getattr(st, key)) for key in
                                 ('st_atime', 'st_ctime', 'st_mode', 'st_mtime', 'st_nlink', 'st_size')))
                        cache.set(self._ck_image_by_path, path, image)
                        return cache.set(self._ck_st_by_path, path, st)

        # In theory, we should never be here except by some error
        raise FuseOSError(ENOENT)

    def readdir(self, path, fh=None):
        default = ['.', '..']
        cache = self.cache

        if self.verbose:
            print("readdir: {}".format(path))

        # Quick cache return
        listing = cache.get(self._ck_folder_listing, path)
        if listing is not None:
            return listing

        else:
            if path == '/':
                return cache.set(self._ck_folder_listing, path, default + ['Albums', 'Rolls'])

            elif path == '/Albums':
                return cache.set(self._ck_folder_listing, path, default + self._library.album_names)

            elif path == '/Rolls':
                return cache.set(self._ck_folder_listing, path, default + self._library.roll_names)


            # Ought to be listing albums or rolls, nothing else
            # (except meta data that the OS might be querying
            elif path.startswith('/Albums/') or path.startswith('/Rolls/'):
                leadingEls, collName = os.path.split(path)  # eg, /Albums and CampingTrip

                # Based on result of split we can assume something about leadingEls
                if leadingEls == '/Albums':
                    collection = self._library.album(collName)
                elif leadingEls == '/Rolls':
                    collection = self._library.roll(collName)
                else:
                    collection = None

                if collection is not None:
                    return cache.set(self._ck_folder_listing, path, default + \
                                     [i.filename for i in collection.images])

        return []

    def flush(self, path, fh):
        if self.verbose:
            print("flush: {}".format(path))
        return os.fsync(fh)

    def fsync(self, path, datasync, fh):
        if self.verbose:
            print("fsync: {} (datasync={})".format(path, datasync))
        return os.fsync(fh)

    def release(self, path, fh):
        if self.verbose:
            print("release: {}".format(path))
        return os.close(fh)




def mount_iphotofs(library, mount=None, foreground=False):
    """

    :param iphoto.iPhotoLibrary library:
    :param str mount:
    :return: None
    """

    def remove_mount(mount):
        """
        Used with atexit to remove mount point after FUSE is done with it.
        :param str mount: the mount point
        :return: None
        """
        try:
            shutil.rmtree(mount)
        except OSError:
            traceback.print_exc(file=sys.stderr)


    this_system = system()
    if this_system == 'Darwin':
        preferredMountLocation = '/Volumes'
    elif this_system == 'Linux':
        preferredMountLocation = '/media'
    elif this_system == 'FreeBSD':
        preferredMountLocation = '/mnt'
    else:
        preferredMountLocation = '/media'

    # If dash (-) is passed as mountpoint or mountpoint is not
    # specified then it will make a mount point based on the
    # name of the iPhoto library.


    # Use the default location like /Volumes
    # and make the mount folder to be the library name
    if mount is None or mount == '-':
        mount = os.path.join(preferredMountLocation, library.name)
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
        mount = os.path.join(mount[1:], library.name)
        try:
            os.makedirs(mount)
        except OSError:
            if not os.path.isdir(mount):
                raise
        # Be sure to remove the mount point we just created
        # and remember that the current directory gets changed
        # so we want to register the absolute path
        atexit.register(remove_mount, os.path.abspath(mount))


    # try:
    print("Library", str(library))
    print("Library name", library.name)
    print("Mounting to", mount)
    fuse = FUSE(
                iPhoto_FUSE_FS(library),
                mount,
                nothreads=False,
                foreground=foreground,
                ro=True,
                allow_other=True,
                fsname=library.name,
                volname=library.name
                )
    return fuse
    # except Exception:
    #     traceback.print_exc(file=sys.stderr)
    #     exit(1)


