
import filelist_xmlparser

import utils , repoutils

import errno , shutil
import gzip

import os , sys
import tempfile

from repolib import abstract_repository , urljoin , logger


class PackageList :

    out_template = """name=%s
sha256=%s
size=%s
href=%s
Filename=%s

"""

    def __init__ ( self , repo=None ) :
        """Input uses a list interface, and output a sequence interface taken from original PackageFile"""
        self.repo = repo
        if self.repo :
            self.download = repoutils.DownloadThread( repo )
        self.pkgfd = tempfile.NamedTemporaryFile()

    def rewind ( self ) :
        if self.pkgfd :
            self.pkgfd.seek(0)

    def __iter__ ( self ) :
        _pkg = {}
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

    def append ( self , pkg ) :
        if not pkg.has_key('sha256') : print type(pkg),":",pkg
        if self.repo :
            self.download.append( pkg )
            self.download.start()
        self.pkgfd.write( self.out_template % ( pkg['name'] , pkg['sha256'] , pkg['size'] , pkg['href'] , pkg['Filename'] ) )

    def extend ( self , values_list ) :
        self.pkgfd.seek(0,2)
        for pkg in values_list :
            self.append( pkg )

    def flush ( self ) :
        if self.repo :
            self.download.destroy()
        pass

# NOTE : The xml version seems more attractive, but we cannot use it until
#        we get a way to build an iterable XML parser, maybe availeble
#        using xml.etree.ElementTree.iterparse
class XMLPackageList ( PackageList ) :

    out_template = """<package type="rpm">
  <name>%s</name>
  <checksum type="sha256" pkgid="YES">%s</checksum>
  <size package="%s"/>
  <location href="%s"/>
  <poolfile href="%s"/>
</package>
"""

    def __init__ ( self , repo=None ) :
        """Input uses a list interface, and output a sequence interface taken from original PackageFile"""
        PackageList.__init__( self , repo )
        self.pkgfd.write( '<?xml version="1.0" encoding="UTF-8"?>\n' )
        self.pkgfd.write( '<metadata xmlns="http://linux.duke.edu/metadata/common" xmlns:rpm="http://linux.duke.edu/metadata/rpm">\n' )

    def __iter__ ( self ) :
        raise Exception( "Iterable parser not yet implemented" )

    def flush ( self ) :
        self.pkgfd.write( '</metadata>\n' )


class yum_repository ( abstract_repository ) :

    def base_url ( self ) :
        return urljoin( self.repo_url , "%s/Fedora/" % self.version )

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
                logger.error( "Architecture '%s' is not available for version %s" % ( arch , self.version ) )
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
            return False
        return True

    def get_package_list ( self , arch , local_repodata , _params , filters ) :

        params = self.params
        params.update( _params )

        download_size = 0
        download_pkgs = PackageList()
        rejected_pkgs = PackageList()
        missing_pkgs = []

        item , filelist = filelist_xmlparser.get_filelist( os.path.join( local_repodata[arch] , "repodata/repomd.xml" ) )

        if not item :
            logger.error( "No primary node within repomd file" )
            os.unlink( os.path.join( local_repodata[arch] , "repodata/repomd.xml" ) )
            sys.exit(255)
    
        # FIXME : On problems, exit or continue next arch ???
    
        localname = os.path.join( local_repodata[arch] , item['href'] )
    
        if os.path.isfile( localname ) :
            error = utils.md5_error( localname , item , item.has_key('size') | utils.SKIP_SIZE )
            if error :
                logger.warning( error )
                os.unlink( localname )
            else :
                if params['mode'] == "update" :
                    return 0 , [] , []
    
        if not os.path.isfile( localname ) :
    
            logger.warning( "No local primary file exist for %s-%s. Downloading." % ( self.version , arch ) )
    
            url = urljoin( self.base_url() , "%s%s" % ( self.metadata_path(arch) , item['href'] ) )
    
            if self._retrieve_file( url , localname ) :
                error = utils.md5_error( localname , item , item.has_key('size') | utils.SKIP_SIZE )
                if error :
                    logger.error( error )
                    os.unlink( localname )
                    sys.exit(255)
            else :
                logger.error( "Problems downloading primary file for %s-%s" % ( self.version , arch ) )
                sys.exit(255)
    
        fd = gzip.open( localname )
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
            pkginfo['Filename'] = os.path.join( self.metadata_path(arch) , pkginfo['href'] )
            download_pkgs.append( pkginfo )
            # FIXME : This might cause a ValueError exception ??
            download_size += pkginfo['size']

            if pkginfo.has_key( 'requires' ) :
                for pkg in pkginfo['requires'] :
                    providers[ pkg ] = 1

        if not filelist :
            logger.error( "No filelists node within repomd file" )
            os.unlink( os.path.join( local_repodata[arch] , "repodata/repomd.xml" ) )
            sys.exit(255)
    
        # FIXME : On problems, exit or continue next arch ???
    
        localname = os.path.join( local_repodata[arch] , filelist['href'] )
    
        if os.path.isfile( localname ) :
            error = utils.md5_error( localname , filelist , filelist.has_key('size') | utils.SKIP_SIZE )
            if error :
                logger.warning( error )
                os.unlink( localname )
            else :
                if params['mode'] == "update" :
                    return 0 , [] , []
    
        if not os.path.isfile( localname ) :
    
            logger.warning( "No local filelists file exist for %s-%s. Downloading." % ( self.version , arch ) )
    
            url = urljoin( self.base_url() , "%s%s" % ( self.metadata_path(arch) , filelist['href'] ) )
    
            if self._retrieve_file( url , localname ) :
                error = utils.md5_error( localname , filelist , filelist.has_key('size') | utils.SKIP_SIZE )
                if error :
                    logger.error( error )
                    os.unlink( localname )
                    sys.exit(255)
            else :
                logger.error( "Problems downloading primary file for %s-%s" % ( self.version , arch ) )
                sys.exit(255)
    
        filesfd = gzip.open( localname )

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
        
        # Rewind list
        rejected_pkgs.rewind()

        logger.warning( "Searching for missing dependencies" )
        for pkginfo in rejected_pkgs :
        
            # NOTE : There are some cases of packages requiring themselves, so we cannot jump to next
            #if all_pkgs.has_key( pkginfo['name'] ) :
            #    continue

            if providers.has_key( pkginfo['name'] ) :
                all_pkgs[ pkginfo['name'] ] = 1
                pkginfo['Filename'] = os.path.join( self.metadata_path(arch) , pkginfo['href'] )
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
                        pkginfo['Filename'] = os.path.join( self.metadata_path(arch) , pkginfo['href'] )
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

        download_pkgs.flush()

        for pkgname in providers.keys() :
            if not all_pkgs.has_key( pkgname ) :
                missing_pkgs.append( pkgname )

        logger.warnig( "Current download size : %.1f Mb" % ( download_size / 1024 / 1024 ) )

        download_pkgs.rewind()
        return download_size , download_pkgs , missing_pkgs

    def get_download_list( self ) :
        return PackageList( self )

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

