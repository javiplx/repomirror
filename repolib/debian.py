
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
        self.__cnt = 0

    def __len__ ( self ) :
        return self.__cnt

    def __iter__ ( self ) :
        self.rewind()
        _pkg = debian_bundle.debian_support.PackageFile.__iter__( self )
        while _pkg :
            pkg = debian_bundle.deb822.Deb822()
            pkg.update( _pkg.next() )
            yield pkg
            _pkg = debian_bundle.debian_support.PackageFile.__iter__( self )

    # This is a final method, not overridable
    def rewind ( self ) :
        if self.pkgfd :
            self.pkgfd.seek(0)

    def append ( self , pkg ) :
        dump_package( pkg , self.pkgfd )
        self.__cnt += 1

class DebianPackageList ( DebianPackageFile , PackageListInterface ) :

    def extend ( self , values_list ) :
        self.pkgfd.seek(0,2)
        for pkg in values_list :
            self.append( pkg )

class DebianDownloadList ( DebianPackageFile , AbstractDownloadList ) :

    def __init__ ( self , repo ) :
        DebianPackageFile.__init__( self )
        AbstractDownloadList.__init__( self , repo )

    def __iter__ ( self ) :
        if self.started :
            raise Exception( "Trying to iterate over a running list" )
        return DebianPackageFile.__iter__( self )

    def push ( self , pkg ) :
        if self.closed :
            raise Exception( "Trying to push into a closed queue" )
        DebianPackageFile.append( self , pkg )

class DebianDownloadThread ( DebianPackageFile , AbstractDownloadThread ) :
 
    def __init__ ( self , repo=None ) :
        AbstractDownloadThread.__init__( self , repo )
        DebianPackageFile.__init__( self )

    def __iter__ ( self ) :
        if self.started :
            raise Exception( "Trying to iterate over a running list" )
        return DebianPackageFile.__iter__( self )


import feed

class debian_feed ( feed.feed_repository ) :

    def __init__ ( self , config , subrepo ) :
        self.subrepo = subrepo
        feed.feed_repository.__init__( self , config )

    def metadata_path ( self , subrepo=None , partial=False ) :
        return "dists/%s/%s/binary-%s/" % ( self.version , self.subrepo[0] , self.subrepo[1] )


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

    def get_master_file ( self , _params , keep=False ) :

        params = self.params
        params.update( _params )

        release_file = self.get_signed_metafile ( params , self.release , ".gpg" , keep )

        version = self.version.split("/")[0].lower()
        if not release_file :
            logger.error( "No valid Release file for suite '%s'" % ( self.version ) )
            return { '':release_file }
        elif release_file is True :
            return { '':True }

        logger.info( "Content verification of metafile %s" % release_file )
        release = debian_bundle.deb822.Release( sequence=open( release_file ) )

        if release['Suite'] !=  release['Codename'] :
            if release['Suite'].lower() == version :
                logger.error( "You have supplied suite '%s'. Please use codename '%s' instead" % ( self.version, release['Codename'] ) )
                os.unlink( release_file )
                return { '':False }

        if release['Codename'].lower() != version :
            logger.error( "Requested version '%s' does not match with codename from Release file ('%s')" % ( self.version, release['Codename'] ) )
            os.unlink( release_file )
            return { '':False }

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
            logger.error( "There is no components entry in Release file for suite '%s', please fix your configuration" % self.version )
            return { '':False }
        else :
            # FIXME : This policy is taken from scratchbox repository, with no explicit component and files located right under dists along Packages file
            logger.warning( "Va que no, ni haskey, ni components" )
            self.components = ( "main" ,)

        release_archs = release['Architectures'].split()
        for arch in self.architectures :
            if arch not in release_archs :
                logger.error( "Architecture '%s' is not available ( %s )" % ( arch , " ".join(release_archs) ) )
                return { '':False }

        return { '':release_file }

    def write_master_file ( self , release_file ) :

        local = os.path.join( self.repo_path() , self.release )

        # FIXME : If we reach this point, is it possible that the file is still there ?
        if not os.path.exists( local ) :
            try :
                os.rename( release_file[''] , local )
            except OSError , ex :
                if ex.errno != errno.EXDEV :
                    print "OSError: %s" % ex
                    sys.exit(1)
                shutil.move( release_file[''] , local )

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
            if utils.integrity_check( filename , _item ) is False :
                os.unlink( filename )
                return False

            return True

        else :
            logger.error( "Checksum for file '%s' not found, exiting." % _name ) 
            return False

    def check_packages_file( self , subrepo , metafile , _params , download=True ) :
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
            master_file = os.path.join( self.repo_path() , self.release )
        else :
            master_file = metafile['']
        suite_path = os.path.join( self.repo_path() , self.metadata_path() )

        release = debian_bundle.deb822.Release( sequence=open( master_file ) )

        localname = False

        for ( extension , read_handler ) in config.mimetypes.iteritems() :

            _name = "%sPackages%s" % ( self.metadata_path(subrepo,True) , extension )
            localname = os.path.join( suite_path , _name )

            if os.path.isfile( localname ) :
                if self.verify( localname , _name , release , params ) :
                    if self.mode == "update" :
                        logger.warning( "Local copy of '%s' is up-to-date, skipping." % _name )
                        return True
                    break
                continue

        else :

          if download :
            # NOTE : Download of Package Release file is quite redundant

            logger.warning( "No local Packages file exist for %s / %s. Downloading." % subrepo )

            for ( extension , read_handler ) in config.mimetypes.iteritems() :

                _name = "%sPackages%s" % ( self.metadata_path(subrepo,True) , extension )
                localname = os.path.join( suite_path , _name )
                url = urljoin( self.metadata_path() , _name )

                if self.downloadRawFile( url , localname ) :
                    if self.verify( localname , _name , release , params ) :
                        break
                    continue

            else :
                logger.error( "No Valid Packages file found for %s / %s" % subrepo )
                localname = False
          else :
            localname = False

        if isinstance(localname,bool) :
            return localname

        return read_handler( localname )

    def get_pkg_list( self ) :
        return DebianPackageList()

    def get_download_list( self ) :
        return DebianDownloadThread( self )


class debian_build_repository ( BuildRepository ) :

    def __init__ ( self , config ) :

        BuildRepository.__init__( self , config )

        self.components = config.get( "components" , None )


