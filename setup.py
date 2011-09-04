#!/usr/bin/python

from distutils.core import setup

setup(
    name = 'repomirror',
    version = '2.0',
    description = 'Generic repository mirroring tool',
    author = 'Javier Palacios',
    author_email = 'javiplx@gmail.com',
    license = 'GPLv2',
    url = 'http://github.com/javiplx/repomirror',
    download_url = 'http://r26936.ovh.net/repomirror',
    scripts = [ 'repomirror' , 'reposnapshot' , 'buildrepo' , 'buildlive' , 'checkmirror' ],
    packages = [ 'repolib' , 'repolib.lists' , 'repomgr' , 'repocache' ],
    data_files = [
                 ( 'share/repomirror' , [ 'docs/samples/repomirror.conf' , 'docs/samples/buildrepo.conf' ] ) ,
                 ( 'share/repomgr/templates' , [ 'repomgr/templates/index.html' , 'repomgr/templates/detail.html' ] ) ,
                 ( 'share/repocache' , [ 'repocache/repocache.conf' , 'repocache/debcache.conf' ] ) ,
                 ( 'share/repomgr' , [ 'repomgr/repomgr.conf' ] )
                 ]
    )

