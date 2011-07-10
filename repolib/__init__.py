
import os

import urllib2

import socket
socket.setdefaulttimeout(5)

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


class mirror_repository ( _repository ) :
    """Convenience class primarily created only to avoid moving download method into base _repository"""

    def __init__ ( self , config ) :
	_repository.__init__( self , config )
        self.repo_url = config[ "url" ]
        self.mode = config[ "mode" ]
        self.params = config[ "params" ]
        self.filters = config[ "filters" ]

    def base_url ( self ) :
        raise Exception( "Calling an abstract method" )

    def metadata_path ( self , partial=False ) :
        raise Exception( "Calling an abstract method" )

    def downloadRawFile ( self , remote , local=None ) :
        """Downloads a remote file to the local system.

        remote - path relative to repository base
        local - Optional local name for the file

        Returns the local file name or False if errors"""

        remote = utils.urljoin( self.base_url() , remote ) 

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


class MirrorRepository ( mirror_repository ) :

    def new ( name ) :
        _config = config.read_mirror_config( name )
        if _config['type'] == "yum" :
            return yum_repository( _config )
        elif _config['type'] == "fedora" :
            return fedora_repository( _config )
        elif _config['type'] == "centos" :
            return centos_repository( _config )
        elif _config['type'] == "fedora_upd" :
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
	mirror_repository.__init__( self , config )
        self.subrepos = []

    def get_master_file ( self , params , keep=False ) :
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
                        release_file = ""
                    else :
                        os.unlink( release_file )
                else :
                    # FIXME : If we consider that our mirror is complete, it is safe to exit here
                    if self.mode == "update" :
                        logger.info( "Existing metadata file is valid, skipping" )
                        os.unlink( signature_file )
                        return True

        else :
            # If gpg is not enabled, the metafile is removed to force fresh download
            if os.path.isfile( release_file ) :
                if keep :
                    release_file = ""
                else :
                    os.unlink( release_file )

        if not os.path.isfile( release_file ) :

            release_file = self.downloadRawFile( meta_file )

            if release_file :
                if params['usegpg'] and sign_ext :
                    errstr = utils.gpg_error( signature_file , release_file )
                    if errstr :
                        logger.error( errstr )
                        os.unlink( release_file )
                        release_file = False

        if params['usegpg'] and sign_ext :
            os.unlink( signature_file )

        return release_file

    def info ( self , release_file ) :
        raise Exception( "Calling an abstract method" )

    def write_master_file ( self , release_file ) :
        raise Exception( "Calling an abstract method" )

    def build_local_tree( self ) :

        suite_path = self.repo_path()

        for subrepo in self.subrepos :
            packages_path = os.path.join( suite_path , subrepo.metadata_path() )
            if not os.path.exists( packages_path ) :
                os.makedirs( packages_path )

    def get_download_list( self ) :
        return DownloadThread( self )


class MirrorComponent ( mirror_repository ) :

    def __init__ ( self , config , compname ) :
        mirror_repository.__init__( self , config )
        self.architectures = [ compname ]

    def __str__ ( self ) :
        return "%s" % self.architectures[0]

    def arch( self ) :
        raise Exception( "Calling an abstract method" )

    def check_packages_file( self , metafile , _params , download=True ) :
        raise Exception( "Calling an abstract method" )

    def match_filters( self , pkginfo , filters ) :
        raise Exception( "Calling an abstract method" )

    def get_package_list ( self , fd , _params , filters ) :
        raise Exception( "Calling an abstract method" )

    def verify( self , filename , _name , release , params ) :
        raise Exception( "Calling an abstract method" )

    def get_download_list( self ) :
        return DownloadThread( self )


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

from yum import *

from debian import *

from feed import *

