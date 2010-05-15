
import os , sys

import urllib2
import tempfile
import ConfigParser


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
        os.unlink(fname)
        return None
    return fname


default_params = {}

# mode (update|init) - decides if we stop processing for unchanged metadata files
default_params['mode'] = "update"

# usegpg. To disable verification of PGP signatures, and force the download of master file every run
default_params['usegpg'] = True
try :
    import GnuPGInterface
    default_params['usegpg'] = True
except :
    default_params['usegpg'] = False


# usemd5. To disable size & checksums verification for broken repositories
default_params['usemd5'] = True


# pkgvflags. To specify special flags for verification of downloaded packages
default_params['pkgvflags'] = "SKIP_NONE"


def read_config ( repo_name ) :

    config = ConfigParser.RawConfigParser()
    if not config.read( [ "/etc/repomirror.conf" , os.path.expanduser("~/.repomirror") ] ) :
        show_error( "Could not find a valid configuration file" )
        sys.exit(255)

    if "global" not in config.sections() :
        show_error( "Broken configuration, missing global section" )
        sys.exit(255)

    if not config.has_option( "global", "destdir" ) :
        show_error( "Broken configuration, missing destination directory" )
        sys.exit(255)

    if repo_name not in config.sections() :
        show_error( "Repository '%s' is not configured" % repo_name )
        sys.exit(255)

    conf = {}
    conf['destdir'] = config.get( "global" , "destdir" )

    conf['type'] = config.get( repo_name , "type" )
    if config.has_option ( repo_name , "url" ) :
        conf['url'] = config.get( repo_name , "url" )
    else :
        scheme = config.get( repo_name , "scheme" )
        server = config.get( repo_name , "server" )
        base_path = config.get( repo_name , "base_path" )
        conf['url'] = urllib2.urlparse.urlunsplit( ( scheme , server , "%s/" % base_path , None , None ) )
    conf['version'] = config.get( repo_name , "version" )
    conf['architectures'] = config.get( repo_name , "architectures" ).split()
    if config.has_option( repo_name , "components" ) :
        conf['components'] = config.get( repo_name , "components" ).split()

    conf['filters'] = {}
    if config.has_option( repo_name , "filters" ) :
        for subfilter in config.get( repo_name , "filters" ).split() :
            if config.has_option( repo_name , subfilter ) :
                conf['filters'][subfilter] = map( lambda x : x.replace("_"," ") , config.get( repo_name , subfilter ).split() )

    conf['params'] = {}
    conf['params'].update( default_params )
    for key in conf['params'].keys() :
        if config.has_option( "global" , key ) :
            try :
                conf['params'][ key ] = config.getboolean( "global" , key )
            except ValueError , ex :
                conf['params'][ key ] = config.get( "global" , key )
        if config.has_option( repo_name , key ) :
            try :
                conf['params'][ key ] = config.getboolean( repo_name , key )
            except ValueError , ex :
                conf['params'][ key ] = config.get( repo_name , key )

    conf['params']['pkgvflags'] = eval( conf['params']['pkgvflags'] )

    return conf

def read_build_config ( repo_name ) :

    config = ConfigParser.RawConfigParser()
    if not config.read( [ "/etc/buildrepo.conf" , os.path.expanduser("~/.buildrepo") ] ) :
        show_error( "Could not find a valid configuration file" )
        sys.exit(255)

    if "global" not in config.sections() :
        show_error( "Broken configuration, missing global section" )
        sys.exit(255)

    if not config.has_option( "global", "destdir" ) :
        show_error( "Broken configuration, missing destination directory" )
        sys.exit(255)

    if repo_name not in config.sections() :
        show_error( "Repository '%s' is not configured" % repo_name )
        sys.exit(255)

    conf = {}
    conf['destdir'] = config.get( "global" , "destdir" )

    conf['type'] = config.get( repo_name , "type" )

    conf['version'] = config.get( repo_name , "version" )
    conf['architectures'] = config.get( repo_name , "architectures" ).split()
    if config.has_option( repo_name , "components" ) :
        conf['components'] = config.get( repo_name , "components" ).split()

    return conf


SKIP_NONE = 0
SKIP_SIZE = 1
SKIP_CKSUM = 2

def md5_error ( filename , item , skip_check = 0 , bsize=128 ) :
    if skip_check == ( SKIP_SIZE | SKIP_CKSUM ) :
        return "No check selected for '%s'" % filename
        return None

    if not ( skip_check | SKIP_SIZE ) :
        if os.stat( filename ).st_size != int( item['size'] ) :
            return "Bad file size '%s'" % filename

    # Policy is to verify all the checksums
    if not ( skip_check | SKIP_CKSUM ) :
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

cksum_handles = { 'md5sum':calc_md5 , 'sha1':calc_sha , 'sha':calc_sha }


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


