
import gzip

import os , sys

import repolib
from lists.yum import *
from lists.yum_xml import *

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
            self.subrepos.update( { str(subrepo) : subrepo } )
        self.repomd = {}
        for name,subrepo in self.subrepos.iteritems() :
            self.repomd[name] = os.path.join( subrepo.metadata_path() , "repomd.xml" )

    def repo_path ( self ) :
        return os.path.join( self.destdir , self.version )

    def base_url ( self ) :
        return repolib.MirrorRepository.base_url(self) + self.base_url_extend()

    def metadata_path ( self , partial=False ) :
        path = self.path_prefix()
        if not partial :
            path += "repodata/"
        return path

    def get_metafile ( self , _params=None ) :

      params = self.params
      if _params : params.update( _params )

      repomd = {}

      for subrepo in self.subrepos :
        metafile = repolib.MirrorRepository.get_metafile( self , self.repomd[subrepo] , params )

        if not metafile :
            repolib.logger.error( "Metadata for '%s-%s' not found" % ( subrepo , self.version ) )
        elif metafile is not True :
                repolib.logger.info( "Content verification of metafile %s" % metafile )
                item , filelist = xml_filelist( metafile )

                if not item or not filelist :
                    repolib.logger.error( "No primary or filelist node within repomd file" )
                    if self.mode != "keep" :
                        os.unlink( metafile )
                    metafile = False
    
        repomd[ subrepo ] = metafile

      return repomd

    def write_master_file ( self , metafiles ) :

        local = {}

        for name,subrepo in self.subrepos.iteritems() :
          if self.mode == "keep" and metafiles[name] is not True :
            local[name] = metafiles[name]
          else :
            repomd = os.path.join( subrepo.repo_path() , self.repomd[name] )
            if not isinstance(metafiles[name],bool) and not os.path.exists( repomd ) :
                    self.safe_rename( metafiles[name] , repomd )
                    if self.sign_ext and not os.path.exists( repomd + self.sign_ext ) :
                        self.safe_rename( metafiles[name] + self.sign_ext , repomd + self.sign_ext )

            local[name] = repomd

        return local

    def info ( self , metafile , cb ) :
        cb( "Mirroring version %s" % self.version )
        cb( "Source at %s" % self.base_url() )
        cb( "Subrepos : %s" % " ".join( self.subrepos ) )

    def get_download_list( self ) :
        return YumDownloadThread( self )
        return YumDownloadFile( self )

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
            return False
        return True

    def get_metafile( self , metafile , _params=None ) :

        params = self.params
        if _params : params.update( _params )

        masterfile = metafile[str(self)]

        if isinstance(masterfile,bool) :
            raise Exception( "Calling %s.get_metafile( %s )" % ( self , metafile ) )

        # FIXME : the same extraction was already performed on master.get_metafile()
        item , filelist = xml_filelist( masterfile )
        local_repodata = os.path.join( self.repo_path() , self.metadata_path(True) )

        primary , secondary = False , False

        _primary = os.path.join( local_repodata , item['href'] )
    
        if os.path.isfile( _primary ) :
            if self.verify( _primary , item , params ) :
                primary = True
                if self.mode == "init" :
                    primary = _primary
    
        if not primary and self.mode != "keep" :
            repolib.logger.warning( "No local primary file exist for %s. Downloading." % self )
            url = repolib.utils.urljoin( self.metadata_path(True) , item['href'] )
            if self.downloadRawFile( url , _primary ) :
                if self.verify( _primary , item , params ) :
                    primary = _primary
                else:
                    os.unlink( _primary )
    
        _secondary = os.path.join( local_repodata , filelist['href'] )
    
        if os.path.isfile( _secondary ) :
            if self.verify( _secondary , filelist , params ) :
                secondary = True
                if self.mode == "init" :
                    secondary = _secondary
    
        if not secondary and self.mode != "keep" :
            repolib.logger.warning( "No local filelists file exist for %s. Downloading." % self )
            url = repolib.utils.urljoin( self.metadata_path(True) , filelist['href'] )
            if self.downloadRawFile( url , _secondary ) :
                if self.verify( _secondary , filelist , params ) :
                    secondary = _secondary
                else :
                    os.unlink( _secondary )
    
        # Workarounds to detect booleans within output
        if False in ( primary , secondary ) :
            return False
        if primary == secondary and isinstance(primary,bool) :
            return primary

        return primary , secondary

    def pkg_list( self ) :
        return YumPackageFile()

    def get_package_list ( self , local_repodata , _params , filters ) :

        params = self.params
        params.update( _params )

        download_pkgs = self.pkg_list()
        rejected_pkgs = self.pkg_list()
        missing_pkgs = []

        fd = gzip.open( local_repodata[0] )
        packages = xml_package_list( fd )
    
        all_pkgs = {}
        providers = {}

        repolib.logger.warning( "Scanning available %s packages for minor filters" % self )
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

            if pkginfo.has_key( 'requires' ) :
                for pkg in pkginfo['requires'] :
                    providers[ pkg ] = 1

        fd.close()
        del packages
        return download_pkgs , missing_pkgs
        filesfd = gzip.open( local_repodata[1] )

        # NOTE : We run over the filelists content, marking package owners for later addition
        repolib.logger.info( "Scanning filelists.xml for file dependencies" )
        files = xml_files_list( filesfd )
        for fileinfo in files :
            if not fileinfo.has_key( 'file' ) : continue
            pkg = fileinfo[ 'name' ]
            # There are multiple packages providing the same item, so we cannot break on matches
            for file in fileinfo[ 'file' ] :
                if providers.has_key( file ) :
                    providers[ pkg ] = 1
    
        filesfd.close()
        
        repolib.logger.info( "Searching for missing dependencies" )
        for pkginfo in rejected_pkgs :
        
            # NOTE : There are some cases of packages requiring themselves, so we cannot jump to next
            #if all_pkgs.has_key( pkginfo['name'] ) :
            #    continue

            if providers.has_key( pkginfo['name'] ) :
                all_pkgs[ pkginfo['name'] ] = 1
                pkginfo['Filename'] = os.path.join( self.metadata_path(True) , pkginfo['href'] )
                download_pkgs.append( pkginfo )
                providers.pop( pkginfo['name'] )

            elif pkginfo.has_key( 'provides' ) :
                for pkg in pkginfo['provides'] :
                    # There are multiple packages providing the same item, so we cannot break on matches

                    # FIXME : We made no attempt to go into a full depenceny loop
                    if providers.has_key( pkg ) :
                    
                        all_pkgs[ pkginfo['name'] ] = 1
                        pkginfo['Filename'] = os.path.join( self.metadata_path(True) , pkginfo['href'] )
                        download_pkgs.append( pkginfo )

#                        if pkginfo.has_key( 'requires' ) :
#                            for reqpkg in pkginfo['requires'] :
#                                providers[ reqpkg ] = 1

        # Rewind file
        fd.seek(0)

        repolib.logger.info( "Running to filter out fixed dependencies" )
        packages = xml_package_list( fd )
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

        return download_pkgs , missing_pkgs

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

