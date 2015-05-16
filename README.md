# pyphotofs: iPhoto File System with FUSE and Python

This tool mounts an iPhoto library as a filesystem with Albums and Rolls as folders within.

## Example Usage

mount_iphotofs.py ~/Pictures/iPhoto\ Library.photolibrary

## Requirements

This tool relies on *plistlib* to read the AlbumData.xml file within
the iPhoto library folder, *fusepy* to interface with FUSE, and
some host-supported implementation of *FUSE* itself.

Required software:
 - FUSE
   -- Mac: http://osxfuse.github.io
   -- GNU/Linux: http://fuse.sourceforge.net
   -- FreeBSD: Built-in
 - fusepy 
   -- https://github.com/terencehonles/fusepy
   -- sudo pip install fusepy
 - plistlib
   -- https://docs.python.org/2/library/plistlib.html
   -- sudo pip install plistlib
 
## To Do

I like the idea of having a Faces folder with a sub folder for each face known
to iPhoto.  This would involve some sqlite scripting, which I do not think requires
any extra dependencies in Python.  Perhaps I will get around to adding this feature
in the future.
 
 
## Caveats

This is just something I threw together over a few days to serve my own purposes, but if
it is of use to anyone else, please enjoy it.  I do not know where the code is broken or
under what conditions something will break.  I *do* know that I mount the filesystem 
read-only, so that should reduce the possibility of totally destroying your iPhoto library.

## Other Uses

This tool consists of a few classes to help read iPhoto libraries.  These classes may
be of use outside of the purpose of mounting the library as a filesystem.  Feel free
to extract these classes and use them in your own product.

## Credits

Created by Robert Harder, rob iharder.net, and released into the Public Domain.
