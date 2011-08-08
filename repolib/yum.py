
import filelist_xmlparser

import gzip

import os , sys

import repolib
from lists.yum import *

try :
    sys.path.append( '/usr/share/createrepo' )
    import genpkgmetadata
except Exception , ex :
    genpkgmetadata = False


class path_handler :
    """This object is intended to allow reworking of local and remote paths.
Main purpose is to allow base and update repositories to share a common url,
while enabling finding proper paths from that location. It is needed for YUM
repositories because repositories are usually decoupled.
This functionality has been extracted to a separate class to increase
visibility of methods overloaded on yum_repository object.
"""

    def base_url_extend ( self ) :
        return ""

    def path_prefix ( self ) :
        return ""


class yum_repository ( repolib.MirrorRepository , path_handler ) :

    sign_ext = ".asc"

    def __init__ ( self , config ) :
        repolib.MirrorRepository.__init__( self , config )
        for archname in self.architectures :
            subrepo = repolib.MirrorComponent.new( archname , config )
            subrepo.repo_url += os.path.join( self.base_url_extend() , subrepo.base_url_extend() )
            self.subrepos.append( subrepo )
        self.repomd = {}
        for subrepo in self.subrepos :
            self.repomd[subrepo] = os.path.join( subrepo.metadata_path() , "repomd.xml" )

    def repo_path ( self ) :
        return os.path.join( self.destdir , self.version )

    def base_url ( self ) :
        return repolib.MirrorRepository.base_url(self) + self.base_url_extend()

    def metadata_path ( self , partial=False ) :
        path = self.path_prefix()
        if not partial :
            path += "repodata/"
        return path

    def get_metafile ( self , _params=None , keep=False ) :

      params = self.params
      if _params : params.update( _params )

      repomd = {}

      for subrepo in self.subrepos :
        metafile = repolib.MirrorRepository.get_metafile( self , self.repomd[subrepo] , params , keep )

        if not metafile :
            repolib.logger.error( "Metadata for '%s' not found" % self.version )
        else :
            if metafile is not True :
                repolib.logger.info( "Content verification of metafile %s" % metafile )
                item , filelist = filelist_xmlparser.get_filelist( metafile )

                if not item or not filelist :
                    repolib.logger.error( "No primary or filelist node within repomd file" )
                    os.unlink( metafile )
                    metafile = False
    
        # NOTE : the initial implementation did return an empty dictionary if metafile is false
        repomd[ subrepo ] = metafile

      return repomd

    def write_master_file ( self , repomd_file ) :

        local = {}

        for subrepo in self.subrepos :
            if repomd_file[subrepo] :
                self.safe_rename( repomd_file[subrepo] , os.path.join( subrepo.repo_path() , self.repomd[subrepo] ) )

                if sign_ext and os.path.isfile( repomd_file[subrepo] + sign_ext ) :
                    self.safe_rename( repomd_file[subrepo] + sign_ext , os.path.join( subrepo.repo_path() , self.repomd[subrepo] + sign_ext ) )

                local[ subrepo ] = os.path.join( subrepo.repo_path() , subrepo.metadata_path(True) )
            else :
                local[ subrepo ] = False

        return local

    def info ( self , metafile ) :
        str  = "Mirroring version %s\n" % self.version
        str += "Source at %s\n" % self.base_url()
        str += "Subrepos : %s\n" % " ".join( map( lambda x : "%s" % x , self.subrepos ) )
        return str

    def get_download_list( self ) :
        return YumDownloadThread( self )

class YumComponent ( repolib.MirrorComponent , path_handler ) :

    def repo_path ( self ) :
        return os.path.join( self.destdir , self.version )

    def metadata_path ( self , partial=False ) :
        path = self.path_prefix()
        if not partial :
            path += "repodata/"
        return path

    def match_filters( self , pkginfo , filters ) :
        if filters.has_key('groups') and pkginfo.has_key('groups') and pkginfo['group'] not in filters['groups'] :
            return False
        return True

    def verify( self , filename , item , params ) :
        # FIXME : no matching on filename vs. href within item is done
        if repolib.utils.integrity_check( filename , item , params['pkgvflags'] ) is False :
            os.unlink( filename )
            return False
        return True

    def get_metafile( self , metafile , _params=None , download=True ) :
        """Verifies checksums and optionally downloads primary and filelist files for
an architecture.
Returns the full pathname for the file in its final destination or False when
error ocurrs. When the repository is in update mode, True is returned to signal
that the current copy is ok.
"""

        # Currently unused, but relevant to verification flags
        params = self.params
        if _params : params.update( _params )

        if not metafile[self] :
            return False

        if download :
            local_repodata = metafile[self]
            master_file = os.path.join( local_repodata , "repodata/repomd.xml" )
        else :
            local_repodata = os.path.join( self.repo_path() , self.metadata_path(True) )
            master_file = metafile[self]

        primary , secondary = False , False

        item , filelist = filelist_xmlparser.get_filelist( master_file )

        _primary = os.path.join( local_repodata , item['href'] )
    
        if os.path.isfile( _primary ) :
            if self.verify( _primary , item , params ) :
                primary = True
                if self.mode == "init" :
                    primary = _primary
    
        if not primary :
    
          if download :

            repolib.logger.warning( "No local primary file exist for %s-%s. Downloading." % ( self.version , self ) )
    
            url = repolib.utils.urljoin( self.metadata_path(True) , item['href'] )
    
            if self.downloadRawFile( url , _primary ) :
                if self.verify( _primary , item , params ) :
                    primary = _primary
    
        _secondary = os.path.join( local_repodata , filelist['href'] )
    
        if os.path.isfile( _secondary ) :
            if self.verify( _secondary , filelist , params ) :
                secondary = True
                if self.mode == "init" :
                    secondary = _secondary
    
        if not secondary :
    
          if download :

            repolib.logger.warning( "No local filelists file exist for %s-%s. Downloading." % ( self.version , self ) )
    
            url = repolib.utils.urljoin( self.metadata_path(True) , filelist['href'] )
    
            if self.downloadRawFile( url , _secondary ) :
                if self.verify( _secondary , filelist , params ) :
                    secondary = _secondary
    
        # Workaround for easily detect True,True and False,False pairs
        if primary == secondary and isinstance(primary,bool) :
            return primary

        return primary , secondary

    def pkg_list( self ) :
        return YumPackageFile()

    def get_package_list ( self , local_repodata , _params , filters ) :

        params = self.params
        params.update( _params )

        download_size = 0
        download_pkgs = self.pkg_list()
        rejected_pkgs = self.pkg_list()
        missing_pkgs = []

        fd = gzip.open( local_repodata[0] )
        packages = filelist_xmlparser.get_package_list( fd )
    
        all_pkgs = {}
        providers = {}

        repolib.logger.warning( "Scanning available packages for minor filters" )
        for pkginfo in packages :
    
# FIXME : If any minor filter is used, Packages file must be recreated for the exported repo
#         Solution : Disable filtering on first approach
#         In any case, the real problem is actually checksumming, reconstructiog Release and signing
    
            if not self.match_filters( pkginfo , filters ) :
                rejected_pkgs.append( pkginfo )
                continue

            all_pkgs[ pkginfo['name'] ] = 1
            pkginfo['Filename'] = os.path.join( self.metadata_path(True) , pkginfo['href'] )
            download_pkgs.append( pkginfo )
            # FIXME : This might cause a ValueError exception ??
            download_size += pkginfo['size']

            if pkginfo.has_key( 'requires' ) :
                for pkg in pkginfo['requires'] :
                    providers[ pkg ] = 1

        filesfd = gzip.open( local_repodata[1] )

        # NOTE : We run over the filelists content, marking package owners for later addition
        repolib.logger.warning( "Scanning filelists.xml for file dependencies" )
        files = filelist_xmlparser.get_files_list( filesfd )
        for fileinfo in files :
            if not fileinfo.has_key( 'file' ) : continue
            pkg = fileinfo[ 'name' ]
            # There are multiple packages providing the same item, so we cannot break on matches
            for file in fileinfo[ 'file' ] :
                if providers.has_key( file ) :
                    providers[ pkg ] = 1
    
        filesfd.close()
        
        repolib.logger.warning( "Searching for missing dependencies" )
        for pkginfo in rejected_pkgs :
        
            # NOTE : There are some cases of packages requiring themselves, so we cannot jump to next
            #if all_pkgs.has_key( pkginfo['name'] ) :
            #    continue

            if providers.has_key( pkginfo['name'] ) :
                all_pkgs[ pkginfo['name'] ] = 1
                pkginfo['Filename'] = os.path.join( self.metadata_path(True) , pkginfo['href'] )
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
                        pkginfo['Filename'] = os.path.join( self.metadata_path(True) , pkginfo['href'] )
                        download_pkgs.append( pkginfo )
                        # FIXME : This might cause a ValueError exception ??
                        download_size += int( pkginfo['size'] )

#                        if pkginfo.has_key( 'requires' ) :
#                            for reqpkg in pkginfo['requires'] :
#                                providers[ reqpkg ] = 1

        # Rewind file
        fd.seek(0)

        repolib.logger.warning( "Running to filter out fixed dependencies" )
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

        repolib.logger.warning( "Current download size : %.1f Mb" % ( download_size / 1024 / 1024 ) )

        return download_size , download_pkgs , missing_pkgs

class fedora_repository ( yum_repository ) :

    sign_ext = False

    def base_url_extend ( self ) :
        return "releases/%s/Fedora/" % self.version

class FedoraComponent ( YumComponent ) :

    def path_prefix ( self ) :
        return "%s/os/" % self

    def base_url_extend ( self ) :
        return self.architectures[0]

class fedora_update_repository ( yum_repository ) :

    sign_ext = False

    def base_url_extend ( self ) :
        return "updates/%s/" % self.version

class FedoraUpdateComponent ( YumComponent ) :

    def path_prefix ( self ) :
        return "%s/" % self

class centos_repository ( yum_repository ) :

    sign_ext = False

    def base_url_extend ( self ) :
        return "%s/" % self.version

class CentosComponent ( YumComponent ) :

    def path_prefix ( self ) :
        return "os/%s/" % self

class centos_update_repository ( yum_repository ) :

    sign_ext = False

    def base_url_extend ( self ) :
        return "%s/updates/" % self.version

class CentosUpdateComponent ( YumComponent ) :

    def path_prefix ( self ) :
        return "%s/" % self


class yum_build_repository ( repolib.BuildRepository ) :

    def __init__ ( self , config , name ) :

        repolib.BuildRepository.__init__( self , config )

        self.name = name

        if not genpkgmetadata :
            raise Exception( "Missing requierements : create repo is required to build yum repositories" )

        if genpkgmetadata.__version__ != '0.4.9' :
            repolib.logger.warning( "Found createrepo %s (expected 0.4.9), notify any error" % genpkgmetadata.__version__ )

        if config.has_key( "extensions" ) :
            repolib.logger.warning( "Fix configuration : 'extensions' is not a valid keyword for yum repositories" )

	if not os.path.isdir( self.repo_path() ) :
            raise Exception( "Repository directory %s does not exists" % self.repo_path() )

    def build ( self ) :

        cmds , directories = genpkgmetadata.parseArgs( [ "dummy" ] )
        directory = os.path.basename( self.repo_path() )
        cmds['quiet'] = True
        cmds['basedir'] = os.path.dirname( self.repo_path() )
        cmds['outputdir'] = self.repo_path()

        olddir = os.path.join( self.repo_path() , cmds['olddir'] )
        if os.path.exists( olddir ) :
            repolib.logger.critical( "Old data directory exists, remove: %s" % olddir )
            return

        mdgen = genpkgmetadata.MetaDataGenerator(cmds)
        if mdgen.checkTimeStamps( directory ):
            repolib.logger.info( "repository '%s' is up to date" % self.name )
            return

        tempdir = os.path.join( self.repo_path() , cmds['tempdir'] )
        if not os.path.isdir( tempdir ) :
            os.mkdir( tempdir )

        mdgen.doPkgMetadata( directory )
        mdgen.doRepoMetadata()

        finaldir = os.path.join( self.repo_path() , cmds['finaldir'] )
        if os.path.exists( finaldir ) :
            os.rename( finaldir , olddir )

        os.rename( tempdir , finaldir )
        if os.path.exists( olddir ) :
            map( lambda x : os.unlink( os.path.join( olddir , x ) ) , os.listdir(olddir) )
            os.rmdir( olddir )

