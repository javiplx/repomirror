
__all__ = [ 'MirrorRepository' , 'MirrorComponent' , 'BuildRepository' ]

import os
import tempfile
import shutil , errno

import urllib2


import repolib
import utils
from lists import *

class _repository :

    def new ( name ) :
        raise Exception( "Calling an abstract method" )

    def __init__ ( self , config ) :

        self.name = config.name

	self.destdir = config[ "destdir" ]
        self.version = config[ "version" ]

        self.architectures = config[ "architectures" ]

        if not os.path.isdir( self.destdir ) :
            raise Exception( "Destination directory %s does not exists" % self.destdir )

    def repo_path ( self ) :
        raise Exception( "Calling an abstract method" )


class _mirror ( _repository ) :
    """Convenience class primarily created only to avoid moving download method into base _repository"""

    # (update|init) - decides if we stop processing for unchanged metadata files
    mode = "update"

    required = ( 'destdir' , 'type' , 'url' , 'version' , 'architectures' )

    def __init__ ( self , config ) :
        missing = []
        for key in self.required :
            if not config.get(key) :
                missing.append( key )
        if missing :
            raise Exception( "Broken '%s' configuration : missing %s." % ( config.name , ", ".join(missing) ) )

	_repository.__init__( self , config )
        self.repo_url = config[ "url" ]
        self.params = config[ "params" ]
        self.filters = config[ "filters" ]

    def repo_path ( self ) :
        return os.path.join( self.destdir , self.name )

    def base_url ( self ) :
        return self.repo_url

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
            repolib.logger.error( "Exception : %s" % ex )
            os.close(handle)
            os.unlink(fname)
            return False
        return fname

class MirrorRepository ( _mirror ) :

    def new ( name ) :
        _config = repolib.config.read_mirror_config( name )
        if _config['type'] == "yum" :
            return repolib.yum_repository( _config )
        elif _config['type'] == "fedora" :
            return repolib.fedora_repository( _config )
        elif _config['type'] == "centos" :
            return repolib.centos_repository( _config )
        elif _config['type'] == "fedora_upd" :
            return repolib.fedora_update_repository( _config )
        elif _config['type'] == "centos_upd" :
            return repolib.centos_update_repository( _config )
        elif _config['type'] == "deb" :
            return repolib.debian_repository( _config )
        elif _config['type'] == "feed" :
            return repolib.feed_repository( _config )
        else :
            raise Exception( "Unknown repository type '%s'" % _config['type'] )
    new = staticmethod( new )

    sign_ext = False

    def __init__ ( self , config ) :
	_mirror.__init__( self , config )
        self.subrepos = {}

    def set_mode ( self , mode ) :
        for subrepo in self.subrepos.values() :
            subrepo.mode = mode
        self.mode = mode

    def select_component ( self , compname ) :
        names = filter( compname.__ne__ , self.subrepos.keys() )
        map( self.subrepos.pop , names )
        if self.subrepos :
            return self.subrepos[compname]
        raise Exception( "subrepo %s does not exists" % compname )

    def get_metafile ( self , metafile , _params=None , keep=False ) :
        """Verifies with gpg and/or downloads a metadata file.
Returns path to metadata file on success, and False if error occurs.
If signature verification fails, stored metadata is removed.

The returned value is an off-tree temporary path except when the metadata file
did already exists and verification succeeds. If this is the case, True is
returned or the path to stored metadata if running in 'init' mode.

The 'keep' flag avoids removal of stored copies if verification fails, while
forcing download of current metadata. This behaviour is intended to avoid
breaking already downloaded repositories when only checking whether they
are up to date."""

        release_file = os.path.join( self.repo_path() , metafile )

        if self.sign_ext :

          signature_file = self.downloadRawFile( metafile + self.sign_ext )

          if not signature_file :
                repolib.logger.critical( "Signature file for version '%s' not found." % ( self.version ) )
                return False

          if _params['usegpg'] :

            if os.path.isfile( release_file ) :
                if not utils.gpg_verify( signature_file , release_file , repolib.logger.warning ) :
                    if not keep :
                        os.unlink( release_file )
                        os.unlink( release_file + self.sign_ext )
                    release_file = ""
                else :
                    if self.mode != "init" :
                        repolib.logger.info( "Existing metadata file is valid, skipping" )
                        os.unlink( signature_file )
                        return True

        # If gpg is not enabled, metafile is removed to force fresh download
        if not self.sign_ext or not _params['usegpg'] :
            if os.path.isfile( release_file ) :
                if not keep :
                    os.unlink( release_file )
                    if self.sign_ext : os.unlink( release_file + self.sign_ext )
                release_file = ""


        if not os.path.isfile( release_file ) :

            release_file = self.downloadRawFile( metafile )

            if release_file :
                if self.sign_ext and _params['usegpg'] :
                    if not utils.gpg_verify( signature_file , release_file , repolib.logger.error ) :
                        os.unlink( release_file )
                        release_file = False

        if self.sign_ext :
          if isinstance(release_file,str) :
            self.safe_rename( signature_file , release_file + self.sign_ext )
          else :
            os.unlink( signature_file )

        return release_file

    def safe_rename ( self , src , dst ) :
        try :
            os.rename( src , dst )
        except OSError , ex :
            if ex.errno != errno.EXDEV :
                repolib.logger.critical( "OSError: %s" % ex )
                sys.exit(1)
            shutil.move( src , dst )

    def info ( self , release_file , cb ) :
        raise Exception( "Calling an abstract method" )

    def write_master_file ( self , release_file ) :
        raise Exception( "Calling an abstract method" )

    def build_local_tree( self ) :

        for subrepo in self.subrepos.values() :
            packages_path = os.path.join( subrepo.repo_path() , subrepo.metadata_path() )
            if not os.path.exists( packages_path ) :
                os.makedirs( packages_path )

    def get_download_list( self ) :
        return DownloadThread( self )
        return DownloadList( self )


class MirrorComponent ( _mirror ) :

    def new ( name , _config ) :
        if _config['type'] == "yum" :
            return repolib.YumComponent( name , _config )
        elif _config['type'] == "fedora" :
            return repolib.FedoraComponent( name , _config )
        elif _config['type'] == "fedora_upd" :
            return repolib.FedoraUpdateComponent( name , _config )
        elif _config['type'] == "centos" :
            return repolib.CentosComponent( name , _config )
        elif _config['type'] == "centos_upd" :
            return repolib.CentosUpdateComponent( name , _config )
        elif _config['type'] == "deb" :
            return repolib.DebianComponent( name , _config )
        elif _config['type'] == "feed" :
            return repolib.SimpleComponent( name , _config )
        else :
            raise Exception( "Unknown component type '%s'" % _config['type'] )
    new = staticmethod( new )

    def __init__ ( self , compname , config ) :
        _mirror.__init__( self , config )
        self.architectures = [ compname ]

    def __str__ ( self ) :
        return "%s" % self.architectures[0]

    def get_metafile( self , metafile , _params=None , download=True ) :
        """Verifies checksums and optionally downloads metadata files for subrepo.
Returns the full pathname for the file in its final destination or False when
error ocurrs. When the repository is in update mode, True is returned to signal
that the current copy is ok.
"""
        raise Exception( "Calling an abstract method" )

    def match_filters( self , pkginfo , filters ) :
        raise Exception( "Calling an abstract method" )

    def get_package_list ( self , fd , _params , filters ) :
        raise Exception( "Calling an abstract method" )

    def verify( self , filename , _name , release , params ) :
        raise Exception( "Calling an abstract method" )

    def pkg_list( self ) :
        return PackageList()


class BuildRepository ( _repository ) :

    def new ( name ) :
        _config = repolib.config.read_build_config( name )
        if _config['type'] == "deb" :
            return repolib.debian_build_repository( _config , name )
        elif _config['type'] == "apt" :
            return repolib.debian_build_apt( _config , name )
        elif _config['type'] == "feed" :
            return repolib.feed_build_repository( _config , name )
        elif _config['type'] == "yum" :
            return repolib.yum_build_repository( _config , name )
        else :
            raise Exception( "Unknown repository build type '%s'" % _config['type'] )
    new = staticmethod( new )

    def __init__ ( self , config , name ) :
        _repository.__init__( self , config )
        self.name = name
        self.detached = config['detached']

    def repo_path ( self ) :
        if self.detached :
            return self.destdir
        return os.path.join( self.destdir , self.name )


