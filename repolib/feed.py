
import debian_bundle.debfile

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

        packages = open( os.path.join( self.repo_path() , "Packages" ) , 'w' )

        for filename in filter( lambda x : os.path.splitext(x)[1] in self.valid_extensions , os.listdir( self.repo_path() ) ) :
            pkg = debian_bundle.debfile.DebFile( os.path.join( self.repo_path() , filename ) )
            control = pkg.control.debcontrol()
            if not control.has_key("Filename") :
                control["Filename"] = filename
            fullpath = os.path.join( self.repo_path() , filename )
            if not control.has_key("Size") :
                control["Size"] = "%s" % os.stat( fullpath ).st_size
            for type in ( 'MD5sum' ,) :
                control[type] = utils.cksum_handles[type.lower()]( fullpath )
            packages.write( "%s\n" % control )

        packages.close()


class feed_repository ( repolib.MirrorRepository ) :

    def base_url ( self ) :
        return self.repo_url

    def repo_path ( self ) :
        return os.path.join( self.destdir , self.name )

    def get_master_file ( self , _params , keep=False ) :
        return True

    def get_subrepos ( self ) :
        return self.architectures

    def metadata_path ( self , subrepo=None , partial=False ) :
        return ""

    def write_master_file ( self , release_file ) :
        return self.repo_path()

    def info ( self , release_file ) :
        str  = "Mirroring %s\n" % self.name
        str += "Architectures : %s\n" % " ".join(self.architectures)
        str += "unused - version %s\n" % ( self.version )
        return str

    def match_filters( self , pkginfo , filters ) :
        if filters.has_key('sections') and pkginfo['Section'] not in filters['sections'] :
            return False
        if filters.has_key('priorities') and pkginfo.has_key('Priority') and pkginfo['Priority'] not in filters['priorities'] :
            return False
        if filters.has_key('tags') and pkginfo.has_key('Tag') and pkginfo['Tag'] not in filters['tags'] :
            return False
        return True

    def get_package_list ( self , subrepo , suite_path , _params , filters ) :

        # params are not used as no verification is possible

        download_size = 0
        missing_pkgs = []

        fd = False
        localname = None

        # As no verification is possible, we download files every time
        for ( extension , read_handler ) in config.extensions.iteritems() :

            _name = "%sPackages%s" % ( self.metadata_path(subrepo,True) , extension )
            localname = os.path.join( suite_path , _name )
            url = urljoin( self.metadata_path() , _name )

            if self.downloadRawFile( url , localname ) :
                    break

        else :
            logger.error( "No Valid Packages file found for %s / %s" % ( subrepo , None ) )
            os.sys.exit(0)

        fd = read_handler( localname )

        all_pkgs = {}
        all_requires = {}

        download_pkgs = PackageList()
        rejected_pkgs = PackageList() 

        if fd :
            packages = debian_bundle.debian_support.PackageFile( localname , fd )

# FIXME : If any minor filter is used, Packages file must be recreated for the exported repo
#         Solution : Disable filtering on first approach
#         In any case, the real problem is actually checksumming, reconstructiog Release and signing

            logger.warning( "Scanning available packages for minor filters" )
            for pkg in packages :
                # At least for the sample feed, double empty lines are used
                fd.readline()
                pkginfo = debian_bundle.deb822.Deb822Dict( pkg )

                # On debian repos, we add this key while writting into PackageList
                pkginfo['Name'] = pkginfo['Package']

                # NOTE : Is this actually a good idea ?? It simplifies, but I would like to mirror main/games but not contrib/games, for example
                # SOLUTION : Create a second and separate Category with the last part (filename) of Section
                # For now, we kept the simplest way
                if pkginfo['Section'].find( "%s/" % subrepo[1] ) == 0 :
                    pkginfo['Section'] = pkginfo['Section'][pkginfo['Section'].find("/")+1:]

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


