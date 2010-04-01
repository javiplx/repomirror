#!/usr/bin/python

# Status and command line options
repostate = "synced"
force = True
# FIXME : Add an ignore all verifications? (pgp+md5)
usegpg = False
#
# repostate. If 'synced', the repository is complete, so checking description files could suffice
# force. Forces processing of synced repositories
# usegpg. To disable verification of PGP signatures. Forces the download of Release file every run

import urllib2

import os , sys
import tempfile
import errno , shutil


import repoutils

import repolib

repo_name = "yum"
config = repolib.read_config( repo_name )

destdir = config[ "destdir" ]

type = config[ "type" ]
scheme = config[ "scheme" ]
server = config[ "server" ]
base_path = config[ "base_path" ]
version = config[ "version" ]
architectures = config[ "architectures" ]


# This gets built to the typical path on source.list
repo_url = urllib2.urlparse.urlunsplit( ( scheme , server , "%s/" % base_path , None , None ) )

repo = repolib.instantiate_repo( type , repo_url , version )

base_url = repo.base_url()

# This is either the home of dists or repomd files
suite_path = repo.repo_path( destdir )

# For fedora, pool and suite path are the same
pool_path = repo.repo_path( destdir )

repomd_file = {}
for arch in architectures :

    try :
        repomd_file[arch] = repoutils.downloadRawFile( urllib2.urlparse.urljoin( base_url , "%s/repodata/repomd.xml" % repo.metadata_path(arch) ) )
    except urllib2.URLError , ex :
        print "Exception : %s" % ex
        for _arch in repomd_file.keys() :
            if _arch != arch :
                os.unlink( repomd_file[_arch] )
        sys.exit(255)
    except urllib2.HTTPError , ex :
        print "Exception : %s" % ex
        for _arch in repomd_file.keys() :
            if _arch != arch :
                os.unlink( repomd_file[_arch] )
        sys.exit(255)

    if not repomd_file[arch] :
        repoutils.show_error( "Architecture '%s' is not available for version %s" % ( arch , version ) )
        for _arch in repomd_file.keys() :
            if _arch != arch :
                os.unlink( repomd_file[_arch] )
        sys.exit(1)

# After verify all the mirroring parameters, it is safe to create directory tree

repo.build_local_tree( repomd_file.keys() )

# And then relocate files from temporary locations

local_repodata = {}
for arch in repomd_file.keys() :
    local_repodata[arch] = os.path.join( suite_path , repo.metadata_path(arch) )
    try :
        os.rename( repomd_file[arch] , os.path.join( local_repodata[arch] , "repodata/repomd.xml" ) )
    except OSError , ex :
        if ex.errno != errno.EXDEV :
            print "OSError: %s" % ex
            sys.exit(1)
        shutil.move( repomd_file[arch] , os.path.join( local_repodata[arch] , "repodata/repomd.xml" ) )

print """
Mirroring version %s
%s
Architectures : %s
""" % ( version , repo_url , " ".join(architectures) )


download_pkgs = {}
download_size = 0

for arch in architectures :

    print "Scanning %s" % ( arch )

    _size , _pkgs = repo.get_package_list( arch , local_repodata[arch] , repostate , force )
    download_size += _size
    download_pkgs.update( _pkgs )


_size = download_size / 1024 / 1024
if _size > 2048 :
    print "Total size to download : %.1f Gb" % ( _size / 1024 )
else :
    print "Total size to download : %.1f Mb" % ( _size )

for pkg in download_pkgs.values() :

    destname = os.path.join( pool_path , pkg['destname'] )

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

    if not repoutils.downloadRawFile ( urllib2.urlparse.urljoin( base_url , pkg['sourcename'] ) , destname ) :
        repoutils.show_error( "Failure downloading file '%s'" % ( pkg['sourcename'] ) , False )

