from distutils.core import setup

setup(
    name='pyphotofs',
    packages=['pyphotofs'],  # this must be the same as the name above
    version='0.1',
    description='Mounts iPhoto libraries using FUSE',
    author='Robert Harder',
    author_email='rob@iharder.net',
    url='https://github.com/rharder/pyphotofs',  # use the URL to the github repo
    download_url='https://github.com/peterldowns/mypackage/tarball/0.1',  # I'll explain this in a second
    keywords=['iphoto', 'pictures', 'album', 'fuse'],  # arbitrary keywords
    classifiers=[],
)
