
import filelist_xmlparser

import gzip

import os , sys

import repolib
from lists.yum import *


class yum_repository ( repolib.MirrorRepository ) :

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

    def base_url_extend ( self ) :
        return ""

    def path_prefix ( self ) :
        return ""

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
            repolib.logger.error( "Repository for %s is not available" % self.version )
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

                if os.path.isfile( repomd_file[subrepo] + ".asc" ) :
                    self.safe_rename( repomd_file[subrepo] + ".asc" , os.path.join( subrepo.repo_path() , self.repomd[subrepo] + ".asc" ) )

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

class YumComponent ( repolib.MirrorComponent ) :

    def base_url_extend ( self ) :
        return ""

    def path_prefix ( self ) :
        return ""

    def metadata_path ( self , partial=False ) :
        path = self.path_prefix()
        if not partial :
            path += "repodata/"
        return path

    def match_filters( self , pkginfo , filters ) :
        if filters.has_key('groups') and pkginfo.has_key('groups') and pkginfo['group'] not in filters['groups'] :
            return False
        return True

    def get_metafile( self , metafiles , _params=None , download=True ) :
        """
Verifies checksums and optionally downloads primary and filelist files for
an architecture.
Returns the full pathname for the file in its final destination or False when
error ocurrs. When the repository is in update mode, True is returned to signal
that the current copy is ok.
"""

        # Currently unused, but relevant to verification flags
        params = self.params
        if _params : params.update( _params )

        if not metafiles[self] :
            return False

        if download :
            local_repodata = metafiles[self]
            master_file = os.path.join( local_repodata , "repodata/repomd.xml" )
        else :
            local_repodata = os.path.join( self.repo_path() , self.metadata_path(True) )
            master_file = metafiles[self]

        item , filelist = filelist_xmlparser.get_filelist( master_file )

        primary = os.path.join( local_repodata , item['href'] )
    
        if os.path.isfile( primary ) :
            if repolib.utils.integrity_check( primary , item , params['pkgvflags'] ) is False :
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
    
            repolib.logger.warning( "No local primary file exist for %s-%s. Downloading." % ( self.version , self ) )
    
            url = repolib.utils.urljoin( self.metadata_path(True) , item['href'] )
    
            if self.downloadRawFile( url , primary ) :
                if repolib.utils.integrity_check( primary , item , params['pkgvflags'] ) is False :
                    os.unlink( primary )
                    primary = False
            else :
                repolib.logger.error( "Problems downloading primary file for %s-%s" % ( self.version , self ) )
                primary = False
    
        secondary = os.path.join( local_repodata , filelist['href'] )
    
        if os.path.isfile( secondary ) :
            if repolib.utils.integrity_check( secondary , filelist , params['pkgvflags'] ) is False :
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
    
            repolib.logger.warning( "No local filelists file exist for %s-%s. Downloading." % ( self.version , self ) )
    
            url = repolib.utils.urljoin( self.metadata_path(True) , filelist['href'] )
    
            if self.downloadRawFile( url , secondary ) :
                if repolib.utils.integrity_check( secondary , filelist , params['pkgvflags'] ) is False :
                    os.unlink( secondary )
                    secondary = False
            else :
                repolib.logger.error( "Problems downloading filelists for %s-%s" % ( self.version , self ) )
                secondary = False
    
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
        return "%s/os/" % self.version

class CentosComponent ( YumComponent ) :

    def path_prefix ( self ) :
        return "%s/" % self

class centos_update_repository ( yum_repository ) :

    sign_ext = False

    def base_url_extend ( self ) :
        return "%s/updates/" % self.version

class CentosUpdateComponent ( YumComponent ) :

    def path_prefix ( self ) :
        return "%s/" % self

