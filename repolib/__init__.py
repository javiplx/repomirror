
import os

import urllib2

import config , utils


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

    def get_download_list( self ) :
        raise Exception( "Calling an abstract method" )


class DownloadList ( list ) :

    def rewind ( self ) :
        pass

    def flush ( self ) :
        pass


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

    def get_signed_metafile ( self , params , meta_file , sign_ext=".asc" ) :

        release_file = os.path.join( self.repo_path() , meta_file )

        if params['usegpg'] :

            signature_file = self.downloadRawFile( meta_file + sign_ext )

            if not signature_file :
                logger.error( "Signature file for version '%s' not found." % ( self.version ) )
                return

            if os.path.isfile( release_file ) :
                errstr = utils.gpg_error( signature_file , release_file )
                if errstr :
                    logger.warning( errstr )
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
                os.unlink( release_file )

        if not os.path.isfile( release_file ) :

            release_file = self.downloadRawFile( meta_file )

            if release_file :
                if params['usegpg'] :
                    errstr = utils.gpg_error( signature_file , release_file )
                    if errstr :
                        logger.error( errstr )
                        os.unlink( release_file )
                        release_file = False
            else :
                logger.error( "Release file for suite '%s' is not found." % ( self.version ) )

        if params['usegpg'] :
            os.unlink( signature_file )

        return release_file

    def build_local_tree( self ) :

        suite_path = self.repo_path()

        for subrepo in self.get_subrepos() :
            packages_path = self.metadata_path( subrepo , False )
            if not os.path.exists( os.path.join( suite_path , packages_path ) ) :
                os.makedirs( os.path.join( suite_path , packages_path ) )

    def downloadRawFile ( self , remote , local=None ) :
        """Downloads a remote file to the local system.

        remote - path relative to repository base
        local - Optional local name for the file

        Returns the local file name"""

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

