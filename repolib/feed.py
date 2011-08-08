
import debian_bundle.debfile
import debtarfile

import os


import config , utils


import repolib


class feed_build_repository ( repolib.BuildRepository ) :

    valid_extensions = ( ".opk" , ".ipk" )

    def __init__ ( self , config , name ) :

        repolib.BuildRepository.__init__( self , config )

        self.name = name
        if config.has_key( "extensions" ) :
            self.valid_extensions = config['extensions']

	if not os.path.isdir( self.repo_path() ) :
            raise Exception( "Repository directory %s does not exists" % self.repo_path() )

    def build ( self ) :

        config.mimetypes[''] = open

        packages = []
        filename = os.path.join( self.repo_path() , "Packages" )
        for ( extension , read_handler ) in config.mimetypes.iteritems() :
            packages.append( read_handler( "%s%s" % ( filename , extension ) , 'w' ) )

        for filename in filter( lambda x : os.path.splitext(x)[1] in self.valid_extensions , os.listdir( self.repo_path() ) ) :
            try :
                pkg = debian_bundle.debfile.DebFile( os.path.join( self.repo_path() , filename ) )
            except debian_bundle.arfile.ArError , ex :
                pkg = debtarfile.DebTarFile( os.path.join( self.repo_path() , filename ) )
            control = pkg.control.debcontrol()
            if not control.has_key("Filename") :
                control["Filename"] = filename
            fullpath = os.path.join( self.repo_path() , filename )
            if not control.has_key("Size") :
                control["Size"] = "%s" % os.stat( fullpath ).st_size
            for type in ( 'MD5sum' ,) :
                control[type] = utils.cksum_handles[type.lower()]( fullpath )
            for pkgsfile in packages :
                pkgsfile.write( "%s\n" % control )

        for pkgsfile in packages :
            pkgsfile.close()


class feed_repository ( repolib.MirrorRepository ) :

    required = ( 'destdir' , 'type' , 'url' , 'architectures' )

    def __init__ ( self , config ) :
        repolib.MirrorRepository.__init__( self , config )
        for archname in self.architectures :
            self.subrepos.append( repolib.MirrorComponent.new( archname , config ) )

    def __subrepo_dict ( self , value ) :
        d = {}
        for k in self.subrepos :
            d[k] = value
        return d

    def get_metafile ( self , _params=None , keep=False ) :
        return self.__subrepo_dict( '' )

    def metadata_path ( self , partial=False ) :
        return ""

    def write_master_file ( self , release_file ) :
        return self.__subrepo_dict( self.repo_path() )

    def info ( self , metafile ) :
        str  = "Mirroring %s\n" % self.name
        str += "Architectures : %s\n" % " ".join(self.architectures)
        if self.version : str += "Version %s\n" % ( self.version )
        return str

    def get_download_list( self ) :
        return DownloadThread( self )

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

    def get_metafile( self , metafile , _params=None , download=True ) :
        """Downloads the Packages file for a feed. As no verification is possible,
fresh download is mandatory, and exception is raised if not specified"""

        localname = False

        params = self.params
        if _params : params.update( _params )

        if not download :
            repolib.logger.warning( "Forcing download mode on %s.get_metafile()" % self )

        for ( extension , read_handler ) in config.mimetypes.iteritems() :

            url = "%sPackages%s" % ( self.metadata_path() , extension )
            localname = os.path.join( self.repo_path() , url )

            if self.downloadRawFile( url , localname ) :
                _name = "%sPackages%s" % ( self.metadata_path(True) , extension )
                if self.verify( localname , _name , metafile , params ) :
                    break
                continue

        else :
            repolib.logger.error( "No valid Packages file found for %s" % self )
            localname = False

        if extension != ".gz" :
            # Forced gz download because debian-installer seems unable to use the bz2 versions
            extension = ".gz"

            url = "%sPackages%s" % ( self.metadata_path() , extension )
            _localname = os.path.join( self.repo_path() , url )

            if self.downloadRawFile( url , _localname ) :
                _name = "%sPackages%s" % ( self.metadata_path(True) , extension )
                if not self.verify( _localname , _name , metafile , params ) :
                    os.unlink( _localname )

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

        download_size = 0
        missing_pkgs = []

        all_pkgs = {}
        all_requires = {}

        download_pkgs = self.pkg_list()
        rejected_pkgs = self.pkg_list()

        if fd :
            if 'name' in dir(fd) :
                fdname = fd.name
            else :
                fdname = fd.filename
            packages = debian_bundle.debian_support.PackageFile( fdname , fd )

# FIXME : If any minor filter is used, Packages file must be recreated for the exported repo
#         Solution : Disable filtering on first approach
#         In any case, the real problem is actually checksumming, reconstructiog Release and signing

            repolib.logger.warning( "Scanning available packages for minor filters" )
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
                # FIXME : This might cause a ValueError exception ??
                download_size += int( pkginfo['Size'] )

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


