#!/usr/bin/python

from distutils.core import setup

setup(
    name = 'repomirror',
    version = '1.2',
    description = 'Generic repository mirroring tool',
    author = 'Javier Palacios',
    author_email = 'javiplx@gmail.com',
    url = 'http://github.com/javiplx/repomirror',
    scripts = [ 'repomirror.py' , 'get_filters.py' , 'buildrepo.py' ],
    data_files = [
                 ( 'share/repomirror' , [ 'repomirror.conf' ] )
                 ],
    packages = [ 'repolib' ],
    py_modules = [ 'repoutils' , 'filelist_xmlparser' ]
    )

