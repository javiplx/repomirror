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
import errno , shutil


import repoutils

import repolib

repo_name = "yum"
config = repolib.read_config( repo_name )

architectures = config[ "architectures" ]

repo = repolib.instantiate_repo( config )

base_url = repo.base_url()

# This is either the home of dists or repomd files
suite_path = repo.repo_path()

# For fedora, pool and suite path are the same
pool_path = repo.repo_path()

repomd_file = repo.get_master_file( repostate , force , usegpg , architectures )

# FIXME : For yum repositories, only errors produce empty output
if not release_file :
    repoutils.show_error( "Cannot process, exiting" )
    sys.exit(255)
release = debian_bundle.deb822.Release( sequence=open( release_file ) )

# After verify all the mirroring parameters, it is safe to create directory tree

repo.build_local_tree( architectures )

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
""" % ( repo.version , repo.repo_url , " ".join(architectures) )


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

