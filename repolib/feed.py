
import debian_bundle.debfile
import debtarfile

import os


import config , utils


import repolib
from repolib import urljoin , logger , PackageList


class feed_build_repository ( repolib.BuildRepository ) :

    def __init__ ( self , config , name ) :

        repolib.BuildRepository.__init__( self , config )

        self.name = name
        self.detached = config['detached']
        if config.has_key( "extensions" ) :
            self.valid_extensions = config['extensions']
        else :
            self.valid_extensions = ( ".opk" , ".ipk" )

	if not os.path.isdir( self.repo_path() ) :
            raise Exception( "Repository directory %s does not exists" % self.repo_path() )

        self.components = config.get( "components" , None )

    def repo_path ( self ) :
        if self.detached :
            return self.destdir
        return os.path.join( self.destdir , self.name )

    def build ( self ) :

        config.mimetypes[''] = open
        packages = []

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

    def base_url ( self ) :
        return self.repo_url

    def repo_path ( self ) :
        return os.path.join( self.destdir , self.name )

    def metadata_path ( self , partial=False ) :
        return ""

    def get_master_file ( self , _params , keep=False ) :
        return { '':'' }

    def write_master_file ( self , release_file ) :
        return self.repo_path()

    def info ( self , release_file ) :
        str  = "Mirroring %s\n" % self.name
        str += "Architectures : %s\n" % " ".join(self.architectures)
        str += "unused - version %s\n" % ( self.version )
        return str

    def get_subrepos ( self ) :
        return ( self ,)

    def comp ( self ) :
        return ""

    def arch ( self ) :
        return self.architectures

    def match_filters( self , pkginfo , filters ) :
        if filters.has_key('sections') and pkginfo.has_key('Section') and pkginfo['Section'] not in filters['sections'] :
            return False
        if filters.has_key('priorities') and pkginfo.has_key('Priority') and pkginfo['Priority'] not in filters['priorities'] :
            return False
        if filters.has_key('tags') and pkginfo.has_key('Tag') and pkginfo['Tag'] not in filters['tags'] :
            return False
        return True

    def verify( self , filename , _name , release , params ) :
        return True

    def check_packages_file( self , subrepo , metafile , _params , download=True ) :
        """Downloads the Packages file for a feed. As no verification is possible,
fresh download is mandatory, and exception is raised if not specified"""

        params = self.params
        params.update( _params )

        release = metafile

        localname = False

        if not download :
            logger.error( "Download of Packages file is mandatory for simple feeds" )
            return False

        for ( extension , read_handler ) in config.mimetypes.iteritems() :

            _name = "%sPackages%s" % ( self.metadata_path(True) , extension )
            localname = os.path.join( self.repo_path() , _name )
            url = urljoin( self.metadata_path() , _name )

            if self.downloadRawFile( url , localname ) :
                if self.verify( localname , _name , release , params ) :
                    break
                continue

        else :
            logger.error( "No Valid Packages file found for %s / %s" % ( subrepo , None ) )
            localname = False

        if isinstance(localname,bool) :
            return localname

        return read_handler( localname )

    def get_package_list ( self , fd , _params , filters ) :

        params = self.params
        params.update( _params )

        # NOTE : On debian repos, there is a per-Package Release file that could be useful to download and check

        download_size = 0
        missing_pkgs = []

        all_pkgs = {}
        all_requires = {}

        download_pkgs = self.get_pkg_list()
        rejected_pkgs = self.get_pkg_list() 

        if fd :
            packages = debian_bundle.debian_support.PackageFile( fd.filename , fd )

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
                if pkginfo['Section'].find( "%s/" % self.comp() ) == 0 :
                    pkginfo['Section'] = pkginfo['Section'][pkginfo['Section'].find("/")+1:]

                if not self.match_filters( pkginfo , filters ) :
                    rejected_pkgs.append( pkginfo )
                    continue

                all_pkgs[ pkginfo['Package'] ] = 1
                download_pkgs.append( pkginfo )
                # FIXME : This might cause a ValueError exception ??
                download_size += int( pkginfo['Size'] )

                if pkginfo.has_key( 'Depends' ) and pkginfo['Depends'] :
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

                    if pkginfo.has_key( 'Depends' ) and pkginfo['Depends'] :
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

    def get_pkg_list( self ) :
        return PackageList()


