
import os

import urllib2


import socket
socket.setdefaulttimeout(5)

urljoin = urllib2.urlparse.urljoin

def unsplit ( scheme , server , path ) :
    urltuple = ( scheme , server , path , None , None )
    return urllib2.urlparse.urlunsplit( urltuple )


import logging

console = logging.StreamHandler()
formatter = logging.Formatter("%(levelname)s : %(message)s")
console.setFormatter(formatter)

logger = logging.getLogger()
logger.addHandler( console )


import config , utils

class _repository :

    def new ( name ) :
        raise Exception( "Calling an abstract method" )

    def __init__ ( self , config ) :

        self.name = config.__name__

	self.destdir = config[ "destdir" ]
        self.version = config[ "version" ]

        self.architectures = config[ "architectures" ]

        if not os.path.isdir( self.destdir ) :
            raise Exception( "Destination directory %s does not exists" % self.destdir )

    def repo_path ( self ) :
        raise Exception( "Calling an abstract method" )


class PackageListInterface :
    """This Interface is just a partial defintion of a list. It is included
as root for inheritance tree"""

    def append ( self , item ) :
        raise Exception( "Calling abstract PackageListInterface.append on %s" % self )

    # NOTE : In a strict sense, this method is not required for list interface, and is actually not used anywhere
    def extend ( self , itemlist ) :
        raise Exception( "Calling abstract PackageListInterface.extend on %s" % self )

    def __iter__ ( self ) :
        raise Exception( "Calling abstract PackageListInterface.__iter__ on %s" % self )

class PackageList ( list , PackageListInterface ) :

    # Avoid representation of full list
    def __repr__ ( self ) :
        return "<PackageList items:%d>" % len(self)


class DownloadInterface ( PackageListInterface ) :
    """Interface for complex download lists, which increase simple list functionality
by allowing appending during iteration"""

    def __init__ ( self , repo ) :
        self.repo = repo
        self.started = False
        self.closed = False

    def start ( self ) :
        """Method to signal when the object becomes a non iterable one, in the sense that iteration cannot be started.
It requires an explicit check on iterator/generator instantiation"""
        raise Exception( "Calling abstract DownloadInterface.start on %s" % self )

    def finish ( self ) :
        """Method to signals when the list becomes a non extendable one, in the sense that no newcomers are allowed.
It requires an explicit check on append/extend methods"""
        raise Exception( "Calling abstract DownloadInterface.finish on %s" % self )

    # This is a final method
    def queue ( self , itemlist ) :
        for item in itemlist :
            self.push( item )

    def push ( self , item ) :
        raise Exception( "Calling abstract DownloadInterface.push on %s" % self )

    def __nonzero__ ( self ) :
        """Method to evaluate in boolean context the existence of available items.
Used in while loop context to enable element extraction"""
        raise Exception( "Calling abstract DownloadInterface.__nonzero_ on %s" % self )

    # This is a redefinition of PackageListInterface, to stress requirement of specific implemenation
    def __iter__ ( self ) :
        raise Exception( "Calling abstract DownloadInterface.__iter__ on %s" % self )


class AbstractDownloadList ( DownloadInterface ) :

    def start ( self ) :

        for pkg in self :
            self.started = True

            destname = os.path.join( self.repo.repo_path() , pkg['Filename'] )

            # FIXME : Perform this check while appending to download_pkgs ???
            if os.path.isfile( destname ) :
                if utils.integrity_check( destname , pkg ) is False :
                    os.unlink( destname )
                else :
                    continue
            else :
                path , name = os.path.split( destname )
                if not os.path.exists( path ) :
                    os.makedirs( path )

            if not self.repo.downloadRawFile ( pkg['Filename'] , destname ) :
                logger.warning( "Failure downloading file '%s'" % os.path.basename(pkg['Filename']) )

    def finish ( self ) :
        self.closed = True

class DownloadList ( list , AbstractDownloadList ) :

    # Avoid representation of full list
    def __repr__ ( self ) :
        return "<DownloadList items:%d>" % len(self)

    def __init__ ( self , repo ) :
        list.__init__( self )
        AbstractDownloadList.__init__( self , repo )

    def push ( self , item ) :
        if self.closed :
            raise Exception( "Trying to push into a closed queue" )
        list.append( self , item )

    def __iter__ ( self ) :
        if self.started :
            raise Exception( "Trying to iterate over a running list" )
        return list.__iter__( self )


import threading

class AbstractDownloadThread ( threading.Thread , DownloadInterface ) :

    def __init__ ( self , repo ) :
        # Check for methods required on the underlying container
        if not 'append' in dir(self) or not '__len__' in dir(self) :
            raise Exception ("Implementation of AbstractDownloadThread required sized objects with append method")
        self.cond = threading.Condition()
        threading.Thread.__init__( self , name=repo.name )
        DownloadInterface.__init__( self , repo )
        self.index = 0

    def finish(self):
        """Ends the main loop"""
        self.cond.acquire()
        try:
            self.closed=True
            # FIXME : Notification takes effect now or after release ???
            self.cond.notify()
        finally:
            self.cond.release()

    def __nonzero__ ( self ) :
        return self.index != len(self)

    def push ( self , item ) :
        """Adds an item to the download queue"""
        self.cond.acquire()
        try:
            if not self :
                # FIXME : Notification takes effect now or after release ???
                self.cond.notify()
            if self.closed :
                raise Exception( "Trying to push into a closed queue" )
            else :
                self.append( item )
        finally:
            self.cond.release()

    def run(self):
        """Main thread loop. Runs over the item list, downloading every file"""

        pkginfo = None
        __iter = self.__iter__()
        self.started = True
        while self.started:
            self.cond.acquire()
            if not self :
                if self.closed :
                   self.started = False
                   continue
                self.cond.wait()
            elif self.started :
                pkginfo = __iter.next()
            self.cond.release()
            if pkginfo :
                self.download_pkg( pkginfo )
                pkginfo = None
                self.index += 1

    def download_pkg ( self , pkg ) :

        destname = os.path.join( self.repo.repo_path() , pkg['Filename'] )

        # FIXME : Perform this check while appending to download_pkgs ???
        if os.path.isfile( destname ) :
            if utils.integrity_check( destname , pkg ) is False :
                os.unlink( destname )
            else :
                return
        else :
            path , name = os.path.split( destname )
            if not os.path.exists( path ) :
                os.makedirs( path )

        if not self.repo.downloadRawFile ( pkg['Filename'] , destname ) :
            logger.warning( "Failure downloading file '%s'" % os.path.basename(pkg['Filename']) )

class DownloadThread ( list , AbstractDownloadThread ) :
    """File download thread. It is build around a threaded list where files
are appended. Once the thread starts, the actual file download begins"""

    # Avoid representation of full list
    def __repr__ ( self ) :
        return "<DownloadThread(%s) items:%d>" % ( self.getName() , len(self) )

    def __hash__ ( self ) :
        return AbstractDownloadThread.__hash__( self )

    def __init__ ( self , repo ) :
        list.__init__( self )
        AbstractDownloadThread.__init__( self , repo )

    def __iter__ ( self ) :
        if self.started :
            raise Exception( "Trying to iterate over a running list" )
        return list.__iter__( self )


class MirrorRepository ( _repository ) :

    def new ( name ) :
        _config = config.read_mirror_config( name )
        if _config['type'] == "yum" :
            return yum_repository( _config )
        elif _config['type'] == "centos" :
            return centos_repository( _config )
        elif _config['type'] == "yum_upd" :
            return fedora_update_repository( _config )
        elif _config['type'] == "centos_upd" :
            return centos_update_repository( _config )
        elif _config['type'] == "deb" :
            return debian_repository( _config )
        elif _config['type'] == "feed" :
            return feed_repository( _config )
        elif _config['type'] == "yast2" :
            return yast2_repository( _config )
        elif _config['type'] == "yast2_update" :
            return yast2_update_repository( _config )
        else :
            Exception( "Unknown repository type '%s'" % _config['type'] )
    new = staticmethod( new )

    def __init__ ( self , config ) :
	_repository.__init__( self , config )
        self.repo_url = urljoin( "%s/" % config[ "url" ] , "" )
        self.mode = config[ "mode" ]
        self.params = config[ "params" ]
        self.filters = config[ "filters" ]

    def base_url ( self ) :
        raise Exception( "Calling an abstract method" )

    def metadata_path ( self , subrepo=None , partial=False ) :
        raise Exception( "Calling an abstract method" )

    def get_signed_metafile ( self , params , meta_file , sign_ext=None , keep=False ) :
        """
Verifies with gpg and/or downloads a metadata file. Return the full pathname
of metadata file on success and False if any error occur. In the signature
verification is not successfull, the local copy is removed and the file is
dowloaded into a temporary location. This behaviour can be disabled by setting
the keep option, and is usually done to avoid the break of already downloaded
repositories.

The returned file is always and off-tree temporary one except when the file
did already exists and signature was successfully verified. When working on
update mode, the special value True is returned to signal that no further
processing is required
"""

        release_file = os.path.join( self.repo_path() , meta_file )

        if params['usegpg'] and sign_ext :

            signature_file = self.downloadRawFile( meta_file + sign_ext )

            if not signature_file :
                logger.error( "Signature file for version '%s' not found." % ( self.version ) )
                return False

            if os.path.isfile( release_file ) :
                errstr = utils.gpg_error( signature_file , release_file )
                if errstr :
                    logger.warning( errstr )
                    # NOTE : The keep flag is a different approach to the behaviour wanted by update mode
                    if keep :
                        release_file = False
                    else :
                        logger.info( "os.unlink( %s )" % release_file )
                        os.unlink( release_file )
                else :
                    # FIXME : If we consider that our mirror is complete, it is safe to exit here
                    if self.mode == "update" :
                        logger.warning( "Metadata file unchanged, exiting" )
                        os.unlink( signature_file )
                        return True

        else :
            # If gpg is not enabled, the metafile is removed to force fresh download
            if os.path.isfile( release_file ) :
                if keep :
                    release_file = False
                else :
                    os.unlink( release_file )

        if release_file and not os.path.isfile( release_file ) :

            release_file = self.downloadRawFile( meta_file )

            if release_file :
                if params['usegpg'] and sign_ext :
                    errstr = utils.gpg_error( signature_file , release_file )
                    if errstr :
                        logger.error( errstr )
                        os.unlink( release_file )
                        release_file = False
            else :
                logger.error( "Release file for suite '%s' is not found." % ( self.version ) )

        if params['usegpg'] and sign_ext :
            os.unlink( signature_file )

        return release_file

    def build_local_tree( self ) :

        suite_path = self.repo_path()

        for subrepo in self.get_subrepos() :
            packages_path = self.metadata_path( subrepo , False )
            if not os.path.exists( os.path.join( suite_path , packages_path ) ) :
                os.makedirs( os.path.join( suite_path , packages_path ) )

    def get_download_list( self ) :
        return DownloadThread( self )

    def downloadRawFile ( self , remote , local=None ) :
        """Downloads a remote file to the local system.

        remote - path relative to repository base
        local - Optional local name for the file

        Returns the local file name or False if errors"""

        remote = urljoin( self.base_url() , remote ) 

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
            logger.error( "Exception : %s" % ex )
            os.close(handle)
            os.unlink(fname)
            return False
        return fname


class BuildRepository ( _repository ) :

    def new ( name ) :
        _config = config.read_build_config( name )
        if _config['type'] == "deb" :
            return debian_build_repository( _config )
        elif _config['type'] == "feed" :
            return feed_build_repository( _config , name )
        else :
            Exception( "Unknown repository build type '%s'" % _config['type'] )
    new = staticmethod( new )

    def __init__ ( self , config ) :
	_repository.__init__( self , config )


from yum import *

from debian import *

from feed import *

