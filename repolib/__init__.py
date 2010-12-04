
import os

import urllib2

import repoutils


import socket
socket.setdefaulttimeout(5)

urljoin = urllib2.urlparse.urljoin

def unsplit ( scheme , server , path ) :
    urltuple = ( scheme , server , path , None , None )
    return urllib2.urlparse.urlunsplit( urltuple )

def downloadRawFile ( remote , local=None , base_url=None ) :
    """Downloads a remote file to the local system.

    remote - URL
    local - Optional local name for the file

    Returns the local file name"""

    if base_url :
        remote = urljoin( base_url , remote ) 

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


import logging

console = logging.StreamHandler()
formatter = logging.Formatter("%(levelname)s : %(message)s")
console.setFormatter(formatter)

logger = logging.getLogger()
logger.addHandler( console )


def instantiate_repo ( config , name=False ) :
    repo = None
    if name is False :
        if config['type'] == "yum" :
            repo = yum_repository( config )
        elif config['type'] == "centos" :
            repo = centos_repository( config )
        elif config['type'] == "yum_upd" :
            repo = fedora_update_repository( config )
        elif config['type'] == "centos_upd" :
            repo = centos_update_repository( config )
        elif config['type'] == "deb" :
            repo = debian_repository( config )
        elif config['type'] == "yast2" :
            repo = yast2_repository( config )
        elif config['type'] == "yast2_update" :
            repo = yast2_update_repository( config )
        else :
            logger.error( "Unknown repository type '%s'" % config['type'] )
    else :
        if config['type'] == "deb" :
            repo = debian_build_repository( config )
        elif config['type'] == "feed" :
            repo = feed_build_repository( config , name )
        else :
            logger.error( "Unknown repository build type '%s'" % config['type'] )
    return repo


class _repository :

    def __init__ ( self , config ) :

	self.destdir = config[ "destdir" ]
        self.version = config[ "version" ]

        self.architectures = config[ "architectures" ]

        if not os.path.isdir( self.destdir ) :
            raise Exception( "Destination directory %s does not exists" % self.destdir )

    def repo_path ( self ) :
        raise Exception( "Calling an abstract method" )


class abstract_repository ( _repository ) :

    def __init__ ( self , config ) :
	_repository.__init__( self , config )
        self.repo_url = urljoin( "%s/" % config[ "url" ] , "" )
        self.params = config[ "params" ]

    def base_url ( self ) :
        raise Exception( "Calling an abstract method" )

    def metadata_path ( self , subrepo=None , partial=False ) :
        raise Exception( "Calling an abstract method" )

    def get_signed_metafile ( self , params , meta_file , sign_ext=".asc" ) :

        local_file = os.path.join( self.repo_path() , meta_file )

        if params['usegpg'] :

            signature_file = self._retrieve_file( urljoin( self.base_url() , meta_file + sign_ext ) )

            if not signature_file :
                logger.error( "Signature file for version '%s' not found." % ( self.version ) )
                return

            if os.path.isfile( local_file ) :
                errstr = repoutils.gpg_error( signature_file , local_file )
                if errstr :
                    logger.warning( errstr )
                    os.unlink( local_file )
                else :
                    os.unlink( signature_file )
                    # FIXME : If we consider that our mirror is complete, it is safe to exit here
                    if params['mode'] == "update" :
                        logger.warning( "Metadata file unchanged, exiting" )
                        return True
                    return local_file

        else :
            if os.path.isfile( local_file ) :
                os.unlink( local_file )

        # FIXME : produce error if we reach this point with existing local_file
        if not os.path.isfile( local_file ) :

            release_file = self._retrieve_file( urljoin( self.base_url() , meta_file ) )

            if not release_file :
                logger.error( "Release file for suite '%s' is not found." % ( self.version ) )
                if params['usegpg'] :
                    os.unlink( signature_file )
                return

            if params['usegpg'] :
                errstr = repoutils.gpg_error( signature_file , release_file )
                os.unlink( signature_file )
                if errstr :
                    logger.error( errstr )
                    os.unlink( release_file )
                    return

        return release_file

    def build_local_tree( self ) :

        suite_path = self.repo_path()

        for subrepo in self.get_subrepos() :
            packages_path = self.metadata_path( subrepo , False )
            if not os.path.exists( os.path.join( suite_path , packages_path ) ) :
                os.makedirs( os.path.join( suite_path , packages_path ) )

    def _retrieve_file ( self , location , localname=None ) :

        try :
            filename  = downloadRawFile( location , localname )
        except urllib2.URLError , ex :
            logger.error( "Exception : %s" % ex )
            return
        except urllib2.HTTPError , ex :
            logger.error( "Exception : %s" % ex )
            return

        return filename

    def get_download_list( self ) :
        return []


class abstract_build_repository ( _repository ) :

    def __init__ ( self , config ) :
	_repository.__init__( self , config )


from yum import *

from debian import *

from feed import *

