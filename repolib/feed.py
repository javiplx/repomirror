
import debian_bundle.debfile
import debtarfile

import os
import tempfile


import config , utils


import repolib


class feed_build_repository ( repolib.BuildRepository ) :

    valid_extensions = ( ".opk" , ".ipk" )

    def __init__ ( self , config , name ) :

        repolib.BuildRepository.__init__( self , config , name )

        if config.has_key( "extensions" ) :
            self.valid_extensions = config['extensions']

	if not os.path.isdir( self.repo_path() ) :
            raise Exception( "Repository directory %s does not exists" % self.repo_path() )

        self.feeds = ( packages_build_repository(self) ,)

    def build ( self ) :
        for feed in self.feeds :
            feed.build()


class packages_build_repository :

    def __init__ ( self , parent ) :
        self.repo_path = parent.repo_path()
        self.base_path = parent.repo_path()
        self.valid_extensions = parent.valid_extensions

        self.recursive = False
        self.architectures = False

        config.mimetypes[''] = open

        self.outchannels = []
        output_path = os.path.join( parent.repo_path() , self.metadata_path() )
        filename = os.path.join( output_path , "Packages" )
        for ( extension , read_handler ) in config.mimetypes.iteritems() :
            self.outchannels.append( read_handler( "%s%s" % ( filename , extension ) , 'w' ) )

    def build ( self ) :
        if self.recursive :
            os.path.walk( self.base_path , self.writer , self )
        else :
            self.writer( self , self.base_path , os.listdir( self.base_path ) )
        self.post_build()

    def post_build ( self ) :
        for pkgsfile in self.outchannels :
            pkgsfile.close()

    def metadata_path ( self , partial=False ) :
        return ""

    def extract_filename ( self , name ) :
            return "./%s" % name.replace( "%s/" % self.repo_path , "" )

    def writer ( self , top , names ) :
        validnames = filter( lambda x : os.path.splitext( x )[1] in self.valid_extensions , names )
        if self.architectures :
            validnames = filter( lambda x : os.path.splitext(x)[0].split('_')[-1] in self.architectures , validnames )
        fullnames = map( lambda x : os.path.join( top , x ) , validnames )
        for fullpath in filter( os.path.isfile , fullnames ) :
            try :
                pkg = debian_bundle.debfile.DebFile( fullpath )
            except debian_bundle.arfile.ArError , ex :
                pkg = debtarfile.DebTarFile( fullpath )
            control = pkg.control.debcontrol()
            control["Filename"] = self.extract_filename( fullpath )
            if not control.has_key("Size") :
                control["Size"] = "%s" % os.stat( fullpath ).st_size
            for type in ( 'MD5sum' ,) :
                control[type] = utils.cksum_handles[type.lower()]( fullpath )
            for pkgsfile in self.outchannels :
                pkgsfile.write( "%s\n" % control )
    writer = staticmethod(writer)


class feed_repository ( repolib.MirrorRepository ) :

    required = ( 'destdir' , 'type' , 'url' , 'architectures' )

    def __init__ ( self , config ) :
        repolib.MirrorRepository.__init__( self , config )
        for archname in self.architectures :
            subrepo = repolib.MirrorComponent.new( archname , config )
            self.subrepos.update( { str(subrepo) : subrepo } )

    def __subrepo_dict ( self , value ) :
        d = {}
        for k in self.subrepos :
            d[k] = value
        return d

    def get_metafile ( self , _params=None ) :
        return self.__subrepo_dict( '' )

    def metadata_path ( self , partial=False ) :
        return ""

    def write_master_file ( self , metafiles ) :
        return self.__subrepo_dict( '' )

    def info ( self , metafile , cb ) :
        cb( "Mirroring %s" % self.name )
        cb( "Architectures : %s" % " ".join(self.architectures) )
        if self.version : cb( "Version %s" % ( self.version ) )

class SimpleComponent ( repolib.MirrorComponent ) :

    def metadata_path ( self , partial=False ) :
        return ""

    def match_filters( self , pkginfo , filters ) :
        if filters.has_key('sections') and pkginfo.has_key('Section') and pkginfo['Section'] not in filters['sections'] :
            return False
        if filters.has_key('priorities') and pkginfo.has_key('Priority') and pkginfo['Priority'] not in filters['priorities'] :
            return False
        if filters.has_key('tags') and pkginfo.has_key('Tag') and pkginfo['Tag'] not in filters['tags'] :
            return False
        return True

    def get_metafile( self , metafile , _params=None ) :
        """Downloads the Packages file for a feed."""

        params = self.params
        if _params : params.update( _params )

        if isinstance(metafile,bool) :
            raise Exception( "Calling %s.get_metafile( %s )" % ( self , metafile ) )

        localname = False

        for ( extension , read_handler ) in config.mimetypes.iteritems() :

            url = "%sPackages%s" % ( self.metadata_path() , extension )
            localname = os.path.join( self.repo_path() , url )

            if self.mode == "keep" :
                localname = tempfile.mktemp()
                repolib.logger.info( "Using temporary '%s' for Packages%s file" % ( localname , extension ) )
            if self.downloadRawFile( url , localname ) :
                _name = "%sPackages%s" % ( self.metadata_path(True) , extension )
                if self.verify( localname , _name , metafile , params ) :
                    break
                os.unlink( localname )
                localname = False
                continue

        else :
            repolib.logger.error( "No valid Packages file found for %s" % self )
            localname = False

        if isinstance(localname,str) :
            return read_handler( localname )

        return localname

    def verify( self , filename , _name , release , params ) :
        return True

    def forward( self , fd ) :
        # At least for the sample feed, double empty lines are used
        fd.readline()

    def get_package_list ( self , fd , _params , filters ) :

        params = self.params
        params.update( _params )

        all_pkgs = {}
        all_requires = {}

        download_pkgs = self.pkg_list()
        rejected_pkgs = self.pkg_list()
        missing_pkgs = []

        if fd :
            if 'name' in dir(fd) :
                fdname = fd.name
            else :
                fdname = fd.filename
            packages = debian_bundle.debian_support.PackageFile( fdname , fd )

# FIXME : If any minor filter is used, Packages file must be recreated for the exported repo
#         Solution : Disable filtering on first approach
#         In any case, the real problem is actually checksumming, reconstructiog Release and signing

            repolib.logger.warning( "Scanning available %s packages for minor filters" % self )
            for pkg in packages :
                self.forward( fd )
                pkginfo = debian_bundle.deb822.Deb822Dict( pkg )

                # On debian repos, we add this key while writting into PackageList
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

                if pkginfo.has_key( 'Depends' ) :
                    for deplist in pkginfo['Depends'].split(',') :                            
                        if not deplist :
                            continue

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

        return download_pkgs , missing_pkgs


