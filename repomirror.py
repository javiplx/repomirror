#!/usr/bin/python

# FIXME : Allow reading from a sources.list file, parsing into scheme, server, path, codename and components

minor_filters = {}
minor_filters['sections'] = []
minor_filters['priorities'] = []
minor_filters['tags'] = []

params = {}
# mode (update|init) - decides if we stop processing for unchanged metadata files
params['mode'] = "update"

# usegpg. To disable verification of PGP signatures. Forces the download of Release file every run
# FIXME : Add an ignore all verifications? (pgp+md5)
params['usegpg'] = False


# usemd5. To disable size & checksums verification for broken repositories
params['usemd5'] = False


import urllib2

import os , sys


import repoutils

import repolib

if sys.argv[1:] :
    if len(sys.argv) > 2 :
        print "Too many arguments"
        print "Usage : %s repo_name" % os.path.basename( sys.argv[0] )
        sys.exit(2)
    repo_name = sys.argv[1]
else :
    print "Usage : %s repo_name" % os.path.basename( sys.argv[0] )
    sys.exit(1)

config = repoutils.read_config( repo_name )

repo = repolib.instantiate_repo( config )

base_url = repo.base_url()


meta_files = repo.get_master_file( params )

# FIXME : debian - identify error from updated repositories
# FIXME : yum - only errors produce empty output
if not meta_files :
    repoutils.show_error( "Cannot process, exiting" )
    sys.exit(255)

# After verify all the mirroring parameters, it is safe to create directory tree

repo.build_local_tree()

# Once created, we move in the primary metadata file

local_repodata = repo.write_master_file( meta_files )

print repo.info( local_repodata )


download_pkgs = {}
download_size = 0

for subrepo in repo.get_subrepos() :

    print "Scanning %s" % ( subrepo , )

    _size , _pkgs = repo.get_package_list( subrepo , local_repodata , params , minor_filters )
    download_size += _size
    download_pkgs.update( _pkgs )


_size = download_size / 1024 / 1024
if _size > 2048 :
    print "Total size to download : %.1f Gb" % ( _size / 1024 )
else :
    print "Total size to download : %.1f Mb" % ( _size )

for pkg in download_pkgs.values() :

    destname = os.path.join( repo.repo_path() , pkg['Filename'] )

    # FIXME : Perform this check while appending to download_pkgs ???
    if os.path.isfile( destname ) :
        error = repoutils.md5_error( destname , pkg )
        if error :
            repoutils.show_error( error , False )
            os.unlink( destname )
        else :
            continue
    else :
        path , name = os.path.split( destname )
        if not os.path.exists( path ) :
            os.makedirs( path )

    if not repoutils.downloadRawFile ( urllib2.urlparse.urljoin( base_url , pkg['Filename'] ) , destname ) :
        repoutils.show_error( "Failure downloading file '%s'" % ( pkg['Filename'] ) , False )
