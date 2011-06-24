
import filelist_xmlparser

import errno , shutil
import gzip

import os , sys
import tempfile

import config
from repolib import utils , MirrorRepository , AbstractDownloadThread
from repolib import urljoin , logger , PackageListInterface , AbstractDownloadList


class YumPackageFile :
    """This pretends to be a file base storage for package lists, to reduce memory footprint.
Is an actual complete implementation of PackageListInterface, but it is not declared
to avoid inheritance problems"""

    out_template = """name=%s
sha256=%s
size=%s
href=%s
Filename=%s

"""

    def __init__ ( self ) :
        self.pkgfd = tempfile.NamedTemporaryFile()
        self.__cnt = 0

    def __len__ ( self ) :
        return self.__cnt

    def __iter__ ( self ) :
        _pkg = {}
        self.rewind()
        line = self.pkgfd.readline()
        while line :
            if line == '\n' :
                yield _pkg
                _pkg = {}
            else :
                k,v = line[:-1].split('=',1)
                _pkg[k] = v
            line = self.pkgfd.readline()
        if _pkg :
            yield _pkg

    def rewind ( self ) :
        if self.pkgfd :
            self.pkgfd.seek(0)

    def append ( self , pkg ) :
        self.pkgfd.write( self.out_template % ( pkg['name'] , pkg.get( 'sha256' , pkg.get( 'sha' ) ) , pkg['size'] , pkg['href'] , pkg['Filename'] ) )
        self.__cnt += 1

class YumPackageList ( YumPackageFile , PackageListInterface ) :

    def extend ( self , values_list ) :
        self.pkgfd.seek(0,2)
        for pkg in values_list :
            self.append( pkg )

class YumDownloadList ( YumPackageFile , AbstractDownloadList ) :

    def __init__ ( self , repo ) :
        YumPackageFile.__init__( self )
        AbstractDownloadList.__init__( self , repo )

    def push ( self , item ) :
        if self.closed :
            raise Exception( "Trying to push into a closed queue" )
        YumPackageFile.append( self , item )

class YumDownloadThread ( YumPackageFile , AbstractDownloadThread ) :

    def __init__ ( self , repo ) :
        YumPackageFile.__init__( self )
        AbstractDownloadThread.__init__( self , repo )

    def __iter__ ( self ) :
        if self.started :
            raise Exception( "Trying to iterate over a running list" )
        return YumPackageFile.__iter__( self )


# NOTE : The xml version seems more attractive, but we cannot use it until
#        we get a way to build an iterable XML parser, maybe availeble
#        using xml.etree.ElementTree.iterparse
class YumXMLPackageList ( YumPackageFile ) :

    out_template = """<package type="rpm">
  <name>%s</name>
  <checksum type="sha256" pkgid="YES">%s</checksum>
  <size package="%s"/>
  <location href="%s"/>
  <poolfile href="%s"/>
</package>
"""

    def __init__ ( self ) :
        """Input uses a list interface, and output a sequence interface taken from original PackageFile"""
        YumPackageFile.__init__( self )
        self.pkgfd.write( '<?xml version="1.0" encoding="UTF-8"?>\n' )
        self.pkgfd.write( '<metadata xmlns="http://linux.duke.edu/metadata/common" xmlns:rpm="http://linux.duke.edu/metadata/rpm">\n' )

    def __iter__ ( self ) :
        raise Exception( "Iterable parser not yet implemented" )

    # NOTE : The flush methods move this object somewhat between a simple and a download list
    def flush ( self ) :
        self.pkgfd.write( '</metadata>\n' )


class yum_repository ( MirrorRepository ) :

    def base_url ( self ) :
        return urljoin( self.repo_url , "%s/Fedora/" % self.version )

    def repo_path ( self ) :
        return os.path.join( os.path.join( self.destdir , self.version ) , "Fedora" )

    def metadata_path ( self , partial=True ) :
        path = ""
        if not partial :
            path += "repodata/"
        return path

    def get_master_file ( self , _params , keep=False ) :

        params = self.params
        params.update( _params )

        repomd_files = {}
        for arch in self.architectures :

            metafile = self.get_signed_metafile( params , "%s/os/%srepomd.xml" % ( arch , self.metadata_path(False) ) , ".asc" , keep )

            if not metafile :
                logger.error( "Architecture '%s' is not available for version %s" % ( arch , self.version ) )
            else :

              if metafile is not True :

                logger.info( "Content verification of metafile %s" % metafile )

                item , filelist = filelist_xmlparser.get_filelist( metafile )

                if not item :
                    logger.error( "No primary node within repomd file" )
                    os.unlink( metafile )
                    metafile = False

                if not filelist :
                    logger.error( "No filelists node within repomd file" )
                    os.unlink( metafile )
                    metafile = False
    
            repomd_files[arch] = metafile

        return repomd_files

    def write_master_file ( self , repomd_file ) :

        local = {}

        for arch in repomd_file.keys() :
          if not repomd_file[arch] :
            local[arch] = False
          else :
            local[arch] = os.path.join( self.repo_path() , "%s/os/%s" % ( arch , self.metadata_path() ) )
            try :
                os.rename( repomd_file[arch] , os.path.join( local[arch] , "repodata/repomd.xml" ) )
            except OSError , ex :
                if ex.errno != errno.EXDEV :
                    print "OSError: %s" % ex
                    sys.exit(1)
                shutil.move( repomd_file[arch] , os.path.join( local[arch] , "repodata/repomd.xml" ) )

        return local

    def info ( self , metafile ) :
        str  = "Mirroring version %s\n" % self.version
        str += "%s\n" % self.repo_url
        str += "Architectures : %s\n" % " ".join(self.architectures)
        return str

    def get_subrepos ( self ) :
        _config = config.read_mirror_config( self.name )
        subrepos = []
        for arch in self.architectures :
            subrepos.append( yum_comp( _config , arch ) )
        return subrepos

    def get_download_list( self ) :
        return YumDownloadThread( self )


class yum_comp ( MirrorRepository ) :

    def __init__ ( self , config , subrepo ) :
        MirrorRepository.__init__( self , config )
        self.architectures = subrepo

    def base_url ( self ) :
        return urljoin( self.repo_url , "%s/Fedora/" % self.version )

    def repo_path ( self ) :
        return os.path.join( os.path.join( self.destdir , self.version ) , "Fedora" )

    def metadata_path ( self , partial=True ) :
        path = "%s/os/" % self.architectures
        if not partial :
            path += "repodata/"
        return path

    def match_filters( self , pkginfo , filters ) :
        if filters.has_key('groups') and pkginfo['group'] not in filters['groups'] :
            return False
        return True

    def check_packages_file( self , metafiles , _params , download=True ) :
        """
Verifies checksums and optionally downloads primary and filelist files for
an architecture.
Returns the full pathname for the file in its final destination or False when
error ocurrs. When the repository is in update mode, True is returned to signal
that the current copy is ok.
"""

        # Currently unused, but relevant to verification flags
        params = self.params
        params.update( _params )

        if not metafiles[self.architectures] :
            return False

        if download :
            local_repodata = metafiles[self.architectures]
            master_file = os.path.join( local_repodata , "repodata/repomd.xml" )
        else :
            local_repodata = os.path.join( self.repo_path() , self.metadata_path() )
            master_file = metafiles[self.architectures]

        item , filelist = filelist_xmlparser.get_filelist( master_file )

        primary = os.path.join( local_repodata , item['href'] )
    
        if os.path.isfile( primary ) :
            if utils.integrity_check( primary , item , params['pkgvflags'] ) is False :
                if not download :
                    primary = False
                else :
                    os.unlink( primary )
            else :
                if self.mode == "update" :
                    primary = True
        else :
            if not download :
                primary = False
    
        if not ( isinstance(primary,bool) or os.path.isfile( primary ) ) :
    
            logger.warning( "No local primary file exist for %s-%s. Downloading." % ( self.version , self.architectures ) )
    
            url = urljoin( self.metadata_path() , item['href'] )
    
            if self.downloadRawFile( url , primary ) :
                if utils.integrity_check( primary , item , params['pkgvflags'] ) is False :
                    os.unlink( primary )
                    primary = False
            else :
                logger.error( "Problems downloading primary file for %s-%s" % ( self.version , self.architectures ) )
                primary = False
    
        secondary = os.path.join( local_repodata , filelist['href'] )
    
        if os.path.isfile( secondary ) :
            if utils.integrity_check( secondary , filelist , params['pkgvflags'] ) is False :
                if not download :
                    secondary = False
                else :
                    os.unlink( secondary )
            else :
                if self.mode == "update" :
                    secondary = True
        else :
            if not download :
                secondary = False
    
        if not ( isinstance(secondary,bool) or os.path.isfile( secondary ) ) :
    
            logger.warning( "No local filelists file exist for %s-%s. Downloading." % ( self.version , self.architectures ) )
    
            url = urljoin( self.metadata_path() , filelist['href'] )
    
            if self.downloadRawFile( url , secondary ) :
                if utils.integrity_check( secondary , filelist , params['pkgvflags'] ) is False :
                    os.unlink( secondary )
                    secondary = False
            else :
                logger.error( "Problems downloading filelists for %s-%s" % ( self.version , self.architectures ) )
                secondary = False
    
        return primary , secondary

    def get_package_list ( self , local_repodata , _params , filters ) :

        params = self.params
        params.update( _params )

        download_size = 0
        download_pkgs = self.get_pkg_list()
        rejected_pkgs = self.get_pkg_list() 
        missing_pkgs = []

        fd = gzip.open( local_repodata[0] )
        packages = filelist_xmlparser.get_package_list( fd )
    
        all_pkgs = {}
        providers = {}

        logger.warning( "Scanning available packages for minor filters" )
        for pkginfo in packages :
    
# FIXME : If any minor filter is used, Packages file must be recreated for the exported repo
#         Solution : Disable filtering on first approach
#         In any case, the real problem is actually checksumming, reconstructiog Release and signing
    
            if not self.match_filters( pkginfo , filters ) :
                rejected_pkgs.append( pkginfo )
                continue

            all_pkgs[ pkginfo['name'] ] = 1
            pkginfo['Filename'] = os.path.join( self.metadata_path() , pkginfo['href'] )
            download_pkgs.append( pkginfo )
            # FIXME : This might cause a ValueError exception ??
            download_size += pkginfo['size']

            if pkginfo.has_key( 'requires' ) :
                for pkg in pkginfo['requires'] :
                    providers[ pkg ] = 1

        filesfd = gzip.open( local_repodata[1] )

        # NOTE : We run over the filelists content, marking package owners for later addition
        logger.warning( "Scanning filelists.xml for file dependencies" )
        files = filelist_xmlparser.get_files_list( filesfd )
        for fileinfo in files :
            if not fileinfo.has_key( 'file' ) : continue
            pkg = fileinfo[ 'name' ]
            # There are multiple packages providing the same item, so we cannot break on matches
            for file in fileinfo[ 'file' ] :
                if providers.has_key( file ) :
                    providers[ pkg ] = 1
    
        filesfd.close()
        
        logger.warning( "Searching for missing dependencies" )
        for pkginfo in rejected_pkgs :
        
            # NOTE : There are some cases of packages requiring themselves, so we cannot jump to next
            #if all_pkgs.has_key( pkginfo['name'] ) :
            #    continue

            if providers.has_key( pkginfo['name'] ) :
                all_pkgs[ pkginfo['name'] ] = 1
                pkginfo['Filename'] = os.path.join( self.metadata_path() , pkginfo['href'] )
                download_pkgs.append( pkginfo )
                # FIXME : This might cause a ValueError exception ??
                download_size += int( pkginfo['size'] )
                providers.pop( pkginfo['name'] )

            elif pkginfo.has_key( 'provides' ) :
                for pkg in pkginfo['provides'] :
                    # There are multiple packages providing the same item, so we cannot break on matches

                    # FIXME : We made no attempt to go into a full depenceny loop
                    if providers.has_key( pkg ) :
                    
                        all_pkgs[ pkginfo['name'] ] = 1
                        pkginfo['Filename'] = os.path.join( self.metadata_path() , pkginfo['href'] )
                        download_pkgs.append( pkginfo )
                        # FIXME : This might cause a ValueError exception ??
                        download_size += int( pkginfo['size'] )

#                        if pkginfo.has_key( 'requires' ) :
#                            for reqpkg in pkginfo['requires'] :
#                                providers[ reqpkg ] = 1

        # Rewind file
        fd.seek(0)

        logger.warning( "Running to filter out fixed dependencies" )
        packages = filelist_xmlparser.get_package_list( fd )
        for pkginfo in packages :
            if not all_pkgs.has_key( pkginfo['name'] ) :
                continue
            if pkginfo.has_key( 'provides' ) :
                for pkg in pkginfo['provides'] :
                    if providers.has_key( pkg ) :
                        providers.pop( pkg )
        
        fd.close()
        del packages

        for pkgname in providers.keys() :
            if not all_pkgs.has_key( pkgname ) :
                missing_pkgs.append( pkgname )

        logger.warning( "Current download size : %.1f Mb" % ( download_size / 1024 / 1024 ) )

        return download_size , download_pkgs , missing_pkgs

    def get_pkg_list( self ) :
        return YumPackageList()


class fedora_update_repository ( yum_repository ) :

    def __init__ ( self , config ) :
        yum_repository.__init__( self , config )

    def base_url ( self ) :
        return urljoin( self.repo_url , "%s/" % self.version )

    def repo_path ( self ) :
        return os.path.join( self.destdir , self.version )

    def metadata_path ( self , subrepo=None , partial=True ) :
        path = ""
        if subrepo :
            path += "%s/" % subrepo
        if not partial :
            path += "repodata/"
        return path

class centos_repository ( yum_repository ) :

    def base_url ( self ) :
        return urljoin( self.repo_url , "%s/" % self.version )

    def repo_path ( self ) :
        return os.path.join( self.destdir , self.version )

    def metadata_path ( self , subrepo=None , partial=True ) :
        path = ""
        if subrepo :
            path += "os/%s/" % subrepo
        if not partial :
            path += "repodata/"
        return path

class centos_update_repository ( centos_repository ) :

    def metadata_path ( self , subrepo=None , partial=True ) :
        path = ""
        if subrepo :
            path += "updates/%s/" % subrepo
        if not partial :
            path += "repodata/"
        return path

class yast2_repository ( yum_repository ) :

    def base_url ( self ) :
        return urljoin( self.repo_url , "distribution/%s/repo/oss/suse/" % self.version )

    def repo_path ( self ) :
        return os.path.join( self.destdir , "distribution/%s" % self.version )

    def metadata_path ( self , subrepo=None , partial=True ) :
        path = ""
        # FIXME : No subrepos available for OpenSuSE
        if not partial :
            path += "repodata/"
        return path

class yast2_update_repository ( yast2_repository ) :

    def base_url ( self ) :
        return urljoin( self.repo_url , "update/%s/" % self.version )

    def repo_path ( self ) :
        return os.path.join( self.destdir , "update/%s" % self.version )

