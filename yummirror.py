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

import gzip


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

# And then relocate files from temporary locations

local_repodata = {}
for arch in repomd_file.keys() :
    local_repodata[arch] = os.path.join( suite_path , repo.metadata_path(arch) )
    if not os.path.exists( os.path.join( local_repodata[arch] , "repodata" ) ) :
        os.makedirs( os.path.join( local_repodata[arch] , "repodata" ) )
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
            item = { 'href':location[0].getAttribute( "href" ) , 'size':int(size[0].firstChild.nodeValue) }
            for _node in node.getElementsByTagName( "checksum" ) :
                item[ _node.getAttribute( "type" ) ] = _node.firstChild.nodeValue
            break
    else :
        show_error( "No primary node within repomd file" )
        os.unlink( os.path.join( local_repodata[arch] , "repodata/repomd.xml" ) )
        sys.exit(255)

    del repodoc

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

        name = pkginfo.getElementsByTagName('name')[0].firstChild.nodeValue
        _arch = pkginfo.getElementsByTagName('arch')[0].firstChild.nodeValue
        pkg_key = "%s-%s" % ( name , _arch )
        if pkg_key in download_pkgs.keys() :
            if _arch != "noarch" :
                show_error( "Package '%s - %s' is duplicated in repositories" % ( name , _arch ) , False )
        else :
            href = pkginfo.getElementsByTagName('location')[0].getAttribute( "href" )
            pkgdict = {
                'sourcename':urllib2.urlparse.urljoin( repo.metadata_path(arch) , href ) ,
                'destname':os.path.join( repo.metadata_path(arch) , href ) ,
                'size':pkginfo.getElementsByTagName('size')[0].getAttribute( "package" )
                }
            download_pkgs[ pkg_key ] = pkgdict
            # FIXME : This might cause a ValueError exception ??
            download_size += int( pkgdict['size'] )

        pkginfo.unlink()
        del pkginfo

    del packages

    print "Current download size : %.1f Mb" % ( download_size / 1024 / 1024 )
    fd.close()


_size = download_size / 1024 / 1024
if _size > 2048 :
    print "Total size to download : %.1f Gb" % ( _size / 1024 )
else :
    print "Total size to download : %.1f Mb" % ( _size )

for pkg in download_pkgs.values() :

    destname = os.path.join( pool_path , pkg['destname'] )

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

    if not downloadRawFile ( urllib2.urlparse.urljoin( base_url , pkg['sourcename'] ) , destname ) :
        show_error( "Failure downloading file '%s'" % ( pkg['sourcename'] ) , False )

