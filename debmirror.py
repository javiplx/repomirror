#!/usr/bin/python

# FIXME : Allow reading from a sources.list file, parsing into scheme, server, path, codename and components

sections = []
priorities = []
tags = []

# Status and command line options
repostate = "synced"
force = True
# FIXME : Add an ignore all verifications? (pgp+md5)
usegpg = False
#
# repostate. If 'synced', the repository is complete, so checking description files could suffice
# force. Forces processing of synced repositories
# usegpg. To disable verification of PGP signatures. Forces the download of Release file every run

# FIXME : Create a separate program to list all the sections, pririties and tags

import debian_bundle.deb822 , debian_bundle.debian_support

import urllib2

import os , sys
import tempfile
import errno , shutil

try :
    import GnuPGInterface
except :
    usegpg = False


import repoutils

import repolib

repo_name = "debian"
config = repolib.read_config( repo_name )

destdir = config[ "destdir" ]

type = config[ "type" ]
scheme = config[ "scheme" ]
server = config[ "server" ]
base_path = config[ "base_path" ]
version = config[ "version" ]
architectures = config[ "architectures" ]
components = config[ "components" ]


# NOTE : If base_path is empty (security), the produced URL has '//' and download fails
#        All the stuff with urljoin is to avoid that, taking care of specify the trailing '/'
#        in cases where we know target is a directory

# This gets built to the typical path on source.list
repo_url = urllib2.urlparse.urlunsplit( ( scheme , server , "%s/" % base_path , None , None ) )

repo = repolib.instantiate_repo( type , repo_url , version )

base_url = repo.base_url()

suite_path = os.path.join( repo.repo_path( destdir ) , repo.metadata_path() )

pool_path = os.path.join( repo.repo_path( destdir ) , "pool" )

local_release = os.path.join( suite_path , "Release" )


if usegpg :
    try :
        release_pgp_file = repoutils.downloadRawFile( urllib2.urlparse.urljoin( base_url , "%sRelease.gpg" % repo.metadata_path() ) )
    except urllib2.URLError , ex :
        print "Exception : %s" % ex
        sys.exit(255)
    except urllib2.HTTPError , ex :
        print "Exception : %s" % ex
        sys.exit(255)

    if not release_pgp_file :
        repoutils.show_error( "Release.gpg file for suite '%s' is not found." % ( version ) )
        sys.exit(255)

    if os.path.isfile( local_release ) :
        errstr = repoutils.gpg_error( release_pgp_file , local_release )
        if errstr :
            repoutils.show_error( errstr , False )
            os.unlink( local_release )
        else :
            # FIXME : If we consider that our mirror is complete, it is safe to exit here
            if repostate == "synced" and not force :
                repoutils.show_error( "Release file unchanged, exiting" , False )
                sys.exit(0)
            release = debian_bundle.deb822.Release( sequence=open( local_release ) )
            os.unlink( release_pgp_file )

else :
    if os.path.isfile( local_release ) :
        os.unlink( local_release )

if not os.path.isfile( local_release ) :

    try :
        release_file = repoutils.downloadRawFile( urllib2.urlparse.urljoin( base_url , "%sRelease" % repo.metadata_path() ) )
    except urllib2.URLError , ex :
        print "Exception : %s" % ex
        sys.exit(255)
    except urllib2.HTTPError , ex :
        print "Exception : %s" % ex
        sys.exit(255)

    if not release_file :
        repoutils.show_error( "Release file for suite '%s' is not found." % ( version ) )
        os.unlink( release_pgp_file )
        sys.exit(255)

    if usegpg :
        errstr = repoutils.gpg_error( release_pgp_file , release_file )
        os.unlink( release_pgp_file )
        if errstr :
            repoutils.show_error( errstr )
            os.unlink( release_file )
            sys.exit(255)

    release = debian_bundle.deb822.Release( sequence=open( release_file ) )
    
    
# FIXME : Why not check also against release['Codename'] ??
if release['Suite'].lower() == version.lower() :
    repoutils.show_error( "You have supplied suite '%s'. Please use codename '%s' instead" % ( version, release['Codename'] ) )
    os.unlink( release_file )
    sys.exit(1)

# NOTE : security and volatile repositories prepend a string to the actual component name
release_comps = map( lambda s : s.rsplit("/").pop() , release['Components'].split() )

for comp in components :
    if comp not in release_comps :
        repoutils.show_error( "Component '%s' is not available ( %s )" % ( comp , " ".join(release_comps) ) )
        sys.exit(1)

release_archs = release['Architectures'].split()
for arch in architectures :
    if arch not in release_archs :
        repoutils.show_error( "Architecture '%s' is not available ( %s )" % ( arch , " ".join(release_archs) ) )
        sys.exit(1)

# After verify all the mirroring parameters, it is safe to create directory tree

if not os.path.exists( suite_path ) :
    os.makedirs( suite_path )

if not os.path.exists( local_release ) :
    try :
        os.rename( release_file , local_release )
    except OSError , ex :
        if ex.errno != errno.EXDEV :
            print "OSError: %s" % ex
            sys.exit(1)
        shutil.move( release_file , local_release )

for comp in components :
    if not os.path.exists( os.path.join( suite_path , comp ) ) :
        os.mkdir( os.path.join( suite_path , comp ) )
    for arch in architectures :
        packages_path = repo.metadata_path( arch , comp )
        if not os.path.exists( os.path.join( suite_path , packages_path ) ) :
            os.mkdir( os.path.join( suite_path , packages_path ) )

if not os.path.exists( pool_path ) :
    os.mkdir( pool_path )

for comp in components :
    pool_com_path = os.path.join( pool_path , comp )
    if not os.path.exists( pool_com_path ) :
        os.mkdir( pool_com_path )

if not release.has_key( 'Version' ) :
    release['Version'] = "undef"
print """
Mirroring %(Label)s %(Version)s (%(Codename)s)
%(Origin)s %(Suite)s , %(Date)s
""" % release
print "Components : %s\nArchitectures : %s\n" % ( " ".join(components) , " ".join(architectures) )


download_pkgs = {}
download_size = 0

for comp in components :

    for arch in architectures :

      print "Scanning %s / %s" % ( comp , arch )

      _size , _pkgs = repo.get_package_list( arch , suite_path , repostate , force , comp , release , sections , priorities , tags )
      download_size += _size
      download_pkgs.update( _pkgs )


_size = download_size / 1024 / 1024
if _size > 2048 :
    print "Total size to download : %.1f Gb" % ( _size / 1024 )
else :
    print "Total size to download : %.1f Mb" % ( _size )

for pkg in download_pkgs.values() :

    destname = os.path.join( destdir , pkg['Filename'] )

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

