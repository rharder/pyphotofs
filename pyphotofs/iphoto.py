"""
Some classes for working with iPhoto libraries.

Should work with Python 2.7 and 3.0+
"""

import datetime
import math
import os
import plistlib

__author__ = "Robert Harder"
__email__ = "rob@iharder.net"
__copyright__ = "This code is released into the Public Domain"
__version__ = "0.1"
__status__ = "Development"


class Cache(object):
    """
    Used internally to cache filesystem data to avoid constantly re-reading of AlbumData.xml.
    """

    def __init__(self, mtime_file=None, cache_timeout_seconds=1, verbose=False):
        # self._time_until_flush = datetime.timedelta(seconds=cache_timeout_seconds)
        self.verbose = verbose
        self._cache = {}
        self._time_until_flush_check = datetime.timedelta(
            seconds=cache_timeout_seconds)  # In busy times, don't bother checking mtime
        self._mtime_file = mtime_file  # File who's modification time will determine cache staleness
        if mtime_file:
            self._last_mtime = os.stat(self._mtime_file).st_mtime  # Previously-known mtime
        self._last_access = datetime.datetime.utcnow()  # Last time we accessed the cache

    def __str__(self):
        return "[Cache based on {}]".format(self._mtime_file)

    def _test_for_flush(self):
        """
        Checks to see if cache should be flushed based on either a change in an underlying file
        or if enough time has passed.
        """
        now = datetime.datetime.utcnow()
        if now - self._last_access > self._time_until_flush_check:  # Have we had a delay since the last access
            if self._mtime_file is None:
                self._cache = {}
                if self.verbose:
                    print("cache flushed", str(self))
            elif os.stat(self._mtime_file).st_mtime > self._last_mtime:
                self._cache = {}  # Cache flushed
                if self.verbose:
                    print("cache flushed", str(self))
        self._last_access = now

    def get(self, domain, key=None, default=None):
        self._test_for_flush()

        # If key is None, that means we're getting an item
        # directly from the cache as opposed to a dictionary
        # in the cache as is often the case.
        if domain in self._cache:
            if key is None:
                if self.verbose:
                    print("cache hit domain={}, key={}".format(domain, key), str(self))
                return self._cache[domain]
            else:  # Cache miss
                if key in self._cache[domain]:
                    if self.verbose:
                        print("cache hit domain={}, key={}".format(domain, key), str(self))
                    return self._cache[domain][key]
                else:
                    if self.verbose:
                        print("cache miss domain={}, key={}".format(domain, key), str(self))
                    return default.__call__() if callable(default) else default
        else:
            if self.verbose:
                print("cache miss domain={}, key={}".format(domain, key), str(self))
            return default.__call__() if callable(default) else default

    def set(self, domain, key, value=None):
        """
        Sets a value in the cache.
        :param key:
        :param domain:
        :param value:
        """

        self._test_for_flush()

        if self.verbose:
            print("cache set domain={}, key={}, value={}".format(domain, key, value), str(self))

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

    # Cache Keys
    _ck_imageFromId = '_ck_imageFromId'
    _ck_imageFromGuid = '_ck_imageFromGuid'
    _ck_collectionsByType = '_ck_collectionsByType'
    _ck_collectionByTypeName = '_ck_collectionByTypeName'
    _ck_collectionNamesByType = '_ck_collectionNamesByType'
    _ck_numCollectionsByType = '_ck_numCollectionsByType'
    _ck_childCaches = '_ck_childCaches'
    _ck_masterImageList = '_ck_masterImageList'

    def __init__(self, library_path, verbose=False):

        # self._albumDataStMTime = None
        self._libraryPath = os.path.normpath(library_path)
        self._album_data_xml = os.path.join(self._libraryPath, 'AlbumData.xml')
        self._plist = plistlib.readPlist(self._album_data_xml)
        self._cache = Cache(mtime_file=self._album_data_xml, verbose=verbose)
        self.verbose = verbose

    def __str__(self):
        return "[iPhoto Library '{}']".format(self.name)

    @property
    def cache(self):
        return self._cache

    @property
    def name(self):
        print(self._libraryPath)
        print(os.path.basename(self._libraryPath))
        print(os.path.splitext(os.path.basename(self._libraryPath)))
        base, _ = os.path.splitext(os.path.basename(self._libraryPath))
        return base

    @property
    def path(self):
        """Returns the path (relative or absolute) to the .iphotolibrary library that was
        originally provided when instantiating the class.
        :return: the originally-provided path to the library
        :rtype: str
        """
        return self._libraryPath

    @property
    def abspath(self):
        """Returns the absolute path to the .iphotolibrary library.
        :return: the absolute path to the library
        :rtype: str
        """
        return os.path.abspath(self._libraryPath)

    ###

    def collections(self, c_type):
        """
        Returns a list of collections within this iPhoto Library.  Typically there will be,
        at a minimum, collections named Photos, Flagged, Last 12 Months, and Last Import.
        The parameter type should be either 'Albums' or 'Rolls' to indicate the kind
        of collections to return.
        :param str c_type:
        :return: the collection
        :rtype: [iPhotoCollection]
        """
        coll_list = self._cache.get(self._ck_collectionsByType, c_type)
        if coll_list is not None:
            return coll_list
        else:
            if c_type == 'Albums':
                coll_list = [iPhotoAlbum(plist, self) for plist in self._plist.get('List of ' + c_type, [])]
            elif c_type == 'Rolls':
                coll_list = [iPhotoRoll(plist, self) for plist in self._plist.get('List of ' + c_type, [])]
            else:
                coll_list = {}
            return self._cache.set(self._ck_collectionsByType, c_type, coll_list)

    @property
    def albums(self):
        """
        Returns a list of albums.
        :return: list of albums
        :rtype: [iPhotoAlbum]
        """
        return self.collections('Albums')

    @property
    def rolls(self):
        """
        Returns a list of rolls.
        :return: list of rolls
        :rtype: [iPhotoRoll]
        """
        return self.collections('Rolls')

    ###

    def collection(self, c_type, name):
        """
        Returns a collection of type 'Album' or 'Roll' with the given name
        :param str c_type: the type of collection ('Album' or 'Roll')
        :param str name: the name of the collection
        :return: the collection
        :rtype: iPhotoCollection
        """
        key = c_type + '::' + name
        coll = self._cache.get(self._ck_collectionByTypeName, key)
        if coll is not None:
            return coll
        else:
            for c in self.collections(c_type):
                if c.name == name:
                    return self._cache.set(self._ck_collectionByTypeName, key, c)

    def album(self, name):
        """
        Returns an album with the given name.
        Equivalent to collection('Album', name).
        :param str name: the name of the album
        :return: the album
        :rtype: iPhotoAlbum
        """
        return self.collection('Albums', name)

    def roll(self, name):
        """
        Returns a roll with the given name.
        Equivalent to collection('Roll', name).
        :param str name: the name of the roll
        :return: the roll
        :rtype: iPhotoRoll
        """
        return self.collection('Rolls', name)

    ###

    def collection_names(self, c_type):
        """
        The names of all the collections of the given type in the library.
        The type can be 'Album' or 'Roll'.
        :param str c_type: the type of collection
        :return: list of collection names
        :rtype: [str]
        """
        names = self._cache.get(self._ck_collectionNamesByType, c_type)
        if names is not None:
            return names
        else:
            names = [c.name for c in self.collections(c_type)]
            return self._cache.set(self._ck_collectionNamesByType, c_type, names)

    @property
    def album_names(self):
        """
        The names of all the albums in the library.
        Equivalent to collection_names('Album').
        :return: list of album names
        :rtype: [str]
        """
        return self.collection_names('Albums')

    @property
    def roll_names(self):
        """
        The names of all the rolls in the library.
        Equivalent to collection_names('Roll').
        :return: list of roll names
        :rtype: [str]
        """
        return self.collection_names('Rolls')

    ###

    def num_collections(self, c_type):
        """
        The number of collections of the given type.
        The type can be 'Album' or 'Roll'.
        :param str c_type: the type of collection
        :return: number of collections
        :rtype: int
        """
        num = self._cache.get(self._ck_numCollectionsByType, c_type)
        if num is not None:
            return num
        else:
            if 'List of ' + c_type in self._plist:
                num = len(self._plist.get('List of ' + c_type, []))
            else:
                num = 0
            return self._cache.set(self._ck_numCollectionsByType, c_type, num)

    @property
    def num_albums(self):
        """
        The number of albums.
        Equivalent to num_collections('Albums')
        :return: number of albums
        :rtype: int
        """
        return self.num_collections('Albums')

    @property
    def num_rolls(self):
        """
        The number of rolls.
        Equivalent to num_collections('Rolls')
        :return: number of rolls
        :rtype: int
        """
        return self.num_collections('Rolls')

    ###

    def image_from_id(self, img_id):
        """
        Returns an iPhotoImage object based on the ID of the image.
        :param str img_id: The unique ID of the image, which is used internally within the .iphotolibrary
        :return: an iPhotoImage object
        :rtype: iPhotoImage
        """
        img = self._cache.get(self._ck_imageFromId, img_id)
        if img is not None:
            return img
        else:
            img_plist = self._plist.get('Master Image List', {}).get(img_id)
            if img_plist is None:
                img = None
            else:
                img = iPhotoImage(img_plist, self)
            return self._cache.set(self._ck_imageFromId, img_id, img)

    def image_from_guid(self, guid):
        img = self._cache.get(self._ck_imageFromGuid, id)
        if img is not None:
            return img
        else:
            mil = self._plist.get('Master Image List', {})
            for _, img_plist in mil.items():
                if img_plist.get('GUID') == guid:
                    img = iPhotoImage(img_plist, self)
                    return self._cache.set(self._ck_imageFromGuid, id, img)

    @property
    def images(self):
        """
        Returns a list of all images within this library.
        :return: list of iPhotoImage objects
        :rtype: [iPhotoImage]
        """
        images = self._cache.get(self._ck_masterImageList)
        if images is not None:
            return images
        else:
            images = [self.image_from_id(img_id) for img_id in self._plist.get('Master Image List', {})]
            return self._cache.set(self._ck_masterImageList, images)

    @property
    def num_images(self):
        """
        Returns the number of images within this library.
        :return: number of images
        :rtype: int
        """
        return len(self._plist.get('Master Image List', []))


class iPhotoCollection(object):
    """Not meant to be instantiated, only inherited"""

    _ck_collectionImagesByTypeName = '_ck_collectionImagesByTypeName'
    _ck_imageByTypeNameFilename = '_ck_imageByTypeNameFilename'

    def __init__(self, albumPlist, parentLib, nameKey):
        self._parentLibrary = parentLib
        self._plist = albumPlist
        self._nameKey = nameKey

    def __str__(self):
        name_key = self._nameKey.replace('Name', '')
        return "[iPhoto {} '{}', images={}]".format(name_key, self.name, self.num_images)

    @property
    def cache(self):
        return self._parentLibrary.cache

    # def _cache(self):
    #     return self._parentLibrary._cache.get(self._parentLibrary._ck_childCaches, self, lambda: Cache())

    @property
    def name(self):
        """
        Returns the name of the album, roll, etc
        :return: name
        """
        return self._plist[self._nameKey]

    @property
    def images(self):
        """
        Returns a list of all images (as iPhotoImage objects) within the collection.
        :return: a list of images
        :rtype: [iPhotoImage]
        """
        cache = self.cache
        key = self._nameKey + '::' + self.name
        img_list = cache.get(self._ck_collectionImagesByTypeName, key)
        if img_list is not None:
            return img_list
        else:
            img_list = [self._parentLibrary.image_from_id(img_id) for img_id in self._plist.get('KeyList', [])]
            return cache.set(self._ck_collectionImagesByTypeName, key, img_list)

    def image_by_filename(self, filename):
        """
        Returns the image (as an iPhotoImage object) with the given filename
        within this collection.
        :param filename: The filename of the image
        :return: The image with the matching filename
        :rypte: iPhotoImage
        """
        cache = self.cache
        key = self._nameKey + '::' + self.name + '::' + filename
        image = cache.get(self._ck_imageByTypeNameFilename, key)
        if image is not None:
            return image
        else:
            for img_id in self._plist.get('KeyList', []):
                image = self._parentLibrary.image_from_id(img_id)
                if image is not None and image.filename == filename:
                    return cache.set(self._ck_imageByTypeNameFilename, key, image)

    @property
    def num_images(self):
        """
        Returns the number of images in the collection.
        :return: number of images
        :rtype: int
        """
        return len(self._plist.get('KeyList', []))  # Not bothering to cache


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

    def __str__(self):
        return "[iPhoto Image '{}', size={}]".format(self.filename, human_size(self.size))

    def _rel_internal_path(self):
        """Returns a path relative to the .iphotoLibrary folder
        For instance if the iPhoto library path is
        /Users/rob/Pictures/iPhoto Library.photolibrary, and
        relpath() returned the value
        Masters/2014/07/07/20140707-235350/IMG_5348.JPG
        then the actual file on disk could be found at
        /Volumes/iPhoto Libraries/2014-2018 Colorado.photolibrary/Masters/2014/07/07/20140707-235350/IMG_5348.JPG
        """
        absImgPath = self._plist.get('ImagePath')
        libName = os.path.basename(self._parentLibrary.abspath)
        return self._rel_internal_path_rel_path_recursive_helper(absImgPath, libName)

    def _rel_internal_path_rel_path_recursive_helper(self, path, targetFolder):
        leadingEl, lastEl = os.path.split(path)
        if lastEl == targetFolder:  # Found it!
            return ''
        else:
            return os.path.join(self._rel_internal_path_rel_path_recursive_helper(leadingEl, targetFolder), lastEl)

    @property
    def declared_image_path(self):
        """Return the image path identified by iPhoto.
        This is generally an absolute path hard coded
        to where the photo library is stored the last
        time iPhoto opened it.  If you are mounting
        an iPhoto library over the network or mounting
        a backup of the library, this will almost certainly
        not be what you are looking for.  The abspath()
        function is probably more appropriate.
        """
        return self._plist.get('ImagePath')

    @property
    def abspath(self):
        return os.path.join(self._parentLibrary.abspath, self._rel_internal_path())

    @property
    def thumbpath(self):
        # TODO: This needs to adapt just as the image path is hard coded in AlbumData.xml
        return self._plist.get('ThumbPath')

    @property
    def caption(self):
        """Return the photo's caption"""
        return self._plist.get('Caption')

    @property
    def filename(self):
        """Returns the original filename of the image, eg, IMG_4358.JPG"""
        return os.path.basename(self.declared_image_path)

    @property
    def type(self):
        """Returns the MediaType tag from iPhoto, eg, Image."""
        return self._plist.get('MediaType')

    @property
    def guid(self):
        return self._plist.get('GUID')

    @property
    def size(self):
        return os.path.getsize(self.abspath)


def human_size(nbytes):
    suffixes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
    rank = int((math.log10(nbytes)) / 3)
    rank = min(rank, len(suffixes) - 1)
    human = nbytes / (1024.0 ** rank)
    f = ('%.1f' % human).rstrip('0').rstrip('.')
    return '%s %s' % (f, suffixes[rank])
