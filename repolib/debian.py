
import debian_bundle.deb822 , debian_bundle.debian_support

import repoutils

import errno , shutil
import urllib2

import os , sys


# FIXME : Include standard plain os.open??
extensions = {}

try :
    import gzip
    extensions['.gz'] = gzip.open
except :
    pass
    
try :
    import bz2
    extensions['.bz2'] = bz2.BZ2File
except :
    pass


from repolib import abstract_repository


class debian_repository ( abstract_repository ) :

    def __init__ ( self , config ) :
        abstract_repository.__init__( self , config )

        self.components = config.get( "components" , None )

        self.release = os.path.join( self.metadata_path() , "Release" )

    def base_url ( self ) :
        return self.repo_url

    def repo_path ( self ) :
        return self.destdir

    def metadata_path ( self , subrepo=None , partial=False ) :
        path = ""
        if subrepo :
            arch , comp = subrepo
            path += "%s/binary-%s/" % ( comp , arch )
        if not partial :
            path = "dists/%s/%s" % ( self.version , path )
        return path

    def get_master_file ( self , _params ) :

        params = self.params
        params.update( _params )

        release_file = self.get_signed_metafile ( params , self.release , ".gpg" )

        if not release_file :
            repoutils.show_error( "Could not retrieve Release file for suite '%s'" % ( self.version ) )
            return

        if release_file is True :
            return

        release = debian_bundle.deb822.Release( sequence=open( release_file ) )

        if release['Suite'] !=  release['Codename'] :
            if release['Suite'].lower() == self.version.lower() :
                repoutils.show_error( "You have supplied suite '%s'. Please use codename '%s' instead" % ( self.version, release['Codename'] ) )
                os.unlink( release_file )
                return

        if release['Codename'].lower() != self.version.lower() :
            repoutils.show_error( "Requested version '%s' does not match with codename from Release file ('%s')" % ( self.version, release['Codename'] ) )
            os.unlink( release_file )
            return

        if release.has_key( "Components" ) :
            # NOTE : security and volatile repositories prepend a string to the actual component name
            release_comps = map( lambda s : s.rsplit("/").pop() , release['Components'].split() )

            if self.components :
                for comp in self.components :
                    if comp not in release_comps :
                        repoutils.show_error( "Component '%s' is not available ( %s )" % ( comp , " ".join(release_comps) ) )
                        return
            else :
                repoutils.show_error( "No components specified, selected all components from Release file" , False )
                self.components = release_comps

        elif self.components :
            repoutils.show_error( "There is no components entry in Release file for suite '%s', please fix your configuration" % self.version )
            return
        else :
            # FIXME : This policy is taken from scratchbox repository, with no explicit component and files located right under dists along Packages file
            repoutils.show_error( "Va que no, ni haskey, ni components" , False )
            self.components = ( "main" ,)

        release_archs = release['Architectures'].split()
        for arch in self.architectures :
            if arch not in release_archs :
                repoutils.show_error( "Architecture '%s' is not available ( %s )" % ( arch , " ".join(release_archs) ) )
                return

        return release_file

    def write_master_file ( self , release_file ) :

        local = os.path.join( self.repo_path() , self.release )

        # FIXME : If we reach this point, is it possible that the file is still there ?
        if not os.path.exists( local ) :
            try :
                os.rename( release_file , local )
            except OSError , ex :
                if ex.errno != errno.EXDEV :
                    print "OSError: %s" % ex
                    sys.exit(1)
                shutil.move( release_file , local )

        return os.path.dirname( local )

    def info ( self , release_file ) :

        release = debian_bundle.deb822.Release( sequence=open( os.path.join( release_file , "Release" ) ) )

        # Some Release files hold no 'version' information
        if not release.has_key( 'Version' ) :
            release['Version'] = None

        # Some Release files hold no 'Date' information
        if not release.has_key( 'Date' ) :
            release['Date'] = None

        str  = "Mirroring %(Label)s %(Version)s (%(Codename)s)\n" % release
        str += "%(Origin)s %(Suite)s , %(Date)s\n" % release
        str += "Components : %s\n" % " ".join(self.components)
        str += "Architectures : %s\n" % " ".join(self.architectures)
        return str

    def get_subrepos ( self ) :
        subrepos = []
        for arch in self.architectures :
            for comp in self.components :
              subrepos.append( ( arch , comp ) )
        return subrepos

    def get_package_list ( self , subrepo , suite_path , _params , filters ) :

        params = self.params
        params.update( _params )

        release = debian_bundle.deb822.Release( sequence=open( os.path.join( self.repo_path() , self.release ) ) )

        # NOTE : Downloading Package Release file is quite redundant

        download_size = 0
        download_pkgs = []
        missing_pkgs = []

        fd = False
        localname = None

        for ( extension , read_handler ) in extensions.iteritems() :

            _name = "%sPackages%s" % ( self.metadata_path(subrepo,True) , extension )
            localname = os.path.join( suite_path , _name )

            if os.path.isfile( localname ) :
                #
                # IMPROVEMENT : For Release at least, and _multivalued in general : Multivalued fields returned as dicts instead of lists
                #
                # FIXME : 'size' element should be a number !!!
                #
                # FIXME : What about other checksums (sha1, sha256)
                _item = {}
                for type in ( 'MD5Sum' , 'SHA1' , 'SHA256' ) :
                    if release.has_key(type) :
                        for item in release[type] :
                            if item['name'] == _name :
                                _item.update( item )
                if _item :
                    if params['usemd5'] :
                        error = repoutils.md5_error( localname , _item )
                        if error :
                            repoutils.show_error( error , False )
                            os.unlink( localname )
                            continue

                    # NOTE : force and unsync should behave different here? We could just force download if forced
                    if params['mode'] == "update" :
                        repoutils.show_error( "Local copy of '%s' is up-to-date, skipping." % _name , False )
                    else :
                        fd = read_handler( localname )

                    break

                else :
                    repoutils.show_error( "Checksum for file '%s' not found, go to next format." % _name , True )
                    continue

        else :

            repoutils.show_error( "No local Packages file exist for %s / %s. Downloading." % subrepo , True )

            for ( extension , read_handler ) in extensions.iteritems() :

                _name = "%sPackages%s" % ( self.metadata_path(subrepo,True) , extension )
                localname = os.path.join( suite_path , _name )
                url = urllib2.urlparse.urljoin( urllib2.urlparse.urljoin( self.base_url() , self.metadata_path() ) , _name )

                if self._retrieve_file( url , localname ) :
                    #
                    # IMPROVEMENT : For Release at least, and _multivalued in general : Multivalued fields returned as dicts instead of lists
                    #
                    # FIXME : 'size' element should be a number !!!
                    #
                    # FIXME : What about other checksums (sha1, sha256)
                    _item = {}
                    for type in ( 'MD5Sum' , 'SHA1' , 'SHA256' ) :
                        if release.has_key(type) :
                            for item in release[type] :
                                if item['name'] == _name :
                                    _item.update( item )
                    if _item :
                        if params['usemd5'] :
                            error = repoutils.md5_error( localname , _item )
                            if error :
                                repoutils.show_error( error , False )
                                os.unlink( localname )
                                continue

                        break

                    else :
                        repoutils.show_error( "Checksum for file '%s' not found, exiting." % _name ) 
                        continue

            else :
                repoutils.show_error( "No Valid Packages file found for %s / %s" % subrepo )
                sys.exit(0)

            fd = read_handler( localname )

        all_pkgs = {}

        if fd :
            packages = debian_bundle.debian_support.PackageFile( localname , fd )

# FIXME : If any minor filter is used, Packages file must be recreated for the exported repo
#         Solution : Disable filtering on first approach
#         In any case, the real problem is actually checksumming, reconstructiog Release and signing

            repoutils.show_error( "Scanning available packages for minor filters" , False )
            for pkg in packages :
                pkginfo = debian_bundle.deb822.Deb822Dict( pkg )

                # NOTE : Is this actually a good idea ?? It simplifies, but I would like to mirror main/games but not contrib/games, for example
                # SOLUTION : Create a second and separate Category with the last part (filename) of Section
                # For now, we kept the simplest way
                if pkginfo['Section'].find( "%s/" % subrepo[1] ) == 0 :
                    pkginfo['Section'] = pkginfo['Section'][pkginfo['Section'].find("/")+1:]

                pkginfo['name'] = pkginfo['Package']
                all_pkgs[ pkginfo['Package'] ] = pkginfo

            fd.close()
            del packages

        for pkg_key,pkginfo in all_pkgs.iteritems() :

            if filters.has_key('sections') and pkginfo['Section'] not in filters['sections'] :
                continue
            if filters.has_key('priorities') and pkginfo['Priority'] not in filters['priorities'] :
                continue
            if filters.has_key('tags') and 'Tag' in pkginfo.keys() and pkginfo['Tag'] not in filters['tags'] :
                continue

            download_pkgs.append( pkginfo )
            # FIXME : This might cause a ValueError exception ??
            download_size += int( pkginfo['Size'] )

            if pkginfo.has_key( 'Depends' ) :
                deplist = []
                for depitem in pkginfo['Depends'].split(',') :
                    # When we found 'or' in Depends, we download all of them
                    for deppkg in depitem.split('|') :
                        pkgname = deppkg.strip().split(None,1)
                        deplist.append( pkgname[0] )
                for deppkg in deplist :
                    if all_pkgs.has_key( deppkg ) :
                        download_pkgs.append( all_pkgs[ deppkg ] )
                        download_size += int( all_pkgs[deppkg]['Size'] )
                        break
                    else :
                        missing_pkgs.append ( deppkg )

        return download_size , download_pkgs , missing_pkgs


