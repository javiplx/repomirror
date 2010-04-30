
import filelist_xmlparser

import repoutils

import urllib2
import errno , shutil
import gzip

import os , sys

from repolib import abstract_repository


class yum_repository ( abstract_repository ) :

    def base_url ( self ) :
        return urllib2.urlparse.urljoin( self.repo_url , "%s/Fedora/" % self.version )

    def repo_path ( self ) :
        return os.path.join( os.path.join( self.destdir , self.version ) , "Fedora" )

    def metadata_path ( self , subrepo=None , partial=True ) :
        path = ""
        if subrepo :
            path += "%s/os/" % subrepo
        if not partial :
            path += "repodata/"
        return path

    def get_master_file ( self , _params ) :

        params = self.params
        params.update( _params )

        repomd_files = {}
        for arch in self.architectures :

            metafile = self.get_signed_metafile ( params , "%srepomd.xml" % self.metadata_path(arch,False) )

            if not metafile :
                repoutils.show_error( "Architecture '%s' is not available for version %s" % ( arch , self.version ) )
                # FIXME : here we could be removing files from their final locations
                for file in repomd_files.values() :
                    os.unlink( file )
                return

            if metafile is not True :
                repomd_files[arch] = metafile

        return repomd_files

    def write_master_file ( self , repomd_file ) :

        local = {}

        for arch in repomd_file.keys() :
            local[arch] = os.path.join( self.repo_path() , self.metadata_path(arch) )
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
        return self.architectures

    def match_filters( self , pkginfo , filters ) :
        if filters.has_key('groups') and pkginfo['group'] not in filters['groups'] :
            return True
        return False

    def get_package_list ( self , arch , local_repodata , _params , filters ) :

        params = self.params
        params.update( _params )

        download_size = 0
        download_pkgs = []
        missing_pkgs = []

        item = filelist_xmlparser.get_filelist( os.path.join( local_repodata[arch] , "repodata/repomd.xml" ) )

        if not item :
            repoutils.show_error( "No primary node within repomd file" )
            os.unlink( os.path.join( local_repodata[arch] , "repodata/repomd.xml" ) )
            sys.exit(255)
    
        # FIXME : On problems, exit or continue next arch ???
    
        localname = os.path.join( local_repodata[arch] , item['href'] )
    
        if os.path.isfile( localname ) :
            error = repoutils.md5_error( localname , item , item.has_key('size') | repoutils.SKIP_SIZE )
            if error :
                repoutils.show_error( error , False )
                os.unlink( localname )
            else :
                if params['mode'] == "update" :
                    return 0 , {}
    
        if not os.path.isfile( localname ) :
    
            repoutils.show_error( "No local Packages file exist for %s-%s. Downloading." % ( self.version , arch ) , True )
    
            url = urllib2.urlparse.urljoin( self.base_url() , "%s%s" % ( self.metadata_path(arch) , item['href'] ) )
    
            if self._retrieve_file( url , localname ) :
                error = repoutils.md5_error( localname , item , item.has_key('size') | repoutils.SKIP_SIZE )
                if error :
                    repoutils.show_error( error )
                    os.unlink( localname )
                    sys.exit(255)
            else :
                repoutils.show_error( "Problems downloading primary file for %s-%s" % ( self.version , arch ) )
                sys.exit(255)
    
        fd = gzip.open( localname )
        packages = filelist_xmlparser.get_package_list( fd )
    
        all_pkgs = {}
        providers = {}

        repoutils.show_error( "Scanning available packages for minor filters" , False )
        for pkginfo in packages :
    
    # FIXME : If any minor filter is used, Packages file must be recreated for the exported repo
    #         Solution : Disable filtering on first approach
    #         In any case, the real problem is actually checksumming, reconstructiog Release and signing
    
            pkginfo['Filename'] = os.path.join( self.metadata_path(arch) , pkginfo['href'] )
            all_pkgs[ pkginfo['name'] ] = pkginfo

            if pkginfo.has_key( 'provides' ) :
                for pkg in pkginfo['provides'] :
                    # There are multiple packages providing the same item, so we need lists
                    if not providers.has_key( pkg ) :
                        providers[ pkg ] = []
                    providers[ pkg ].append( pkginfo['name'] )

        fd.close()

        for pkg_key,pkginfo in all_pkgs.iteritems() :

            if self.match_filters( pkginfo , filters ) :
                continue

            download_pkgs.append( pkginfo )
            # FIXME : This might cause a ValueError exception ??
            download_size += pkginfo['size']
    
            if pkginfo.has_key( 'requires' ) :
                for deppkg in pkginfo[ 'requires' ] :
                    if all_pkgs.has_key( deppkg ) :
                        download_pkgs.append( all_pkgs[ deppkg ] )
                        download_size += int( all_pkgs[deppkg]['size'] )
                    else :
                        # File requirements are not fixed by this loop
                        if providers.has_key( deppkg ) :
                            for _pkg in providers[ deppkg ] :
                                download_pkgs.append( all_pkgs[_pkg] )
                                download_size += int( all_pkgs[_pkg]['size'] )
                        else :
                            missing_pkgs.append ( deppkg )

        repoutils.show_error( "Current download size : %.1f Mb" % ( download_size / 1024 / 1024 ) , False )

        return download_size , download_pkgs , missing_pkgs

class fedora_update_repository ( yum_repository ) :

    def __init__ ( self , config ) :
        yum_repository.__init__( self , config )

    def base_url ( self ) :
        return urllib2.urlparse.urljoin( self.repo_url , "%s/" % self.version )

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
        return urllib2.urlparse.urljoin( self.repo_url , "%s/" % self.version )

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
        return urllib2.urlparse.urljoin( self.repo_url , "distribution/%s/repo/oss/suse/" % self.version )

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
        return urllib2.urlparse.urljoin( self.repo_url , "update/%s/" % self.version )

    def repo_path ( self ) :
        return os.path.join( self.destdir , "update/%s" % self.version )

