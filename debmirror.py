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


# FIXME : Include standard plain os.open??
extensions = {}

try :
    import gzip
    extensions['.gz'] = gzip.open
except :
    pass
    
try :
    import bz2
    extensions['.bz2'] = bz2.BZ2File
except :
    pass


def downloadRawFile ( remote , local=None ) :
    """Downloads a remote file to the local system.

    remote - URL
    local - Optional local name for the file

    Returns the local file name"""

    if not local :
        (handle, fname) = tempfile.mkstemp()
    else :
        fname = local
        handle = os.open( fname , os.O_WRONLY | os.O_TRUNC | os.O_CREAT )
    try:
        response = urllib2.urlopen( remote )
        data = response.read(256)
        while data :
            os.write(handle, data)
            data = response.read(256)
        os.close(handle)
    except Exception ,ex :
        print "Exception : %s" % ex
        os.close(handle)
        if not local :
            os.unlink(fname)
        return None
    return fname

def md5_error ( filename , item , bsize=128 ) :
    if os.stat( filename ).st_size != int( item['size'] ) :
        return "Bad file size '%s'" % filename
    # Policy is to verify all the checksums
    for type in cksum_handles.keys() :
        if item.has_key( type ) :
            if cksum_handles[type]( filename , bsize ) != item[type] :
                return "Bad %s checksum '%s'" % ( type , filename )
    return None

def calc_md5(filename, bsize=128):
    f = open( filename , 'rb' )
    _md5 = md5.md5()
    data = f.read(bsize)
    while data :
        _md5.update(data)
        data = f.read(bsize)
    f.close()
    return _md5.hexdigest()

def calc_sha(filename, bsize=128):
    f = open( filename , 'rb' )
    _sha = sha.sha()
    data = f.read(bsize)
    while data :
        _sha.update(data)
        data = f.read(bsize)
    f.close()
    return _sha.hexdigest()

import md5 , sha

cksum_handles = { 'md5sum':calc_md5 , 'sha1':calc_sha }

def gpg_error( signature , file , full_verification=False ) :

    if full_verification :
        return _gpg_error( signature , file )

    (sigfd, signature_file ) = tempfile.mkstemp()
    fd = open( signature )
    line = fd.readline()
    while line :
        os.write( sigfd , line )
        if line[:-1] == "-----END PGP SIGNATURE-----" :
            os.close( sigfd )
            if not _gpg_error( signature_file , file ) :
                fd.close()
                os.unlink( signature_file )
                return False
            sigfd = os.open( signature_file , os.O_WRONLY | os.O_TRUNC )
        line = fd.readline()
    else :
        os.close( sigfd )
    fd.close()
    os.unlink( signature_file )
    return "All signatures failed"

def _gpg_error( signature , file ) :
    gpgerror = "Not verified"
    try :
        result = GnuPGInterface.GnuPG().run( [ "--verify", signature , file ] )
        result.wait()
        gpgerror = False
    except IOError , ex :
        gpgerror = "Bad signatute : %s" % ex
    return gpgerror

def show_error( str , error=True ) :
    if error :
        print "ERROR : %s" % str
    else :
        print "WARNING : %s" % str


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
        release_pgp_file = downloadRawFile( urllib2.urlparse.urljoin( base_url , "%sRelease.gpg" % repo.metadata_path() ) )
    except urllib2.URLError , ex :
        print "Exception : %s" % ex
        sys.exit(255)
    except urllib2.HTTPError , ex :
        print "Exception : %s" % ex
        sys.exit(255)

    if not release_pgp_file :
        show_error( "Release.gpg file for suite '%s' is not found." % ( version ) )
        sys.exit(255)

    if os.path.isfile( local_release ) :
        errstr = gpg_error( release_pgp_file , local_release )
        if errstr :
            show_error( errstr , False )
            os.unlink( local_release )
        else :
            # FIXME : If we consider that our mirror is complete, it is safe to exit here
            if repostate == "synced" and not force :
                show_error( "Release file unchanged, exiting" , False )
                sys.exit(0)
            release = debian_bundle.deb822.Release( sequence=open( local_release ) )
            os.unlink( release_pgp_file )

else :
    if os.path.isfile( local_release ) :
        os.unlink( local_release )

if not os.path.isfile( local_release ) :

    try :
        release_file = downloadRawFile( urllib2.urlparse.urljoin( base_url , "%sRelease" % repo.metadata_path() ) )
    except urllib2.URLError , ex :
        print "Exception : %s" % ex
        sys.exit(255)
    except urllib2.HTTPError , ex :
        print "Exception : %s" % ex
        sys.exit(255)

    if not release_file :
        show_error( "Release file for suite '%s' is not found." % ( version ) )
        os.unlink( release_pgp_file )
        sys.exit(255)

    if usegpg :
        errstr = gpg_error( release_pgp_file , release_file )
        os.unlink( release_pgp_file )
        if errstr :
            show_error( errstr )
            os.unlink( release_file )
            sys.exit(255)

    release = debian_bundle.deb822.Release( sequence=open( release_file ) )
    
    
# FIXME : Why not check also against release['Codename'] ??
if release['Suite'].lower() == version.lower() :
    show_error( "You have supplied suite '%s'. Please use codename '%s' instead" % ( version, release['Codename'] ) )
    os.unlink( release_file )
    sys.exit(1)

# NOTE : security and volatile repositories prepend a string to the actual component name
release_comps = map( lambda s : s.rsplit("/").pop() , release['Components'].split() )

for comp in components :
    if comp not in release_comps :
        show_error( "Component '%s' is not available ( %s )" % ( comp , " ".join(release_comps) ) )
        sys.exit(1)

release_archs = release['Architectures'].split()
for arch in architectures :
    if arch not in release_archs :
        show_error( "Architecture '%s' is not available ( %s )" % ( arch , " ".join(release_archs) ) )
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

release_sections = []
release_priorities = []
release_tags = []

for comp in components :

    for arch in architectures :

        print "Scanning %s / %s" % ( comp , arch )

        # NOTE : Downloading Release file is quite redundant

        fd = False
        localname = None

        for ( extension , read_handler ) in extensions.iteritems() :

            localname = os.path.join( suite_path , "%sPackages%s" % ( repo.metadata_path(arch,comp) , extension ) )

            if os.path.isfile( localname ) :
                #
                # IMPROVEMENT : For Release at least, and _multivalued in general : Multivalued fields returned as dicts instead of lists
                #
                # FIXME : 'size' element should be a number !!!
                #
                # FIXME : What about other checksums (sha1, sha256)
                _item = {}
                for type in ( 'MD5Sum' , 'SHA1' , 'SHA256' ) :
                    for item in release[type] :
                        if item['name'] == "%sPackages%s" % ( repo.metadata_path(arch,comp) , extension ) :
                            _item.update( item )
                if _item :
                    error = md5_error( localname , _item )
                    if error :
                        show_error( error , False )
                        os.unlink( localname )
                        continue

                    # NOTE : force and unsync should behave different here? We could just force download if forced
                    if repostate == "synced" and not force :
                        show_error( "Local copy of '%sPackages%s' is up-to-date, skipping." % ( repo.metadata_path(arch,comp) , extension ) , False )
                    else :
                        fd = read_handler( localname )

                    break

                else :
                    show_error( "Checksum for file '%sPackages%s' not found, go to next format." % ( repo.metadata_path(arch,comp) , extension ) , True )
                    continue

        else :

            show_error( "No local Packages file exist for %s / %s. Downloading." % ( comp , arch ) , True )

            for ( extension , read_handler ) in extensions.iteritems() :

                localname = os.path.join( suite_path , "%sPackages%s" % ( repo.metadata_path(arch,comp) , extension ) )
                url = urllib2.urlparse.urljoin( repo.base_url(arch,comp) , "%sPackages%s" % ( repo.metadata_path(arch,comp) , extension ) )

                if downloadRawFile( url , localname ) :
                    #
                    # IMPROVEMENT : For Release at least, and _multivalued in general : Multivalued fields returned as dicts instead of lists
                    #
                    # FIXME : 'size' element should be a number !!!
                    #
                    # FIXME : What about other checksums (sha1, sha256)
                    _item = {}
                    for type in ( 'MD5Sum' , 'SHA1' , 'SHA256' ) :
                        for item in release[type] :
                            if item['name'] == "%sPackages%s" % ( repo.metadata_path(arch,comp) , extension ) :
                                _item.update( item )
                    if _item :
                        error = md5_error( localname , _item )
                        if error :
                            show_error( error , False )
                            os.unlink( localname )
                            continue

                        break

                    else :
                        show_error( "Checksum for file '%s' not found, exiting." % item['name'] ) 
                        continue

            else :
                show_error( "No Valid Packages file found for %s / %s" % ( comp , arch ) )
                sys.exit(0)

            fd = read_handler( localname )

        if fd :
            packages = debian_bundle.debian_support.PackageFile( localname , fd )

# FIXME : If any minor filter is used, Packages file must be recreated for the exported repo
#         Solution : Disable filtering on first approach
#         In any case, the real problem is actually checksumming, reconstructiog Release and signing

            print "Scanning available packages for minor filters"
            for pkg in packages :
                pkginfo = debian_bundle.deb822.Deb822Dict( pkg )

                # NOTE : Is this actually a good idea ?? It simplifies, but I would like to mirror main/games but not contrib/games, for example
                # SOLUTION : Create a second and separate Category with the last part (filename) of Section
                # For now, we kept the simplest way
                if pkginfo['Section'].find("%s/"%comp) == 0 :
                    pkginfo['Section'] = pkginfo['Section'][pkginfo['Section'].find("/")+1:]

                if pkginfo['Section'] not in release_sections :
                    release_sections.append( pkginfo['Section'] )
                if pkginfo['Priority'] not in release_priorities :
                    release_priorities.append( pkginfo['Priority'] )
                if 'Tag' in pkginfo.keys() and pkginfo['Tag'] not in release_tags :
                    release_tags.append( pkginfo['Tag'] )

                if sections and pkginfo['Section'] not in sections :
                    continue
                if priorities and pkginfo['Priority'] not in priorities :
                    continue
                if tags and 'Tag' in pkginfo.keys() and pkginfo['Tag'] not in tags :
                    continue

                pkg_key = "%s-%s" % ( pkginfo['Package'] , pkginfo['Architecture'] )
                if pkg_key in download_pkgs.keys() :
                    if pkginfo['Architecture'] != "all" :
                        show_error( "Package '%s - %s' is duplicated in repositories" % ( pkginfo['Package'] , pkginfo['Architecture'] ) , False )
                else :
                    download_pkgs[ pkg_key ] = pkginfo
                    # FIXME : This might cause a ValueError exception ??
                    download_size += int( pkginfo['Size'] )

            print "Current download size : %.1f Mb" % ( download_size / 1024 / 1024 )
            fd.close()


# print "All sects",release_sections
# print "All prios",release_priorities
# # print "All tags",release_tags


_size = download_size / 1024 / 1024
if _size > 2048 :
    print "Total size to download : %.1f Gb" % ( _size / 1024 )
else :
    print "Total size to download : %.1f Mb" % ( _size )

for pkg in download_pkgs.values() :

    destname = os.path.join( destdir , pkg['Filename'] )

    # FIXME : Perform this check while appending to download_pkgs ???
    if os.path.isfile( destname ) :
        error = md5_error( destname , pkg )
        if error :
            show_error( error , False )
            os.unlink( destname )
        else :
            continue
    else :
        path , name = os.path.split( destname )
        if not os.path.exists( path ) :
            os.makedirs( path )

    if not downloadRawFile ( urllib2.urlparse.urljoin( repo_url , pkg['Filename'] ) , destname ) :
        show_error( "Failure downloading file '%s'" % ( pkg['Filename'] ) , False )

