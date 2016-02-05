#!/usr/bin/env python

from __future__ import print_function

from pyphotofs.iphotofuse import *


def main():
    lib_path = "/Users/rob/Pictures/iPhoto Library.photolibrary"
    # lib_path = "c:\\temp\\2007 Levi and Keatra Wedding"
    plain_lib = iPhotoLibrary(lib_path, verbose=False)

    for ipl in [plain_lib]:
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
    mount_iphotofs(argv, foreground=True)
    # with open('./mount/iPhoto Library/Albums/Photos/lion square.png') as f:
    #     data = f.read()
    # print(len(data))


if __name__ == "__main__":
    main()
