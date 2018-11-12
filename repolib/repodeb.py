
import debian.deb822
import gnupg

import os , sys
import stat


import config


import repolib
from lists.repodeb import *


class debian_repository ( repolib.MirrorRepository ) :

    sign_ext = ".gpg"

    def __init__ ( self , config ) :
        repolib.MirrorRepository.__init__( self , config )

        self.architectures = config.get( "architectures" , [ "i386" , "amd64" ] )

        # Stored for later use during Release file checks
        self.__config = config

        self.components = config.get( "components" , [] )

        if self.components :
            self.__set_components( config )

        # Not strictly required, but kept as member for convenience
        self.repomd = os.path.join( self.metadata_path() , "Release" )

        if self.params['pkgvflags'] != repolib.SKIP_NONE :
            repolib.logger.warning( "Some checks skipped for %s" % self.name )

    def dump_conf ( self ) :
        data = repolib.MirrorRepository.dump_conf()
        data.update( { 'subdir':self.subdir , 'components':self.components } )
        if self.components :
            data['components'] = " ".join(self.components)

    def __set_components ( self , config ) :
        for archname in self.architectures :
            for compname in self.components :
                subrepo = repolib.MirrorComponent.new( ( archname , compname ) , config )
                self.subrepos[subrepo] = subrepo

    def __str__ ( self ) :
        # FIXME : consider suite, codename or real version, maybe coming from Release
        return self.version

    def metadata_path ( self , partial=False ) :
        path = ""
        if not partial :
            path = "dists/%s" % self.version
        return path

    def __subrepo_dict ( self , value ) :
        d = {}
        for k in self.subrepos :
            d[k] = value
        return d

    def get_metafile ( self , _params=None ) :

        params = self.params
        if _params : params.update( _params )

        release_file = repolib.MirrorRepository.get_metafile( self , self.repomd , params )

        if not release_file :
            repolib.logger.error( "Metadata for '%s' not found" % self.version )
            return self.__subrepo_dict( release_file )
        elif release_file is True :
            return self.__subrepo_dict( True )

        repolib.logger.info( "Content verification of metafile %s" % release_file )
        release = debian.deb822.Release( sequence=open( release_file ) )


        # Although both names and suites can be used within sources.list, we
        # will enforce mirroring based on codenames
        # FIXME : Is sensible to use in any way the version from Release?

        version = self.version.split("/").pop(0).split("-").pop(0)
        suite = release['Suite']
        codename = release['Codename']

        if suite != codename and suite == version :
            repolib.logger.error( "You have supplied suite '%s'. Please use codename '%s' instead" % ( self.version, codename ) )
            os.unlink( release_file )
            return self.__subrepo_dict( False )

        if codename != version :
            repolib.logger.error( "Requested version '%s' does not match with codename from Release file ('%s')" % ( self.version, codename ) )
            os.unlink( release_file )
            return self.__subrepo_dict( False )


        # Neither architectures nor components are required. If defined,
        # the configured values are verified to avoid mismathes.
        # If not configured, values from Release file are taken.

        release_archs = release['Architectures'].split()
        for arch in self.architectures :
            if arch not in release_archs :
                repolib.logger.error( "Architecture '%s' is not available ( %s )" % ( arch , " ".join(release_archs) ) )
                # FIXME : only this architecture should get marked as unavailable
                os.unlink( release_file )
                return self.__subrepo_dict( False )

        if release.has_key( "Components" ) :
            # NOTE : security and volatile repositories prepend a string to the actual component name
            release_comps = map( lambda s : s.rsplit("/").pop() , release['Components'].split() )

            if self.components :
                for comp in self.components :
                    if comp.endswith( "/debian-installer" ) :
                        comp = comp[:-17]
                    if comp not in release_comps :
                        repolib.logger.error( "Component '%s' is not available ( %s )" % ( comp , " ".join(release_comps) ) )
                        # FIXME : only this component should get marked as unavailable
                        os.unlink( release_file )
                        return self.__subrepo_dict( False )
            else :
                repolib.logger.warning( "No components specified, selected all components from Release file" )
                self.components.extend( release_comps )
                self.__set_components( self.__config )
                self.set_mode( self.mode )

        elif self.components :
            repolib.logger.error( "There is no components entry in Release file for '%s', please fix your configuration" % self.version )
            os.unlink( release_file )
            return self.__subrepo_dict( False )
        else :
            repolib.logger.warning( "Component list undefined, setting to main" )
            self.components = ( "main" ,)
            self.__set_components( self.__config )
            self.set_mode( self.mode )

        # Remove temporarily stored items
        if self.components :
            del self.__config

        return self.__subrepo_dict( release_file )

    def write_master_file ( self , metafiles ) :

        tempfiles = set( metafiles.values() )
        tempfile = tempfiles.pop()

        if tempfiles :
            raise Exception( "Too many different Release files returned" )

        if self.mode == "keep" and tempfile is not True :
            return self.__subrepo_dict( tempfile )

        local = os.path.join( self.repo_path() , self.repomd )

        if not isinstance(tempfile,bool) and not os.path.exists( local ) :

            self.safe_rename( tempfile , local , True )

            if self.sign_ext and not os.path.isfile( local + self.sign_ext ) and os.path.isfile( tempfile + self.sign_ext ):
                self.safe_rename( tempfile + self.sign_ext , local + self.sign_ext , True )

        return self.__subrepo_dict( local )

    def build_local_tree( self ) :
        repolib.MirrorRepository.build_local_tree( self )
        if self.mirror_class == "cache" :
            pooldir = os.path.join( self.repo_path() , "pool" )
            if not os.path.isdir( pooldir ) :
                os.mkdir( pooldir )
            os.chown( pooldir , config.web['uid'] , config.web['gid'] )

    def info ( self , metafile , cb ) :

        release_file = set(metafile.values()).pop()
        if release_file is True :
            release_file = os.path.join( self.repo_path() , self.repomd )
        release = debian.deb822.Release( sequence=open( release_file ) )

        # Some Release files hold no 'version' information
        if not release.has_key( 'Version' ) :
            release['Version'] = ""
        else :
            release['Version'] += " "

        # Some Release files hold no 'Date' information
        if not release.has_key( 'Date' ) :
            release['Date'] = ""
        else :
            release['Date'] = " , %s" % release['Date']

        cb( "Mirroring %(Label)s %(Version)s(%(Codename)s)" % release )
        cb( "%(Origin)s %(Suite)s%(Date)s" % release )
        cb( "Subrepos : %s" % " ".join( map( str , self.subrepos.keys() ) ) )

    def get_download_list( self ) :
        return DebianDownloadFile( self )

from feed import SimpleComponent , feed_build_repository , packages_build_repository

class DebianComponent ( SimpleComponent ) :

    def __init__ ( self , ( arch , comp ) , config ) :
        SimpleComponent.__init__( self , "%s/%s" % ( arch , comp ) , config )
        self.archname , self.component = arch, comp
        self.repomd = os.path.join( self.metadata_path() , "Release" )

    def metadata_path ( self , partial=False ) :
        path = "%s/binary-%s/" % ( self.component , self.archname )
        if not partial :
            path = "dists/%s/%s" % ( self.version , path )
        return path

    def verify( self , filename , _name , release , params ) :
        _item = {}
        for type in ( 'MD5Sum' , 'SHA1' , 'SHA256' ) :
            if release.has_key(type) :
                for item in release[type] :
                    if item['name'] == _name :
                        _item.update( item )
        if _item :
            if repolib.integrity_check( filename , _item , params['pkgvflags'] ) :
                return True
            return False

        else :
            repolib.logger.error( "Checksum for file '%s' not found, exiting." % _name ) 
            return False

    def get_metafile( self , metafile , _params=None ) :

        params = self.params
        if _params : params.update( _params )

        masterfile = metafile[self]

        if isinstance(masterfile,bool) :
            raise Exception( "Calling %s.get_metafile( %s )" % ( self , metafile ) )

        release = debian.deb822.Release( sequence=open( masterfile ) )

        if self.mode in ( "init" , "metadata" ) :
          # NOTE : ubuntu has no Release file on installer components
          localname = os.path.join( self.repo_path() , self.repomd )

          if os.path.isfile( localname ) :
            _name = "%sRelease" % self.metadata_path(True)
            if self.verify( localname , _name , release , params ) :
                repolib.logger.info( "Local copy of '%s' is up-to-date, skipping." % _name )
            else :
                os.unlink( localname )

          if not os.path.isfile( localname ) :
            repolib.logger.info( "No local Release file exist for %s. Downloading." % self )
            url = "%sRelease" % self.metadata_path()
            if self.downloadRawFile( url , localname ) :
                _name = "%sRelease" % self.metadata_path(True)
                if not self.verify( localname , _name , release , params ) :
                    os.unlink( localname )
                    repolib.logger.warning( "No valid Release file found for %s" % self )

        localname = False

        for ( extension , read_handler ) in config.mimetypes.iteritems() :

            _name = "%sPackages%s" % ( self.metadata_path() , extension )
            localname = os.path.join( self.repo_path() , _name )

            if os.path.isfile( localname ) :
                _name = "%sPackages%s" % ( self.metadata_path(True) , extension )
                if self.verify( localname , _name , release , params ) :
                    if self.mode == "init" :
                        break
                    repolib.logger.info( "Local copy of '%s' is up-to-date, skipping." % _name )
                    return True
                elif self.mode == "keep" :
                    # FIXME : could happen that another compression is OK
                    return False
                os.unlink( localname )

        else :

          localname = False
          if self.mode != "keep" :
            repolib.logger.info( "No local Packages file exist for %s. Downloading." % self )
            localname = SimpleComponent.get_metafile( self , release , _params )
            if not isinstance(localname,bool) :
               classname = "%s" % localname.__class__
               if str(self).endswith("/debian-installer") and classname != "gzip.GzipFile" :
                   repolib.logger.info( "Force download of Packages.gz for installer components" )

                   url = "%sPackages%s" % ( self.metadata_path() , ".gz" )
                   _localname = os.path.join( self.repo_path() , url )

                   if self.downloadRawFile( url , _localname ) :
                       _name = "%sPackages%s" % ( self.metadata_path(True) , ".gz" )
                       if not self.verify( _localname , _name , release , params ) :
                           os.unlink( _localname )


        if isinstance(localname,str) :
            return read_handler( localname )

        return localname

    def pkg_list( self ) :
        return DebianPackageFile()

    def forward( self , fd ) :
        pass


class debian_build_repository ( feed_build_repository ) :

    valid_extensions = ( ".deb" ,)

class debian_component_repository ( packages_build_repository ) :

    def __init__ ( self , parent , arch , compname ) :
        self.version = parent.version
        self.architecture , self.component = arch , compname
        self.archfilters = ( "all" , arch )

        output_path = os.path.join( parent.repo_path() , self.metadata_path() )
        if not os.path.isdir( output_path ) : os.makedirs( output_path )

        packages_build_repository.__init__( self , parent )
        self.base_path = os.path.join( self.repo_path , "pool" , compname )
        self.recursive = True

    def metadata_path ( self , partial=False ) :
        path = "%s/binary-%s/" % ( self.component , self.architecture )
        if not partial :
            path = "dists/%s/%s" % ( self.version , path )
        return path

    def extract_filename ( self , name ) :
        return name.replace( "%s/" % self.repo_path , "" )

    def build ( self ) :
        packages_build_repository.build( self )

    def post_build ( self ) :
        packages_build_repository.post_build( self )
        self.build_release()

    def build_release ( self ) :
        output_path = os.path.join( self.repo_path , self.metadata_path() )
        filename = os.path.join( output_path , "Release" )
        fd = open( filename , 'w' )
        fd.write( "Version: %s\n" % self.version )
        fd.write( "Component: %s\n" % self.component )
        fd.write( "Architecture: %s\n" % self.architecture )
        fd.close()


class debian_build_apt ( repolib.BuildRepository ) :

    required = ( 'destdir' , 'type' , 'url' , 'version' , 'architectures' , 'components' )

    valid_extensions = ( ".deb" ,)

    def __init__ ( self , config , name ) :

        repolib.BuildRepository.__init__( self , config , name )

        if not config.has_key( "architectures" ) :
            raise Exception( "Broken configuration : no architecture defined" )

        self.architectures = config["architectures"]

        self.components = []
        if config['components'] != ["-"] :
            self.components.extend( config['components'] )

	if not os.path.isdir( self.repo_path() ) :
            raise Exception( "Repository directory %s does not exists" % self.repo_path() )

        self.gpgkey = config.get('usegpg', False)
        self.gpgpass = config.get('gpgpass')

        self.feeds = []
        for arch in self.architectures :
            for compname in self.components :
                self.feeds.append( debian_component_repository(self,arch,compname) )

    def metadata_path ( self , partial=False ) :
        path = ""
        if not partial :
            path = "dists/%s" % self.version
        return path

    def build ( self ) :
        for feed in self.feeds :
            feed.build()
        self.post_build()

    def post_build ( self ) :
        self.build_release()

    def build_release ( self ) :
        release_file =  os.path.join( self.repo_path() , self.metadata_path() , "Release" )
        fd = open( release_file , 'w' )
        fd.write( "Version: %s\n" % self.version )
        fd.write( "Architectures: %s\n" % " ".join(self.architectures) )
        fd.write( "Components: %s\n" % " ".join(self.components) )
        labels = { 'md5sum':'MD5Sum' , 'sha1':'SHA1' , 'sha256':'SHA256' }
        for type in labels :
            fd.write( "%s:\n"  % labels[type] )
            for feed in self.feeds :
                for extension in config.mimetypes :
                    basename = "Packages" + extension
                    packages = os.path.join( feed.metadata_path(True) , basename )
                    _packages = os.path.join( feed.repo_path , feed.metadata_path() , basename )
                    cksum = repolib.cksum_handles[type]( _packages )
                    fd.write( "  %s  %15s %s\n" % ( cksum , os.stat(_packages).st_size , packages ) )
        fd.close()

        if self.gpgkey :
            gpg = gnupg.GPG()
            print gpg.sign_file(open(release_file, 'rb'), keyid=self.gpgkey, passphrase=self.gpgpass, detach=True, output=release_file+'.gpg')

