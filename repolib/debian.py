
import debian_bundle.deb822 , debian_bundle.debian_support

import errno , shutil

import os , sys
import tempfile


import config , utils


from repolib import MirrorRepository , BuildRepository , AbstractDownloadThread
from repolib import urljoin , logger , PackageListInterface , AbstractDownloadList


def safe_encode ( str ) :
    try :
        out = "%s" % str.encode('utf-8')
    except UnicodeDecodeError , ex :
        out = "%s" % str
    return out

# Derived from Deb822.dump()
def dump_package(deb822 , fd):
    _multivalued_fields = [ "Description" ]
    fd.write('%s:%s\n' % ('Name',safe_encode(deb822['Package'])))
    for key, value in deb822.iteritems():
        if not value or value[0] == '\n':
            # Avoid trailing whitespace after "Field:" if it's on its own
            # line or the value is empty
            # XXX Uh, really print value if value == '\n'?
            fd.write('%s:%s\n' % (key, safe_encode(value)))
        else :
            values = value.split('\n')
            fd.write('%s: %s\n' % (key, safe_encode(values.pop(0))))
            for v in values:
                _v = values.pop(0)
                if _v == '' :
                    fd.write(' .\n')
                else :
                    fd.write(' %s\n' % safe_encode(_v))
    fd.write('\n')

class DebianPackageFile ( debian_bundle.debian_support.PackageFile ) :
    """This implements a read & write PackageFile.
Input uses a list interface, and output a sequence interface taken from original PackageFile"""

    def __init__ ( self ) :
        self.pkgfd = tempfile.NamedTemporaryFile()
        debian_bundle.debian_support.PackageFile.__init__( self , self.pkgfd.name , self.pkgfd )

    def __iter__ ( self ) :
        self.rewind()
        _pkg = debian_bundle.debian_support.PackageFile.__iter__( self )
        while _pkg :
            pkg = debian_bundle.deb822.Deb822()
            pkg.update( _pkg.next() )
            yield pkg
            _pkg = debian_bundle.debian_support.PackageFile.__iter__( self )

    def rewind ( self ) :
        if self.pkgfd :
            self.pkgfd.seek(0)

    def append ( self , pkg ) :
        dump_package( pkg , self.pkgfd )

    def extend ( self , values_list ) :
        self.pkgfd.seek(0,2)
        for pkg in values_list :
            self.append( pkg )

class DebianPackageList ( DebianPackageFile , PackageListInterface ) :
    """This is an empty class required to avoid double inheritance"""

class DebianDownloadList ( DebianPackageFile , AbstractDownloadList ) :

    def __init__ ( self , repo ) :
        DebianPackageFile.__init__( self )
        AbstractDownloadList.__init__( self , repo )

    def rewind ( self ) :
        if self.started :
            raise Exception( "Trying to iterate over a running list" )
        DebianPackageFile.rewind( self )

    def append ( self , pkg ) :
        if self.closed :
            raise Exception( "Trying to append to a closed list" )
        DebianPackageFile.append( self , pkg )

class DebianDownloadThread ( DebianPackageFile , AbstractDownloadThread ) :
 
    def __init__ ( self , repo=None ) :
        AbstractDownloadThread.__init__( self , repo )
        DebianPackageFile.__init__( self )
        self.__my_cnt = 0

    def __len__ ( self ) :
        return self.__my_cnt

    def start ( self ) :
        logger.info( "Starting thread on %s %s" % ( self , self.started ) )
        AbstractDownloadThread.start( self )
        logger.info( "Starting thread on %s %s" % ( self , self.started ) )

    def __iter__ ( self ) :
        if self.started :
            raise Exception( "Trying to iterate over a running list" )
        return DebianPackageFile.__iter__( self )

    def __nonzero__ ( self ) :
        return self.index != len(self)

    def append ( self , item ) :
        """Adds an item to the download queue"""
        self.cond.acquire()
        try:
            if not self :
                # FIXME : Notification takes effect now or after release ???
                self.cond.notify()
            if self.closed :
                raise Exception( "Trying to append file '%s' to a closed thread" % item['Filename'] )
            else :
                # FIXME : this append could happen with a closed list ??
                if self.closed :
                    raise Exception( "Trying to append to a closed list" )
                DebianPackageFile.append( self , item )
                self.__my_cnt += 1
        finally:
            self.cond.release()


class debian_repository ( MirrorRepository ) :

    def __init__ ( self , config ) :
        MirrorRepository.__init__( self , config )

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
            logger.error( "Could not retrieve Release file for suite '%s'" % ( self.version ) )
            return

        if release_file is True :
            return

        release = debian_bundle.deb822.Release( sequence=open( release_file ) )

        if release['Suite'] !=  release['Codename'] :
            if release['Suite'].lower() == self.version.lower() :
                logger.error( "You have supplied suite '%s'. Please use codename '%s' instead" % ( self.version, release['Codename'] ) )
                os.unlink( release_file )
                return

        if release['Codename'].lower() != self.version.lower() :
            logger.error( "Requested version '%s' does not match with codename from Release file ('%s')" % ( self.version, release['Codename'] ) )
            os.unlink( release_file )
            return

        if release.has_key( "Components" ) :
            # NOTE : security and volatile repositories prepend a string to the actual component name
            release_comps = map( lambda s : s.rsplit("/").pop() , release['Components'].split() )

            if self.components :
                for comp in self.components :
                    if comp not in release_comps :
                        logger.error( "Component '%s' is not available ( %s )" % ( comp , " ".join(release_comps) ) )
                        return
            else :
                logger.warning( "No components specified, selected all components from Release file" )
                self.components = release_comps

        elif self.components :
            logger.error( "There is no components entry in Release file for suite '%s', please fix your configuration" % self.version )
            return
        else :
            # FIXME : This policy is taken from scratchbox repository, with no explicit component and files located right under dists along Packages file
            logger.warning( "Va que no, ni haskey, ni components" )
            self.components = ( "main" ,)

        release_archs = release['Architectures'].split()
        for arch in self.architectures :
            if arch not in release_archs :
                logger.error( "Architecture '%s' is not available ( %s )" % ( arch , " ".join(release_archs) ) )
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
            if params['usemd5'] :
                error = utils.md5_error( filename , _item )
                if error :
                    logger.warning( error )
                    os.unlink( filename )
                    return False

            return True

        else :
            logger.error( "Checksum for file '%s' not found, exiting." % _name ) 
            return False

    def get_package_list ( self , subrepo , suite_path , _params , filters ) :

        params = self.params
        params.update( _params )

        release = debian_bundle.deb822.Release( sequence=open( os.path.join( self.repo_path() , self.release ) ) )

        # NOTE : Downloading Package Release file is quite redundant

        download_size = 0
        missing_pkgs = []

        fd = False
        localname = None

        for ( extension , read_handler ) in config.extensions.iteritems() :

            _name = "%sPackages%s" % ( self.metadata_path(subrepo,True) , extension )
            localname = os.path.join( suite_path , _name )

            if os.path.isfile( localname ) :
                if self.verify( localname , _name , release , params ) :
                    # NOTE : force and unsync should behave different here? We could just force download if forced
                    if self.mode == "update" :
                        logger.warning( "Local copy of '%s' is up-to-date, skipping." % _name )
                    else :
                        fd = read_handler( localname )
                    break
                continue

        else :

            logger.warning( "No local Packages file exist for %s / %s. Downloading." % subrepo )

            for ( extension , read_handler ) in config.extensions.iteritems() :

                _name = "%sPackages%s" % ( self.metadata_path(subrepo,True) , extension )
                localname = os.path.join( suite_path , _name )
                url = urljoin( self.metadata_path() , _name )

                if self.downloadRawFile( url , localname ) :
                    if self.verify( localname , _name , release , params ) :
                        break
                    continue

            else :
                logger.error( "No Valid Packages file found for %s / %s" % subrepo )
                sys.exit(0)

            fd = read_handler( localname )

        all_pkgs = {}
        all_requires = {}

        download_pkgs = DebianPackageList()
        rejected_pkgs = DebianPackageList()

        if fd :
            packages = debian_bundle.debian_support.PackageFile( localname , fd )

# FIXME : If any minor filter is used, Packages file must be recreated for the exported repo
#         Solution : Disable filtering on first approach
#         In any case, the real problem is actually checksumming, reconstructiog Release and signing

            logger.warning( "Scanning available packages for minor filters" )
            for pkg in packages :
                pkginfo = debian_bundle.deb822.Deb822Dict( pkg )

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


