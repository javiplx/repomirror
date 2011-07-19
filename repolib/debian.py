
import debian_bundle.deb822 , debian_bundle.debian_support

import errno , shutil

import os , sys


import config , utils


from repolib import MirrorRepository , BuildRepository , logger
from debian_lists import DebianPackageList , DebianDownloadList , DebianDownloadThread


class debian_repository ( MirrorRepository ) :

    def __init__ ( self , config ) :
        MirrorRepository.__init__( self , config )

        # Stored for later use during Release file checks
        self.components = config.get( "components" , None )

        for archname in self.architectures :
            for compname in self.components :
                self.subrepos.append( DebianComponent( config , ( archname , compname ) ) )

        # Not strictly required, but kept as member for convenience
        self.release = os.path.join( self.metadata_path() , "Release" )

    def base_url ( self ) :
        return self.repo_url

    def repo_path ( self ) :
        return self.destdir

    def metadata_path ( self , partial=False ) :
        path = ""
        if not partial :
            path = "dists/%s/%s" % ( self.version , path )
        return path

    def get_master_file ( self , _params , keep=False ) :

        params = self.params
        params.update( _params )

        release_file = self.get_signed_metafile ( params , self.release , ".gpg" , keep )

        if not release_file :
            logger.error( "No valid Release file for '%s'" % ( self.version ) )
            return { '':release_file }
        elif release_file is True :
            return { '':True }

        logger.info( "Content verification of metafile %s" % release_file )
        release = debian_bundle.deb822.Release( sequence=open( release_file ) )


        # Although both names and suites can be used within sources.list, we
        # will enforce mirroring based on codenames
        # FIXME : Is sensible to use in any way the version from Release?

        version = self.version.split("/").pop(0)
        suite = release['Suite']
        codename = release['Codename']

        if suite != codename and suite == version :
            logger.error( "You have supplied suite '%s'. Please use codename '%s' instead" % ( self.version, codename ) )
            os.unlink( release_file )
            return { '':False }

        if codename != version :
            logger.error( "Requested version '%s' does not match with codename from Release file ('%s')" % ( self.version, codename ) )
            os.unlink( release_file )
            return { '':False }


        # We get sure that all the requested components are defined in the
        # mirrored repository.
        # If no component is defined neither on repomirror configuration or
        # in Release file, main is selected as the only component to mirror

        if release.has_key( "Components" ) :
            # NOTE : security and volatile repositories prepend a string to the actual component name
            release_comps = map( lambda s : s.rsplit("/").pop() , release['Components'].split() )

            if self.components :
                for comp in self.components :
                    if comp not in release_comps :
                        logger.error( "Component '%s' is not available ( %s )" % ( comp , " ".join(release_comps) ) )
                        return { '':False }
            else :
                logger.warning( "No components specified, selected all components from Release file" )
                self.components = release_comps

        elif self.components :
            logger.error( "There is no components entry in Release file for '%s', please fix your configuration" % self.version )
            return { '':False }
        else :
            logger.warning( "Component list undefined, setting to main" )
            self.components = ( "main" ,)


        # Architecture requires the same verification than components, but
        # as it must be present on Release and repomirror configuration the
        # workflow is much simpler

        release_archs = release['Architectures'].split()
        for arch in self.architectures :
            if arch not in release_archs :
                logger.error( "Architecture '%s' is not available ( %s )" % ( arch , " ".join(release_archs) ) )
                return { '':False }


        return { '':release_file }

    def write_master_file ( self , release_file ) :

        # Path for local copy must be created in advance by build_local_tree
        local = os.path.join( self.repo_path() , self.release )

        if not os.path.exists( local ) :
            try :
                os.rename( release_file[''] , local )
            except OSError , ex :
                if ex.errno != errno.EXDEV :
                    print "OSError: %s" % ex
                    sys.exit(1)
                shutil.move( release_file[''] , local )

        return { '' : os.path.dirname( local ) }

    def info ( self , release_file ) :

        release = debian_bundle.deb822.Release( sequence=open( os.path.join( release_file[''] , "Release" ) ) )

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

    def base_url ( self ) :
        return self.repo_url

    def repo_path ( self ) :
        return self.destdir

    def metadata_path ( self , partial=False ) :
        path = "%s/binary-%s/" % ( self.compname , self.archname )
        if not partial :
            path = "dists/%s/%s" % ( self.version , path )
        return path

    def match_filters( self , pkginfo , filters ) :
        if filters.has_key('sections') and pkginfo.has_key('Section') and pkginfo['Section'] not in filters['sections'] :
            return False
        if filters.has_key('priorities') and pkginfo.has_key('Priority') and pkginfo['Priority'] not in filters['priorities'] :
            return False
        if filters.has_key('tags') and pkginfo.has_key('Tag') and pkginfo['Tag'] not in filters['tags'] :
            return False
        return True

    def verify( self , filename , _name , release , params ) :
        #
        # IMPROVEMENT : For Release at least, and _multivalued in general : Multivalued fields returned as dicts instead of lists
        #
        # FIXME : 'size' element should be a number !!!
        #
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
            logger.error( "Checksum for file '%s' not found, exiting." % _name ) 
            return False

    def check_packages_file( self , metafile , _params , download=True ) :
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
            master_file = os.path.join( metafile[''] , "Release" )
        else :
            master_file = metafile['']

        release = debian_bundle.deb822.Release( sequence=open( master_file ) )

        localname = False

        for ( extension , read_handler ) in config.mimetypes.iteritems() :

            _name = "%sPackages%s" % ( self.metadata_path() , extension )
            localname = os.path.join( self.repo_path() , _name )

            if os.path.isfile( localname ) :
                _name = "%sPackages%s" % ( self.metadata_path(True) , extension )
                if self.verify( localname , _name , release , params ) :
                    if self.mode == "update" :
                        logger.warning( "Local copy of '%s' is up-to-date, skipping." % _name )
                        return True
                    break
                continue

        else :

          if download :
            # NOTE : Download of Package Release file is quite redundant

            logger.warning( "No local Packages file exist for %s. Downloading." % self )

            localname = SimpleComponent.check_packages_file( self , release , _params , True )

          else :
            localname = False

        if isinstance(localname,str) :
            return read_handler( localname )

        return localname

    def get_package_list ( self , fd , _params , filters ) :

        params = self.params
        params.update( _params )

        # NOTE : Downloading Package Release file is quite redundant

        download_size = 0
        missing_pkgs = []

        all_pkgs = {}
        all_requires = {}

        download_pkgs = DebianPackageList()
        rejected_pkgs = DebianPackageList()

        if fd :
            if 'name' in dir(fd) :
                fdname = fd.name
            else :
                fdname = fd.filename
            packages = debian_bundle.debian_support.PackageFile( fdname , fd )

# FIXME : If any minor filter is used, Packages file must be recreated for the exported repo
#         Solution : Disable filtering on first approach
#         In any case, the real problem is actually checksumming, reconstructiog Release and signing

            logger.warning( "Scanning available packages for minor filters" )
            for pkg in packages :
                pkginfo = debian_bundle.deb822.Deb822Dict( pkg )
                pkginfo['Name'] = pkginfo['Package']

                # NOTE : Is this actually a good idea ?? It simplifies, but I would like to mirror main/games but not contrib/games, for example
                # SOLUTION : Create a second and separate Category with the last part (filename) of Section
                # For now, we kept the simplest way
# FIXME : Remaining reference to subrepo
#                if pkginfo['Section'].find( "%s/" % subrepo[1] ) == 0 :
#                    pkginfo['Section'] = pkginfo['Section'][pkginfo['Section'].find("/")+1:]

                if not self.match_filters( pkginfo , filters ) :
                    rejected_pkgs.append( pkginfo )
                    continue

                all_pkgs[ pkginfo['Package'] ] = 1
                download_pkgs.append( pkginfo )
                # FIXME : This might cause a ValueError exception ??
                download_size += int( pkginfo['Size'] )

                if pkginfo.has_key( 'Depends' ) :
                    for deplist in pkginfo['Depends'].split(',') :                            
                        # When we found 'or' in Depends, we will download all of them
                        for depitem in deplist.split('|') :
                            # We keep only the package name, more or less safer within a repository
                            pkgname = depitem.strip().split(None,1)
                            all_requires[ pkgname[0] ] = 1

            fd.close()
            del packages

            for pkginfo in rejected_pkgs :

                # FIXME : We made no attempt to go into a full depenceny loop
                if all_requires.has_key( pkginfo['Package'] ) :
                    all_pkgs[ pkginfo['Package'] ] = 1
                    download_pkgs.append( pkginfo )
                    # FIXME : This might cause a ValueError exception ??
                    download_size += int( pkginfo['Size'] )

                    if pkginfo.has_key( 'Depends' ) :
                        for deplist in pkginfo['Depends'].split(',') :                            
                            # When we found 'or' in Depends, we will download all of them
                            for depitem in deplist.split('|') :
                                # We keep only the package name, more or less safer within a repository
                                pkgname = depitem.strip().split(None,1)
                                all_requires[ pkgname[0] ] = 1

            for pkgname in all_requires.keys() :
                if not all_pkgs.has_key( pkgname ) :
                    missing_pkgs.append( pkgname )

        return download_size , download_pkgs , missing_pkgs

    def get_download_list( self ) :
        return DebianDownloadThread( self )


class debian_build_repository ( BuildRepository ) :

    def __init__ ( self , config ) :

        BuildRepository.__init__( self , config )

        self.components = config.get( "components" , None )


