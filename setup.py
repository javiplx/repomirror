#!/usr/bin/python

from distutils.core import setup

setup(
    name = 'repomirror',
    version = '1.5',
    description = 'Generic repository mirroring tool',
    author = 'Javier Palacios',
    author_email = 'javiplx@gmail.com',
    license = 'GPLv2',
    url = 'http://github.com/javiplx/repomirror',
    download_url = 'http://r26936.ovh.net/repomirror',
    scripts = [ 'repomirror' , 'get_filters' , 'buildrepo' , 'checkmirror' , 'buildlive' ],
    data_files = [
                 ( 'share/repomirror' , [ 'repomirror.conf' , 'buildrepo.conf' ] ) ,
                 ( 'share/repomgr/templates' , [ 'repomgr/templates/index.html' , 'repomgr/templates/detail.html' ] ) ,
                 ( 'share/repocache' , [ 'repocache/repocache.conf' , 'repocache/debcache.conf' ] ) ,
                 ( 'share/repomgr' , [ 'repomgr/repomgr.conf' ] )
                 ],
    packages = [ 'repolib' , 'repolib.lists' , 'repomgr' , 'repocache' ],
    py_modules = [ 'filelist_xmlparser' , 'debtarfile' ]
    )

