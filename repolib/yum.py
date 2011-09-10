
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

    required = ( 'destdir' , 'type' , 'url' , 'version' , 'architectures' )

    sign_ext = ".asc"

    def __init__ ( self , config ) :
        repolib.MirrorRepository.__init__( self , config )
        if self.mirror_class == "cache" :
            repolib.logger.warning( "Class 'cache' not implemented for %s (type %s)" % ( self.name , config['type'] ) )
        # NOTE : although it is a required keyword, we set default for subclassing
        self.architectures = config.get( "architectures" , [ "i386" , "x86_64" ] )
        self.__set_components( config )

    def __set_components ( self , config ) :
        for archname in self.architectures :
            subrepo = repolib.MirrorComponent.new( archname , config )
            subrepo.repo_url += os.path.join( self.base_url_extend() , subrepo.base_url_extend() )
            self.subrepos[subrepo] = subrepo

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

      for subrepo in self.subrepos.values() :
        metafile = repolib.MirrorRepository.get_metafile( self , subrepo.repomd , params )

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

        for subrepo in self.subrepos.values() :
            if self.mode == "keep" and metafiles[subrepo] is not True :
                local[subrepo] = metafiles[subrepo]
            else :
                repomd = os.path.join( subrepo.repo_path() , subrepo.repomd )
                if not isinstance(metafiles[subrepo],bool) and not os.path.exists( repomd ) :
                    self.safe_rename( metafiles[subrepo] , repomd )
                    if self.sign_ext and not os.path.exists( repomd + self.sign_ext ) and os.path.isfile( metafiles[subrepo] + self.sign_ext ):
                        self.safe_rename( metafiles[subrepo] + self.sign_ext , repomd + self.sign_ext )

                local[subrepo] = repomd

        return local

    def build_local_tree( self ) :
        repolib.MirrorRepository.build_local_tree( self )
        if self.mirror_class == "cache" :
            for subrepo in self.subrepos.values() :
                packages_path = os.path.join( subrepo.repo_path() , subrepo.metadata_path() )
                toppath = os.path.dirname( os.path.normpath( packages_path ) )
                if not os.path.exists( packages_path ) :
                    os.makedirs( packages_path )
                os.chown( toppath , repolib.webuid , repolib.webgid )

    def info ( self , metafile , cb ) :
        cb( "Mirroring version %s" % self.version )
        cb( "Source at %s" % self.base_url() )
        cb( "Subrepos : %s" % " ".join( self.subrepos ) )

    def get_download_list( self ) :
        return YumDownloadFile( self )

class YumComponent ( repolib.MirrorComponent , path_handler ) :

    def __init__ ( self , compname , config ) :
        repolib.MirrorComponent.__init__( self , compname , config )
        self.repomd = os.path.join( self.metadata_path() , "repomd.xml" )

    def metadata_path ( self , partial=False ) :
        path = self.path_prefix()
        if not partial :
            path += "repodata/"
        return path

    def match_filters( self , pkginfo , filters ) :
        if filters.has_key('groups') and pkginfo.has_key('group') and pkginfo['group'] not in filters['groups'] :
            return False
        return True

    def verify( self , filename , item , params ) :
        # FIXME : no matching on filename vs. href within item is done
        if repolib.utils.integrity_check( filename , item , params['pkgvflags'] ) :
            return True
        return False

    def get_metafile( self , metafile , _params=None ) :

        params = self.params
        if _params : params.update( _params )

        masterfile = metafile[self]

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

    def get_package_list ( self , local_repodata , _params , filters , depiter=5 ) :

        params = self.params
        params.update( _params )

        self.included = {}
        self.required = {}

        download_pkgs = self.pkg_list()
        rejected_pkgs = self.pkg_list()

        if self.mirror_class == "cache" :
            repolib.logger.warning( "Trying to get packages for %s cached repository" % self.name )
            return download_pkgs , []

        fd = gzip.open( local_repodata[0] )
        packages = xml_package_list( fd )
    
        for pkginfo in packages :

            if pkginfo['name'] not in pkginfo['provides'] :
                repolib.logger.warning( "Bad provides on '%s' : %s" % ( pkginfo['name'] , pkginfo['provides'] ) )
                pkginfo['provides'].append( pkginfo['name'] )

            pkginfo['Filename'] = os.path.join( self.metadata_path(True) , pkginfo['href'] )

            if not self.match_filters( pkginfo , filters ) :
                rejected_pkgs.append( pkginfo )
                continue

            self.handle( pkginfo )
            download_pkgs.append( pkginfo )

        fd.close()
        del packages

        if not filters :
            repolib.logger.info( "No filters defined, component assumed as complete" )
            return download_pkgs , ()

        if not self.required :
            repolib.logger.info( "No pending requirement" )
            return download_pkgs , ()

        # NOTE : run over filelists content, marking owners for inclusion
        #        expensive, lots of paths in dependencies and only a few cleaned
        repolib.logger.info( "Scanning filelists.xml for file providers" )
        filesfd = gzip.open( local_repodata[1] )

        files = xml_files_list( filesfd )
        for fileinfo in files :
            if not fileinfo.has_key( 'file' ) : continue
            # NOTE : some paths are provided by multiple packages, so no break
            for path in fileinfo['file'] :
                if self.required.has_key( path ) :
                    self.required[ fileinfo['name'] ] = 1
                    self.required.pop( path )
    
        filesfd.close()
        
        if not rejected_pkgs :

            if self.required :
                repolib.logger.warning( "No candidates to fill missing dependencies" )

        else :

            repolib.logger.info( "Scanning %s for dependencies" % self )
            for iter in range(depiter) :
                found = 0
                for pkginfo in rejected_pkgs :
                    for pkgname in pkginfo['provides'] :
                        if self.required.has_key( pkginfo['name'] ) :
                            found += 1
                            self.handle( pkginfo )
                            download_pkgs.append( pkginfo )
                            break
                if len(self.required) == 0 or found == 0 :
                    break

        missing_pkgs = []

        if self.required :
            repolib.logger.info( "There are %s missing dependencies within %s" % ( len(self.required) , self ) )
            for pkgname in self.required.keys() :
                if not self.included.has_key( pkgname ) :
                    missing_pkgs.append( pkgname )

        return download_pkgs , missing_pkgs

    def handle ( self , pkg ) :

        # NOTE : pkg name in provides, skipping explicit inclusion/exclusion

        for provides in pkg['provides'] :
            self.included[ provides ] = 1
            if self.required.has_key( provides ) :
                self.required.pop( provides )

        for pkgname in pkg.get('requires',()) :
            if not self.included.has_key( pkgname ) :
                self.required[ pkgname ] = 1

class fedora_repository ( yum_repository ) :

    required = ( 'destdir' , 'type' , 'url' , 'version' )

    sign_ext = ""

    def base_url_extend ( self ) :
        return "releases/%s/Fedora/" % self.version

    def __str__ ( self ) :
        return "fedora %s" % self.version

class FedoraComponent ( YumComponent ) :

    def path_prefix ( self ) :
        return "%s/os/" % self

    def base_url_extend ( self ) :
        return self.compname

class fedora_update_repository ( yum_repository ) :

    required = ( 'destdir' , 'type' , 'url' , 'version' )

    sign_ext = ""

    def base_url_extend ( self ) :
        return "updates/%s/" % self.version

    def __str__ ( self ) :
        return "fedora update %s" % self.version

class FedoraUpdateComponent ( YumComponent ) :

    def path_prefix ( self ) :
        return "%s/" % self

class centos_repository ( yum_repository ) :

    required = ( 'destdir' , 'type' , 'url' , 'version' )

    sign_ext = ""

    def base_url_extend ( self ) :
        return "%s/" % self.version

    def __str__ ( self ) :
        return "centos %s" % self.version

class CentosComponent ( YumComponent ) :

    def path_prefix ( self ) :
        return "os/%s/" % self

class centos_update_repository ( yum_repository ) :

    required = ( 'destdir' , 'type' , 'url' , 'version' )

    sign_ext = ""

    def base_url_extend ( self ) :
        return "%s/updates/" % self.version

    def __str__ ( self ) :
        return "centos update %s" % self.version

class CentosUpdateComponent ( YumComponent ) :

    def path_prefix ( self ) :
        return "%s/" % self


class yum_build_repository ( repolib.BuildRepository ) :

    def __init__ ( self , config , name ) :

        repolib.BuildRepository.__init__( self , config , name )

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

