#!/usr/bin/env python

"""
Mounts an iPhoto library as a filesystem.
"""

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


__author__ = "Robert Harder"
__email__ = "rob@iharder.net"
__copyright__ = "This code is released into the Public Domain"
__version__ = "0.1"
__status__ = "Development"


class Cache(object):
    _cache = {}
    _last_access = datetime.datetime.utcnow()
    _time_until_flush = datetime.timedelta(minutes=1)


    def __init__(self, cache_timeout_seconds=60):
        self._time_until_flush = datetime.timedelta(seconds=cache_timeout_seconds)


    def _test_for_flush(self):
        now = datetime.datetime.utcnow()
        if now - self._last_access > self._time_until_flush:
            _cache = {}  # Cache flushed
        self._last_access = now


    def get(self, domain, key=None, default=None):
        self._test_for_flush()

        # If key is None, that means we're getting an item
        # directly from the cache as opposed to a dictionary
        # in the cache as is often the case.
        if domain in self._cache:
            if key is None:
                return self._cache[domain]
            else:  # Cache miss
                if key in self._cache[domain]:
                    return self._cache[domain][key]
                else:
                    return default.__call__() if callable(default) else default
        else:
            return default.__call__() if callable(default) else default

    def set(self, domain, key, value=None):
        """
        Sets a value in the cache.
        """

        self._test_for_flush()

        # If value is None, that means we're setting an item
        # directly in the cache as opposed to a dictionary
        # in the cache as is often the case
        if value is None:
            self._cache[domain] = key
            return key
        else:
            if domain not in self._cache:
                self._cache[domain] = {}
            self._cache[domain][key] = value
            return value



class iPhotoLibrary(object):
    """A Python class for reading iPhoto libraries 'statically' including
    non-active iPhoto libraries.
    Author: Robert Harder
    """

    _plist = None
    _albumDataStMTime = None
    _libraryPath = None
    _cache = Cache()

    _ck_imageFromId = '_ck_imageFromId'
    _ck_collectionsByType = '_ck_collectionsByType'
    _ck_collectionByTypeName = '_ck_collectionByTypeName'
    _ck_collectionNamesByType = '_ck_collectionNamesByType'
    _ck_numCollectionsByType = '_ck_numCollectionsByType'
    _ck_childCaches = '_ck_childCaches'

    def __init__(self, library_path):
        self._plist = None
        self._libraryPath = library_path
        self.flush_cache()

    def flush_cache(self):
        self._plist = plistlib.readPlist(os.path.join(self._libraryPath, 'AlbumData.xml'))
        self._albumDataStMTime = os.stat(self._libraryPath).st_mtime
        self._cache = Cache()


    def path(self):
        """Returns the path (relative or absolute) to the .iphotolibrary library that was
        originally provided when instantiating the class."""
        return self._libraryPath

    def abspath(self):
        """Returns the absolute path to the .iphotolibrary library."""
        return os.path.abspath(self._libraryPath)
###

    def collections(self, type):
        list = self._cache.get(self._ck_collectionsByType, type)
        if list is not None:
            return list
        else:
            if type == 'Albums':
                list = [iPhotoAlbum(plist, self) for plist in self._plist['List of ' + type]]
            elif type == 'Rolls':
                list = [iPhotoRoll(plist, self) for plist in self._plist['List of ' + type]]
            else:
                list = {}
            return self._cache.set(self._ck_collectionsByType, type, list)


    def albums(self):
        return self.collections('Albums')

    def rolls(self):
        return self.collections('Rolls')
###

    def collection(self, type, name):
        key = type + '::' + name
        coll = self._cache.get(self._ck_collectionByTypeName, key)
        if coll is not None:
            return coll
        else:
            for c in self.collections(type):
                if c.name == name:
                    return self._cache.set(self._ck_collectionByTypeName, key, c)

    def album(self, name):
        return self.collection('Albums', name)

    def roll(self, name):
        return self.collection('Rolls', name)
###

    def collection_names(self, type):
        names = self._cache.get(self._ck_collectionNamesByType, type)
        if names is not None:
            return names
        else:
            names = [c.name for c in self.collections(type)]
            return self._cache.set(self._ck_collectionNamesByType, type, names)

    def album_names(self):
        return self.collection_names('Albums')

    def roll_names(self):
        return self.collection_names('Rolls')
###

    def num_collections(self, type):
        num = self._cache.get(self._ck_numCollectionsByType, type)
        if num is not None:
            return num
        else:
            if 'List of ' + type in self._plist:
                num = len(self._plist['List of ' + type])
            else:
                num = 0
            return self._cache.set(self._ck_numCollectionsByType, type, num)

    def num_albums(self):
        return self.num_collections('Albums')

    def num_rolls(self):
        return self.num_collections('Rolls')
###

    def image_from_id(self, id):
        """
        Returns an iPhotoImage object based on the ID of the image.
        :param id: The unique ID of the image, which is used internally within the .iphotolibrary
        :return: an iPhotoImage object
        """
        img = self._cache.get(self._ck_imageFromId, id)
        if img is not None:
            return img
        else:
            imgPlist = self._plist['Master Image List'][id]
            if imgPlist is None:
                img = None
            else:
                img = iPhotoImage(imgPlist, self)
            return self._cache.set(self._ck_imageFromId, id, img)

    def images(self):
        images = self._cache.get(self._ck_masterImageList)
        if images is not None:
            return images
        else:
            images = [self.image_from_id(id) for id in self._plist['Master Image List']]
            return self._cache.set(self._ck_masterImageList, images)




class iPhotoCollection(object):
    """Not meant to be instantiated, only inherited"""

    _parentLibrary = None
    _plist = None
    _nameKey = ''
    _ck_collectionImagesByTypeName = '_ck_collectionImagesByTypeName'
    _ck_imageByTypeNameFilename = '_ck_imageByTypeNameFilename'

    def __init__(self, albumPlist, parentLib, nameKey):
        self._parentLibrary = parentLib
        self._plist = albumPlist
        self._nameKey = nameKey

    def _cache(self):
        return self._parentLibrary._cache.get(self._parentLibrary._ck_childCaches, self, lambda:Cache())

    def name(self):
        """
        Returns the name of the album, roll, etc
        :return: name
        """
        return self._plist[self._nameKey]
    
    def images(self):
        """
        Returns a list of all images (as iPhotoImage objects) within the collection.
        :return: a list of images
        """
        cache = self._cache()
        key = self._nameKey + '::' + self.name
        list = cache.get(self._ck_collectionImagesByTypeName, key)
        if list is not None:
            return list
        else:
            list = [self._parentLibrary.image_from_id(id) for id in self._plist['KeyList']]
            return cache.set(self._ck_collectionImagesByTypeName, key, list)

    def image_by_filename(self, filename):
        """
        Returns the image (as an iPhotoImage object) with the given filename
        within this collection.
        :param filename: The filename of the image
        :return: The image with the matching filename
        """
        cache = self._cache()
        key = self._nameKey + '::' + self.name + '::' + filename
        image = cache.get(self._ck_imageByTypeNameFilename, key)
        if image is not None:
            return image
        else:
            for id in self._plist['KeyList']:
                image = self._parentLibrary.image_from_id(id)
                if image is not None and image.filename() == filename:
                    return cache.set(self._ck_imageByTypeNameFilename, key, image)

    def num_images(self):
        """Returns the number of images in the collection."""
        return len(self._plist['KeyList'])  # Not bothering to cache



class iPhotoAlbum(iPhotoCollection):
    def __init__(self, albumPlist, parentLib):
        super(iPhotoAlbum, self).__init__(albumPlist, parentLib, 'AlbumName')


class iPhotoRoll(iPhotoCollection):
    def __init__(self, albumPlist, parentLib):
        super(iPhotoRoll, self).__init__(albumPlist, parentLib, 'RollName')



class iPhotoImage:

    _parentLibrary = None
    _plist = None


    def __init__(self, photoPlist, parentLib):
        self._parentLibrary = parentLib
        self._plist = photoPlist

    def declared_image_path(self):
        """Return the image path identified by iPhoto.
        This is generally an absolute path hard coded
        to where the photo library is stored the last
        time iPhoto opened it.  If you are mounting
        an iPhoto library over the network or mounting
        a backup of the library, this will almost certainly
        not be what you are looking for.  The relpath()
        and abspath() methods are probably more appropriate.
        """
        return self._plist['ImagePath']
    
    def _rel_internal_path(self):
        """Returns a path relative to the .iphotoLibrary folder
        For instance if the iPhoto library path is
        /Users/rob/Pictures/iPhoto Library.photolibrary, and
        relpath() returned the value
        Masters/2014/07/07/20140707-235350/IMG_5348.JPG
        then the actual file on disk could be found at
        /Volumes/iPhoto Libraries/2014-2018 Colorado.photolibrary/Masters/2014/07/07/20140707-235350/IMG_5348.JPG
        """
        absImgPath = self._plist['ImagePath']
        libName = os.path.basename(self._parentLibrary.abspath())
        return self._rel_internal_path_rel_path_recursive_helper(absImgPath, libName)
    
    def _rel_internal_path_rel_path_recursive_helper(self, path, targetFolder):
        leadingEl, lastEl = os.path.split(path)
        if lastEl == targetFolder: # Found it!
            return ''
        else:
            return os.path.join(self._rel_internal_path_rel_path_recursive_helper(leadingEl,targetFolder), lastEl)
    
    def abspath(self):
        return os.path.join(self._parentLibrary.abspath(), self._rel_internal_path())

    def thumbpath(self):
        # TODO: This needs to adapt just as the image path is hard coded in AlbumData.xml
        return self._plist['ThumbPath']

    def caption(self):
        """Return the photo's caption"""
        return self._plist['Caption']
    
    def filename(self):
        """Returns the original filename of the image, eg, IMG_4358.JPG"""
        return os.path.basename( self.declared_image_path() )

    def type(self):
        """Returns the MediaType tag from iPhoto, eg, Image."""
        return self._plist['MediaType']
        





class iPhoto_FUSE_FS(LoggingMixIn, Operations):


    _ck_st_by_path = '_ck_st_by_path'
    _ck_collection_by_name = '_ck_collection_by_name'
    _ck_collection_by_path = '_ck_collection_by_path'
    _ck_folder_listing = '_ck_folder_listing'
    _ck_image_by_path = '_ck_image_by_path'
    

    def __init__(self, lib):
        self.library = lib
        self.rwlock = Lock()

    def _cache(self):
        return self.library._cache.get(self.library._ck_childCaches, self, lambda:Cache())

    def add_uid_gid_pid(self, stDict):
        uid, gid, pid = fuse_get_context()
        stDict['st_uid'] = uid
        stDict['st_gid'] = gid
        stDict['st_pid'] = pid
        return stDict



    def open(self, path, flags=0, mode=0):
        image = self._cache().get(self._ck_image_by_path, path)
        if image is not None:
            return os.open(image.abspath(), flags, mode)
        else:
            return None



    def read(self, path, size, offset, fh):
        # If we've already enumerated the enclosing folder, then
        # we have all the data we need to read it.
        # If someone tries to read a file without having first
        # enumerated the folder (such as a file with a fixed,
        # known location), then we need to get some info first.

        # TODO
        image = self._cache().get(self._ck_image_by_path, path)
#        if self._ck_image_by_path in self._cache and path in self._cache[self._ck_image_by_path]:
        if image is not None:
            with self.rwlock:
                os.lseek(fh, offset, 0)
                return os.read(fh, size)
        raise RuntimeError('unexpected path: %r' % path)

    def getattr(self, path, fh=None):
        cache = self._cache()

        st = cache.get(self._ck_st_by_path, path)
        if st is not None:
            return st
        else:

            if path == '/': # If cache is cleared, '/' stat needs to be specified
                st = dict(st_mode=(S_IFDIR | 0755), st_nlink=4)  # 4 = . .. Albums Rolls
                return cache.set(self._ck_st_by_path, path, st)

            elif path == '/Albums' or path == '/Rolls':
                nlink = 2 + self.library.num_collections(path[1:])  # And remove leading slash
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
                        collection = self.library.album(collName)
                    elif leadingEls == '/Rolls':
                        collection = self.library.roll(collName)
                    else:
                        collection = None
                    if collection is not None:
                        nlink = 2 + collection.num_images()
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
                    if collType == '/Albums':
                        image = self.library.album(collName).image_by_filename(imgName)

                    elif collType == '/Rolls':
                        image = self.library.roll(collName).image_by_filename(imgName)

                    if image is not None:
                        st = os.lstat( image.abspath() )
                        st = self.add_uid_gid_pid(
                            dict((key, getattr(st, key)) for key in
                            ('st_atime', 'st_ctime', 'st_mode', 'st_mtime', 'st_nlink', 'st_size')))
                        cache.set(self._ck_image_by_path, path, image)
                        return cache.set(self._ck_st_by_path, path, st)

        # In theory, we should never be here except by some error
        raise FuseOSError(ENOENT)

    def readdir(self, path, fh=None):
        default = ['.', '..']
        cache = self._cache()

        # Quick cache return
        listing = cache.get(self._ck_folder_listing, path)
        if listing is not None:
            return listing

        else:
            if path == '/':
                return cache.set(self._ck_folder_listing, path, default + ['Albums', 'Rolls'])

            elif path == '/Albums':
                return cache.set(self._ck_folder_listing, path, default + self.library.album_names())

            elif path == '/Rolls':
                return cache.set(self._ck_folder_listing, path, default + self.library.roll_names())


            # Ought to be listing albums or rolls, nothing else
            # (except meta data that the OS might be querying
            elif path.startswith('/Albums/') or path.startswith('/Rolls/'):
                leadingEls, collName = os.path.split(path)  # eg, /Albums and CampingTrip

                # Based on result of split we can assume something about leadingEls
                if leadingEls == '/Albums':
                    collection = self.library.album(collName)
                elif leadingEls == '/Rolls':
                    collection = self.library.roll(collName)
                else:
                    collection = None

                if collection is not None:
                    return cache.set(self._ck_folder_listing, path, default + \
                        [i.filename() for i in collection.images()])

        return []



    
    def flush(self, path, fh):
        return os.fsync(fh)
        
    def fsync(self, path, datasync, fh):
        return os.fsync(fh)
    
    def release(self, path, fh):
        return os.close(fh)

    chmod = os.chmod
    chown = os.chown
    readlink = os.readlink
                
    # Disable unused operations:
    getxattr = None
    listxattr = None
    opendir = None
    releasedir = None


def strip_end(text, suffix):
    if not text.endswith(suffix):
        return text
    return text[:len(text)-len(suffix)]



def remove_mount(mount):
    try:
        shutil.rmtree(mount)
    except OSError, e:
        print e


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
        fuse = FUSE(iPhoto_FUSE_FS(iPhotoLibrary(libraryPath)), mount, ro=True)
        #fuse = FUSE(iPhoto_FUSE_FS(iPhotoLibrary(libraryPath)), mount, foreground=True, ro=True)
    except Exception, e:
        print e
        exit(1)
