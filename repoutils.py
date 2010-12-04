
import os

import repolib
import tempfile
import ConfigParser


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
        print "Could not find a valid configuration file"
        return False

    if "global" not in config.sections() :
        print "Broken configuration, missing global section"
        return False

    if not config.has_option( "global", "destdir" ) :
        print "Broken configuration, missing destination directory"
        return False

    if repo_name not in config.sections() :
        print "Repository '%s' is not configured" % repo_name
        return False

    conf = {}
    conf['destdir'] = config.get( "global" , "destdir" )

    conf['type'] = config.get( repo_name , "type" )
    if config.has_option ( repo_name , "url" ) :
        conf['url'] = config.get( repo_name , "url" )
    else :
        scheme = config.get( repo_name , "scheme" )
        server = config.get( repo_name , "server" )
        base_path = config.get( repo_name , "base_path" )
        conf['url'] = repolib.unsplit( scheme , server , "%s/" % base_path )
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
        print "Could not find a valid configuration file"
        return False

    if repo_name not in config.sections() :
        print "Repository '%s' is not configured" % repo_name
        return False

    conf = {}

    if config.has_option( repo_name , "destdir" ) :

        conf['destdir'] = config.get( repo_name , "destdir" )
        conf['detached'] = True

    else :

        if "global" not in config.sections() :
            print "Broken configuration, missing global section"
            return False

        if not config.has_option( "global", "destdir" ) :
            print "Broken configuration, missing destination directory"
            return False

        conf['destdir'] = config.get( "global" , "destdir" )
        conf['detached'] = False

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


import threading

class DownloadThread ( threading.Thread ) :
    """File download thread. It is build around a threaded list where files
are appended. Once inserted, the files are downloaded by the main loop"""

    def __init__ ( self , repo ) :
        self.repo = repo
        # FIXME : Set to true when started, not during initialization
        self.running = True
        self.closed = False
        self.list=[]
        self.cond = threading.Condition()
        threading.Thread.__init__(self)

    def download_pkg ( self , pkg ) :

        destname = os.path.join( self.repo.repo_path() , pkg['Filename'] )

        # FIXME : Perform this check while appending to download_pkgs ???
        if os.path.isfile( destname ) :
            error = md5_error( destname , pkg )
            if error :
                show_error( error , False )
                os.unlink( destname )
            else :
                return
        else :
            path , name = os.path.split( destname )
            if not os.path.exists( path ) :
                os.makedirs( path )

        if not repolib.downloadRawFile ( pkg['Filename'] , destname , self.repo.base_url() ) :
            show_error( "Failure downloading file '%s'" % ( pkg['Filename'] ) , False )

    def run(self):
        """Main thread loop. Runs over the item list, downloading every file"""

        while self.running:
            self.cond.acquire()
            pkginfo = None
            if not self.list :
                if self.closed :
                   self.running = False
                   continue
                self.cond.wait()
            if self.running and self.list :
                pkginfo = self.list.pop(0)
            self.cond.release()
            if pkginfo :
                self.download_pkg( pkginfo )

    def append ( self , item ) :
        """Adds an item to the download queue"""
        self.cond.acquire()
        # FIXME : Raise exception if not running !!!
        try:
            if not self.list :
                # FIXME : Notification takes effect now or after release ???
                self.cond.notify()
            if self.closed :
                show_error( "Trying to append file '%s' to a closed thread" % item['Filename'] , False )
            else :
                self.list.append( item.copy() )
        finally:
            self.cond.release()

    def destroy(self):
        """Ends the main loop"""
        self.cond.acquire()
        try:
            self.closed=True
            # FIXME : Notification takes effect now or after release ???
            self.cond.notify()
        finally:
            self.cond.release()

