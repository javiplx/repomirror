
import debian_bundle.deb822 , debian_bundle.debian_support

import os , sys
import stat


import config , utils


import repolib
from lists.debian import *


class debian_repository ( repolib.MirrorRepository ) :

    sign_ext = ".gpg"

    def __init__ ( self , config ) :
        repolib.MirrorRepository.__init__( self , config )

        # Stored for later use during Release file checks
        self.components = config.get( "components" , None )

        self.subdir = config["subdir"]

        for archname in self.architectures :
            for compname in self.components :
                self.subrepos.append( repolib.MirrorComponent.new( ( archname , compname ) , config ) )

        # Not strictly required, but kept as member for convenience
        self.release = os.path.join( self.metadata_path() , "Release" )

    def repo_path ( self ) :
        if self.subdir :
            return os.path.join( self.destdir , self.subdir )
        return repolib.MirrorRepository.repo_path(self)

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

    def get_metafile ( self , _params=None , keep=False ) :

        params = self.params
        if _params : params.update( _params )

        release_file = repolib.MirrorRepository.get_metafile( self , self.release , params , keep )

        if not release_file :
            repolib.logger.error( "Metadata for '%s' not found" % self.version )
            return self.__subrepo_dict( release_file )
        elif release_file is True :
            return self.__subrepo_dict( True )

        repolib.logger.info( "Content verification of metafile %s" % release_file )
        release = debian_bundle.deb822.Release( sequence=open( release_file ) )


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


        # We get sure that all the requested components are defined in the
        # mirrored repository.
        # If no component is defined neither on repomirror configuration or
        # in Release file, main is selected as the only component to mirror

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
                self.components = release_comps

        elif self.components :
            repolib.logger.error( "There is no components entry in Release file for '%s', please fix your configuration" % self.version )
            os.unlink( release_file )
            return self.__subrepo_dict( False )
        else :
            repolib.logger.warning( "Component list undefined, setting to main" )
            self.components = ( "main" ,)


        # Architecture requires the same verification than components, but
        # as it must be present on Release and repomirror configuration the
        # workflow is much simpler

        release_archs = release['Architectures'].split()
        for arch in self.architectures :
            if arch not in release_archs :
                repolib.logger.error( "Architecture '%s' is not available ( %s )" % ( arch , " ".join(release_archs) ) )
                # FIXME : only this architecture should get marked as unavailable
                os.unlink( release_file )
                return self.__subrepo_dict( False )


        return self.__subrepo_dict( release_file )

    def write_master_file ( self , meta_files ) :

        # Path for local copy must be created in advance by build_local_tree
        local = os.path.join( self.repo_path() , self.release )

        temp_files = set( meta_files.values() )

        if len(temp_files) > 1 :
            repolib.logger.warning( "Too many different Release files returned" )

        for temp_file in temp_files :
          # FIXME : if local exists, we might left behind a temporary file
          if not isinstance(temp_file,bool) and not os.path.exists( local ) :
            self.safe_rename( temp_file , local )

            os.chmod( local , stat.S_IWUSR | stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH )

            if os.path.isfile( temp_file + ".gpg" ) :
                self.safe_rename( temp_file + ".gpg" , local + ".gpg" )

                os.chmod( local + ".gpg" , stat.S_IWUSR | stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH )

        return self.__subrepo_dict( os.path.dirname( local ) )

    def info ( self , metafile ) :

        release_file = set(metafile.values())
        release = debian_bundle.deb822.Release( sequence=open( os.path.join( release_file.pop() , "Release" ) ) )

        if release_file :
            repolib.logger.warning( "Too many different Release files returned" )

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

        str  = "Mirroring %(Label)s %(Version)s(%(Codename)s)\n" % release
        str += "%(Origin)s %(Suite)s%(Date)s\n" % release
        str += "Subrepos : %s\n" % " ".join( map( lambda x : "%s" % x , self.subrepos ) )
        return str

from feed import SimpleComponent , feed_build_repository

class DebianComponent ( SimpleComponent ) :

    def __init__ ( self , ( arch , comp ) , config ) :
        self.subdir = config["subdir"]
        self.archname , self.compname = arch, comp
        SimpleComponent.__init__( self , ( arch , comp ) , config )

    def __str__ ( self ) :
        return "%s/%s" % ( self.archname , self.compname )

    def repo_path ( self ) :
        if self.subdir :
            return os.path.join( self.destdir , self.subdir )
        return SimpleComponent.repo_path(self)

    def metadata_path ( self , partial=False ) :
        path = "%s/binary-%s/" % ( self.compname , self.archname )
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
            if utils.integrity_check( filename , _item ) is False :
                os.unlink( filename )
                return False

            return True

        else :
            repolib.logger.error( "Checksum for file '%s' not found, exiting." % _name ) 
            return False

    def get_metafile( self , metafile , _params=None , download=True ) :
        """
Verifies checksums and optionally downloads the Packages file for a component.
Returns the full pathname for the file in its final destination or False when
error ocurrs. When the repository is in update mode, True is returned to signal
that the current copy is ok.
"""

        # Currently unused, but relevant to verification flags
        params = self.params
        if _params : params.update( _params )

        if download :
            master_file = os.path.join( metafile[self] , "Release" )
        else :
            master_file = metafile[self]

        release = debian_bundle.deb822.Release( sequence=open( master_file ) )

        _name = "%sRelease" % self.metadata_path()
        localname = os.path.join( self.repo_path() , _name )

        if os.path.isfile( localname ) :
            _name = "%sRelease" % self.metadata_path(True)
            if self.verify( localname , _name , release , params ) :
                repolib.logger.info( "Local copy of '%s' is up-to-date, skipping." % _name )

        if not os.path.isfile( localname ) :
          if download :
            repolib.logger.info( "No local Release file exist for %s. Downloading." % self )
            url = "%sRelease" % self.metadata_path()
            if self.downloadRawFile( url , localname ) :
                _name = "%sRelease" % self.metadata_path(True)
                if not self.verify( localname , _name , release , params ) :
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
                continue

        else :

          localname = False
          if download :
            repolib.logger.info( "No local Packages file exist for %s. Downloading." % self )
            localname = SimpleComponent.get_metafile( self , release , _params , True )

        if isinstance(localname,str) :
            return read_handler( localname )

        return localname

    def pkg_list( self ) :
        return DebianPackageList()

    def forward( self , fd ) :
        pass


class debian_build_repository ( feed_build_repository ) :

    valid_extensions = ( ".deb" ,)


class debian_component_repository ( debian_build_repository ) :

    def __init__ ( self , config , name ) :

        debian_build_repository.__init__( self , config , name )

        if not config['architectures'] or len(config['architectures']) > 1 :
            raise Exception( "Broken '%s' configuration : single architecture required." % name )

        if not config['components'] or len(config['components']) > 1 :
            raise Exception( "Broken '%s' configuration : single component required." % name )

        self.architecture , self.component = config['architectures'][0] , config['components'][0]

    def build ( self ) :
        feed_build_repository.build( self )
        fd = open( os.path.join( self.repo_path() , "Release" ) , 'w' )
        fd.write( "Version: %s\n" % self.version )
        fd.write( "Component: %s\n" % self.component )
        fd.write( "Architecture: %s\n" % self.architecture )
        fd.close()



