#!/usr/bin/python

# FIXME : Allow reading from a sources.list file, parsing into scheme, server, path, codename and components

scheme = "http"
server = "ftp.rediris.es"
base_path = "mirror/fedora"
server_upd = "download.fedora.redhat.com"
base_path_upd = "pub/fedora/linux/updates"
destdir = "/home/jpalacios/repomirror"
#destdir = "/shares/internal/PUBLIC/mirrors/debian"

version = "12" # "lenny"
architectures = [ "i386" , "x86_64" ] # architectures = [ "i386" , "amd64" ]
components = [ "main" , "contrib" ]
components = [ "contrib" ]
#
#server = "security.debian.org"
#base_path = ""
#version = "lenny/updates"
#components = [ "main" ]
#
#server = "volatile.debian.org"
#base_path = "debian-volatile"
#version = "lenny/volatile"
#components = [ "main" ]
#
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

import md5

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
    if item['size'] :
      # FIXME : Temporary to speedup fedora mirroring developement
      if os.stat( filename ).st_size != int( item['size'] ) :
        return "Bad file size '%s'" % filename
    if item['md5sum'] :
      # FIXME : Temporary to speedup fedora mirroring developement
      if calc_md5( filename , bsize ) != item['md5sum'] :
        return "Bad MD5 checksum '%s'" % filename
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


class yum_repository :

    def __init__ ( self , url , version ) :
        self.repo_url = url
        self.version = version

    def base_url ( self ) :
        return urllib2.urlparse.urljoin( repo_url , "%s/Fedora/" % version )

    def repo_path ( self , destdir ) :
        return os.path.join( os.path.join( destdir , version ) , "Fedora" )

    def metadata_path ( self , arch ) :
        return "%s/os/" % arch

    def packages_path ( self , arch ) :
        return "%s/Packages" % self.metadata_path( arch )

class fedora_update_repository ( yum_repository ) :

    def __init__ ( self , url , version , arch=None ) :
        yum_repository.__init__( self , url , version , arch )

    def base_url ( self ) :
        return urllib2.urlparse.urljoin( repo_url , "%s/" % version )

    def repo_path ( self , destdir ) :
        return os.path.join( destdir , version )

    def metadata_path ( self ) :
        return "%s/" % arch

    def packages_path ( self ) :
        return self.metadata_path()


# This gets built to the typical path on source.list
repo_url = urllib2.urlparse.urlunsplit( ( scheme , server , "%s/" % base_path , None , None ) )

repo = yum_repository( repo_url , version )
#upd#repo = fedora_update_repository( repo_url_upd , version )

base_url = repo.base_url()

# This is either the home of dists or repomd files
suite_path = repo.repo_path( destdir )

# For fedora, pool and suite path are the same
pool_path = suite_path


#if os.path.isfile( local_release ) :
#    os.unlink( local_release )

#if not os.path.isfile( local_release ) :
#
#    try :
#        release_file = downloadRawFile( urllib2.urlparse.urljoin( base_url , "Release" ) )
#    except urllib2.URLError , ex :
#        print "Exception : %s" % ex
#        sys.exit(255)
#    except urllib2.HTTPError , ex :
#        print "Exception : %s" % ex
#        sys.exit(255)
#
#    if not release_file :
#        show_error( "Release file for suite '%s' is not found." % ( version ) )
#        os.unlink( release_pgp_file )
#        sys.exit(255)
#
#    # release = debian_bundle.deb822.Release( sequence=open( release_file ) )
#
#print "file is",release_file


repomd_file = {}
for arch in architectures :

    try :
        repomd_file[arch] = downloadRawFile( urllib2.urlparse.urljoin( base_url , "%s/repodata/repomd.xml" % repo.metadata_path(arch) ) )
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
        show_error( "Architecture '%s' is not available for version %s" % ( arch , version ) )
        for _arch in repomd_file.keys() :
            if _arch != arch :
                os.unlink( repomd_file[_arch] )
        sys.exit(1)

# After verify all the mirroring parameters, it is safe to create directory tree

if not os.path.exists( suite_path ) :
    os.makedirs( suite_path )

for arch in repomd_file.keys() :
    local_packages = os.path.join( pool_path , repo.packages_path(arch) )
    if not os.path.exists( local_packages ) :
        os.makedirs( local_packages )

# And then relocate files from temporary locations

local_repodata = {}
for arch in repomd_file.keys() :
    local_repodata[arch] = os.path.join( suite_path , repo.metadata_path(arch) )
    if not os.path.exists( os.path.join( local_repodata[arch] , "repodata" ) ) :
        os.mkdir( os.path.join( local_repodata[arch] , "repodata" ) )
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

release_sections = []
release_priorities = []
release_tags = []

import xml.dom.minidom

for arch in architectures :

    print "Scanning %s" % ( arch )

    item = False

    repodoc = xml.dom.minidom.parse( os.path.join( local_repodata[arch] , "repodata/repomd.xml" ) )
    doc = repodoc.documentElement
    for node in doc.getElementsByTagName( "data" ) :
        if node.getAttribute( "type" ) == "primary" :
            location = node.getElementsByTagName( "location" )
            if not location :
                show_error( "No location element within repomd file" )
                continue
            # FIXME : Produce an error if multiple locations ?
            size = node.getElementsByTagName( "size" )
            if size :
                _size = int(size[0].firstChild.nodeValue)
            else :
                _size = False
            item = { 'href':location[0].getAttribute( "href" ) , 'size':_size , 'md5sum':False }
            # FIXME : Loop over checksum tags to populate item with available checksums
            break
    else :
        show_error( "No primary node within repomd file" )
        os.unlink( os.path.join( local_repodata[arch] , "repodata/repomd.xml" ) )
        sys.exit(255)

    # FIXME : On problems, exit or continue next arch ???

    localname = os.path.join( local_repodata[arch] , item['href'] )

    if os.path.isfile( localname ) :
        error = md5_error( localname , item )
        if error :
            show_error( error , False )
            os.unlink( localname )
        else :
            if repostate == "synced" and not force :
                break

    if not os.path.isfile( localname ) :

        show_error( "No local Packages file exist for %s-%s. Downloading." % ( version , arch ) , True )

        url = urllib2.urlparse.urljoin( base_url , "%s/%s" % ( repo.metadata_path(arch) , item['href'] ) )

        if downloadRawFile( url , localname ) :
            error = md5_error( localname , item )
            if error :
                show_error( error )
                os.unlink( localname )
                sys.exit(255)
        else :
            show_error( "Problems downloading primary file for %s-%s" % ( version , arch ) )
            sys.exit(255)

    fd = gzip.open( localname )
    packages = xml.dom.minidom.parse( fd )
    # FIXME : What about gettint doc root and so ...

    print "Scanning available packages for minor filters (not implemented yet !!!)"
    # Most relevant for minor filter is   <format><rpm:group>...</rpm:group>

    for pkginfo in packages.getElementsByTagName( "package" ) :

        # FIXME : A XML -> Dict class is quite helpful here !!

# FIXME : If any minor filter is used, Packages file must be recreated for the exported repo
#         Solution : Disable filtering on first approach
#         In any case, the real problem is actually checksumming, reconstructiog Release and signing


        """
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
        """

        name = pkginfo.getElementsByTagName('name')[0].firstChild.nodeValue
        _arch = pkginfo.getElementsByTagName('arch')[0].firstChild.nodeValue
        pkg_key = "%s-%s" % ( name , _arch )
        if pkg_key in download_pkgs.keys() :
            if _arch != "noarch" :
                show_error( "Package '%s - %s' is duplicated in repositories" % ( name , _arch ) , False )
        else :
            pkgdict = {
                'href':pkginfo.getElementsByTagName('location')[0].getAttribute( "href" ) ,
                'size':pkginfo.getElementsByTagName('size')[0].getAttribute( "package" ) ,
                'md5sum':False
                }
            download_pkgs[ pkg_key ] = pkgdict
            # FIXME : This might cause a ValueError exception ??
            download_size += int( pkgdict['size'] )

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

    destname = os.path.join( os.path.join( pool_path , repo.packages_path(arch) ) , pkg['href'] )

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

    print "downloadRawFile ( %s , %s )" % ( urllib2.urlparse.urljoin( base_url , "%s/%s" % ( repo.metadata_path(arch) , pkg['href'] ) ) , destname )
    if not downloadRawFile ( urllib2.urlparse.urljoin( base_url , "%s/%s" % ( repo.metadata_path(arch) , pkg['href'] ) ) , destname ) :
        show_error( "Failure downloading file '%s'" % ( pkg['href'] ) , False )
