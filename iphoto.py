#!/usr/bin/env python

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
                if c.name() == name:
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
            names = [c.name() for c in self.collections(type)]
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
        key = self._nameKey + '::' + self.name()
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
        key = self._nameKey + '::' + self.name() + '::' + filename
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
        


