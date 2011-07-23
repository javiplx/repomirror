
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

        for archname in self.architectures :
            for compname in self.components :
                self.subrepos.append( DebianComponent( config , ( archname , compname ) ) )

        # Not strictly required, but kept as member for convenience
        self.release = os.path.join( self.metadata_path() , "Release" )

    def repo_path ( self ) :
        # NOTE : we don't append the repository name to allow sharing of packages pool
        return self.destdir

    def metadata_path ( self , partial=False ) :
        if partial :
            return ""
        return "dists/%s" % self.version

    def __subrepo_dict ( self , value ) :
        d = {}
        for k in self.subrepos :
            d[k] = value
        return d

    def get_master_file ( self , _params , keep=False ) :

        params = self.params
        params.update( _params )

        release_file = self.get_signed_metafile ( params , self.release , keep )

        version = self.version.split("/")[0].split("-")[0].lower()
        if not release_file :
            repolib.logger.error( "No valid Release file for '%s'" % ( self.version ) )
            return self.__subrepo_dict( release_file )
        elif release_file is True :
            return self.__subrepo_dict( True )

        repolib.logger.info( "Content verification of metafile %s" % release_file )
        release = debian_bundle.deb822.Release( sequence=open( release_file ) )


        # Although both names and suites can be used within sources.list, we
        # will enforce mirroring based on codenames
        # FIXME : Is sensible to use in any way the version from Release?

        version = self.version.split("/").pop(0)
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
                        return self.__subrepo_dict( False )
            else :
                repolib.logger.warning( "No components specified, selected all components from Release file" )
                self.components = release_comps

        elif self.components :
            repolib.logger.error( "There is no components entry in Release file for '%s', please fix your configuration" % self.version )
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
                return self.__subrepo_dict( False )


        return self.__subrepo_dict( release_file )

    def write_master_file ( self , meta_files ) :

        # Path for local copy must be created in advance by build_local_tree
        local = os.path.join( self.repo_path() , self.release )

        temp_file = meta_files.values()[0]
        if not os.path.exists( local ) :
            self.safe_rename( temp_file , local )

            os.chmod( local , stat.S_IWUSR | stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH )

            if os.path.isfile( temp_file + ".gpg" ) :
                self.safe_rename( temp_file + ".gpg" , local + ".gpg" )

                os.chmod( local + ".gpg" , stat.S_IWUSR | stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH )

        return self.__subrepo_dict( os.path.dirname( local ) )

    def info ( self , meta_files ) :

        release_file = meta_files.values()[0]
        release = debian_bundle.deb822.Release( sequence=open( os.path.join( release_file , "Release" ) ) )

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

from feed import SimpleComponent

class DebianComponent ( SimpleComponent ) :

    def __init__ ( self , config , ( arch , comp ) ) :
        self.archname , self.compname = arch, comp
        SimpleComponent.__init__( self , config , ( arch , comp ) )

    def __str__ ( self ) :
        return "%s/%s" % ( self.archname , self.compname )

    def repo_path ( self ) :
        return self.destdir

    def metadata_path ( self , partial=False ) :
        path = "%s/binary-%s/" % ( self.compname , self.archname )
        if partial :
            return path
        return "dists/%s/%s" % ( self.version , path )

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

    def get_metafile( self , metafile , _params , download=True ) :
        """
Verifies checksums and optionally downloads the Packages file for a component.
Returns the full pathname for the file in its final destination or False when
error ocurrs. When the repository is in update mode, True is returned to signal
that the current copy is ok.
"""

        # Currently unused, but relevant to verification flags
        params = self.params
        params.update( _params )

        if download :
            master_file = os.path.join( metafile[self] , "Release" )
        else :
            master_file = metafile[self]

        release = debian_bundle.deb822.Release( sequence=open( master_file ) )

        _name = "%sRelease" % self.metadata_path()
        localname = os.path.join( self.repo_path() , _name )

        if os.path.isfile( localname ) :
            _name = "%sRelease" % self.metadata_path(True)
            if not self.verify( localname , _name , release , params ) :
                os.unlink( localname )

        if not os.path.isfile( localname ) :
            url = "%sRelease" % self.metadata_path()
            if self.downloadRawFile( url , localname ) :
                _name = "%sRelease" % self.metadata_path(True)
                if not self.verify( localname , _name , release , params ) :
                    repolib.logger.warning( "Missing Release file for %s" % self )

        localname = False

        for ( extension , read_handler ) in config.mimetypes.iteritems() :

            _name = "%sPackages%s" % ( self.metadata_path() , extension )
            localname = os.path.join( self.repo_path() , _name )

            if os.path.isfile( localname ) :
                _name = "%sPackages%s" % ( self.metadata_path(True) , extension )
                if self.verify( localname , _name , release , params ) :
                    if self.mode == "update" :
                        repolib.logger.warning( "Local copy of '%s' is up-to-date, skipping." % _name )
                        return True
                    break
                continue

        else :

          if download :
            # NOTE : Download of Package Release file is quite redundant

            repolib.logger.warning( "No local Packages file exist for %s. Downloading." % self )

            localname = SimpleComponent.get_metafile( self , release , _params , True )

          else :
            localname = False

        if isinstance(localname,str) :
            return read_handler( localname )

        return localname

    def pkg_list( self ) :
        return DebianPackageList()

    def forward( self , fd ) :
        pass


class debian_build_repository ( repolib.BuildRepository ) :

    def __init__ ( self , config ) :

        repolib.BuildRepository.__init__( self , config )

        self.components = config.get( "components" , None )


