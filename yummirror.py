#!/usr/bin/python

params = {}
# mode (update|init) - decides if we stop processing for unchanged metadata files
params['mode'] = "update"

# usegpg. To disable verification of PGP signatures. Forces the download of Release file every run
# FIXME : Add an ignore all verifications? (pgp+md5)
params['usegpg'] = False

import urllib2

import os , sys
import errno , shutil


import repoutils

import repolib

repo_name = "yum"
config = repolib.read_config( repo_name )

repo = repolib.instantiate_repo( config )

base_url = repo.base_url()

suite_path = repo.repo_path()

repomd_file = repo.get_master_file( params )

# FIXME : For yum repositories, only errors produce empty output
if not repomd_file :
    repoutils.show_error( "Cannot process, exiting" )
    sys.exit(255)

# After verify all the mirroring parameters, it is safe to create directory tree

repo.build_local_tree()

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
""" % ( repo.version , repo.repo_url , " ".join(repo.architectures) )


download_pkgs = {}
download_size = 0

for arch in repo.architectures :

    print "Scanning %s" % ( arch )

    _size , _pkgs = repo.get_package_list( arch , local_repodata[arch] , params )
    download_size += _size
    download_pkgs.update( _pkgs )


_size = download_size / 1024 / 1024
if _size > 2048 :
    print "Total size to download : %.1f Gb" % ( _size / 1024 )
else :
    print "Total size to download : %.1f Mb" % ( _size )

for pkg in download_pkgs.values() :

    destname = os.path.join( repo.repo_path() , pkg['destname'] )

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

