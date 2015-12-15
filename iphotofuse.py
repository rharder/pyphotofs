#!/usr/bin/env python



import time
from errno import ENOENT
from stat import S_IFDIR
from threading import Lock

from fuse import FuseOSError, Operations, LoggingMixIn, fuse_get_context

from iphoto import *


class iPhoto_FUSE_FS(LoggingMixIn, Operations):
    _ck_st_by_path = '_ck_st_by_path'
    _ck_collection_by_name = '_ck_collection_by_name'
    _ck_collection_by_path = '_ck_collection_by_path'
    _ck_folder_listing = '_ck_folder_listing'
    _ck_image_by_path = '_ck_image_by_path'

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
        """:type: iPhotoLibrary"""
        self.rwlock = Lock()
        self.verbose = verbose

    @property
    def cache(self):
        return self._library.cache
    #
    # def _cache(self):
    #     return self.__library._cache.get(self.__library._ck_childCaches, self, lambda: Cache())

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
                st = dict(st_mode=(S_IFDIR | 0755), st_nlink=4)  # 4 = . .. Albums Rolls
                return cache.set(self._ck_st_by_path, path, st)

            elif path == '/Albums' or path == '/Rolls':
                nlink = 2 + self._library.num_collections(path[1:])  # And remove leading slash
                now = time.mktime(datetime.datetime.now().timetuple())
                st = self.add_uid_gid_pid(dict(
                    st_mode=(S_IFDIR | 0755), st_nlink=nlink,
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
                            st_mode=(S_IFDIR | 0755), st_nlink=nlink,
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
