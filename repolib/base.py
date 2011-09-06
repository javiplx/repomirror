
__all__ = [ 'MirrorRepository' , 'MirrorComponent' , 'BuildRepository' , 'snapshot_build_repository' ]

import os
import tempfile
import shutil , errno
import stat


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

        if not os.path.isdir( self.destdir ) :
            raise Exception( "Destination directory %s does not exists" % self.destdir )

    def repo_path ( self ) :
        raise Exception( "Calling an abstract method" )


class _mirror ( _repository ) :
    """Convenience class primarily created only to avoid moving download method into base _repository"""

    mode = "update"

    required = ( 'destdir' , 'type' , 'url' , 'version' )

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
        self.mirror_class = config[ "class" ]

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
        if not utils.download( remote , handle ) :
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
        self.repomd = None
        self.subrepos = {}

    def __str__ ( self ) :
        name = self.name
        if self.name != self.version :
            name += " %s" % self.version
        return name

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

    def get_metafile ( self , metafile , _params=None ) :
        """Verifies with gpg and/or downloads a metadata file.
Returns path to metadata file on success, and False if error occurs.
If signature verification fails, stored metadata is removed.

The returned value is an off-tree temporary path except when the metadata file
did already exists and verification succeeds, where the path to the stored
metadata is returned in 'init' mode and True in any other operation mode."""

        release_file = os.path.join( self.repo_path() , metafile )

        if self.sign_ext :

          signature_file = self.downloadRawFile( metafile + self.sign_ext )

          if not signature_file :
              repolib.logger.critical( "Signature file for version '%s' not found." % ( self.version ) )
              if _params['usegpg'] :
                  return False

          if _params['usegpg'] :

            if os.path.isfile( release_file ) :
                if not utils.gpg_verify( signature_file , release_file , repolib.logger.warning ) :
                    if self.mode != "keep" :
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
                if self.mode != "keep" :
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
           if isinstance( signature_file , str ) :
            self.safe_rename( signature_file , release_file + self.sign_ext )
          else :
            os.unlink( signature_file )

        return release_file

    def safe_rename ( self , src , dst , chmod=False ) :
        try :
            os.rename( src , dst )
        except OSError , ex :
            if ex.errno != errno.EXDEV :
                repolib.logger.critical( "OSError: %s" % ex )
                sys.exit(1)
            shutil.move( src , dst )
        if chmod :
            mode = stat.S_IWUSR | stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH
            os.chmod( dst , mode )

    def info ( self , release_file , cb ) :
        raise Exception( "Calling an abstract method" )

    def write_master_file ( self , metafiles ) :
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
        self.compname = compname
        self.repomd = None

    def __str__ ( self ) :
        return "%s" % self.compname

    def get_metafile( self , metafile , _params=None ) :
        """Verifies checksums and optionally downloads metadata files for subrepo.
Returns the full pathname for the file in its final destination or False when
error ocurrs. When the repository is in update mode, True is returned to signal
that the current copy is ok.
"""
        raise Exception( "Calling an abstract method" )

    def match_filters( self , pkginfo , filters ) :
        raise Exception( "Calling an abstract method" )

    def get_package_list ( self , fd , _params , filters , depiter=5 ) :
        raise Exception( "Calling an abstract method" )

    def verify( self , filename , _name , release , params ) :
        raise Exception( "Calling an abstract method" )

    def pkg_list( self ) :
        return PackageList()


class BuildRepository ( _repository ) :

    def new ( name , input=None ) :
        if input :
            if name in repolib.config.get_all_build_repos() :
                raise Exception( "already exists" )
            if not isinstance(input,dict) :
                raise Exception( "Given '%s' object, only dictionaries allowed" % input.__class__.__name__ )
            _config = repolib.config.read_build_config( name , input )
        else :
            _config = repolib.config.read_build_config( name )
        if _config['type'] == "deb" :
            return repolib.debian_build_repository( _config , name )
        elif _config['type'] == "apt" :
            return repolib.debian_build_apt( _config , name )
        elif _config['type'] == "feed" :
            return repolib.feed_build_repository( _config , name )
        elif _config['type'] == "yum" :
            return repolib.yum_build_repository( _config , name )
        elif _config['type'] == "snapshot" :
            return repolib.snapshot_build_repository( _config , name )
        else :
            raise Exception( "Unknown repository build type '%s'" % _config['type'] )
    new = staticmethod( new )

    def __init__ ( self , config , name ) :
        _repository.__init__( self , config )
        self.name = name
        self.detached = config['detached']
        self.source = config['source']
        self.force = config['force']

    def repo_path ( self ) :
        if self.detached :
            return self.destdir
        return os.path.join( self.destdir , self.name )


class snapshot_build_repository ( BuildRepository ) :

    def build ( self ) :
	if self.force :
	    if self.source :
                if os.path.isdir( self.repo_path() ) :
                    raise Exception( "Snapshot destination directory '%s' already dexists" % self.repo_path() )
            os.mkdir( self.repo_path() )

        source = repolib.MirrorRepository.new( self.source )
        source.set_mode( "keep" )

        meta_files = source.get_metafile()
        if meta_files.values().count( True ) != len(meta_files) :
            for file in set(meta_files.values()) :
                if not isinstance(file,bool) :
                    os.unlink( file )
            if source.sign_ext and source.params['usegpg'] :
                raise Exception( "Source repository '%s' is not up to date" % self.source )
            for subrepo in meta_files :
                meta_files[subrepo] = True

        src = source.repo_path()
        dst = self.repo_path()

        if source.repomd :
            src = os.path.join( source.repo_path() , source.repomd )
            dst = os.path.join( self.repo_path() , source.repomd )
            os.makedirs( os.path.dirname( dst ) )
            shutil.copy( src , dst )
            if source.sign_ext and source.params['usegpg'] :
                shutil.copy( src + source.sign_ext , dst + source.sign_ext )

        for subrepo in source.subrepos.values() :
            srcdir = os.path.join( subrepo.repo_path() , subrepo.metadata_path() )
            dstdir = os.path.dirname( os.path.join( self.repo_path() , subrepo.metadata_path() ) )
            # debian-installer share directory with standard component, so we must check
            if not os.path.isdir( os.path.dirname( dstdir ) ) :
                os.makedirs( os.path.dirname( dstdir ) )
            shutil.copytree( srcdir , dstdir )


