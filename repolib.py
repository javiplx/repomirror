
import os , sys
import errno , shutil

import urllib2

import repoutils


def instantiate_repo ( config ) :
    repo = None
    if config['type'] == "yum" :
        repo = yum_repository( config )
    elif config['type'] == "centos" :
        repo = centos_repository( config )
    elif config['type'] == "yum_upd" :
        repo = fedora_update_repository( config )
    elif config['type'] == "centos_upd" :
        repo = centos_update_repository( config )
    elif config['type'] == "deb" :
        repo = debian_repository( config )
    else :
        repoutils.show_error( "Unknown repository type '%s'" % config['type'] )
    return repo

import gzip
import xml.dom.minidom
import filelist_xmlparser

class abstract_repository :

    def __init__ ( self , config ) :

        self.repo_url = urllib2.urlparse.urljoin( "%s/" % config[ "url" ] , "" )

	self.destdir = config[ "destdir" ]
        self.version = config[ "version" ]

        self.architectures = config[ "architectures" ]

        if not os.path.isdir( self.destdir ) :
            raise Exception( "Destination directory %s does not exists" % self.destdir )

    def build_local_tree( self ) :

        suite_path = self.repo_path()

        for subrepo in self.get_subrepos() :
            packages_path = self.metadata_path( subrepo , False )
            if not os.path.exists( os.path.join( suite_path , packages_path ) ) :
                os.makedirs( os.path.join( suite_path , packages_path ) )

    def _retrieve_file ( self , location , localname=None ) :

        try :
            filename  = repoutils.downloadRawFile( location , localname )
        except urllib2.URLError , ex :
            repoutils.show_error( "Exception : %s" % ex )
            return
        except urllib2.HTTPError , ex :
            repoutils.show_error( "Exception : %s" % ex )
            return

        return filename


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

    def get_master_file ( self , params ) :

        repomd_files = {}
        for arch in self.architectures :

            repomd_files[arch] = self._retrieve_file( urllib2.urlparse.urljoin( self.base_url() , "%srepomd.xml" % self.metadata_path(arch,False) ) )

            if not repomd_files[arch] :
                repoutils.show_error( "Architecture '%s' is not available for version %s" % ( arch , self.version ) )
                for file in repomd_files.values :
                    os.unlink( file )
                return

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

    def get_package_list ( self , arch , local_repodata , params , minor_filters ) :

        download_size = 0
        download_pkgs = {}

        item = False

        repodoc = xml.dom.minidom.parse( os.path.join( local_repodata[arch] , "repodata/repomd.xml" ) )
        doc = repodoc.documentElement
        for node in doc.getElementsByTagName( "data" ) :
            if node.getAttribute( "type" ) == "primary" :
                location = node.getElementsByTagName( "location" )
                if not location :
                    repoutils.show_error( "No location element within repomd file" )
                    continue
                item = { 'href':location[0].getAttribute( "href" ) }
                # FIXME : Produce an error if multiple locations ?
                size = node.getElementsByTagName( "size" )
                if size :
                    item['size'] = int(size[0].firstChild.nodeValue)
                for _node in node.getElementsByTagName( "checksum" ) :
                    item[ _node.getAttribute( "type" ) ] = _node.firstChild.nodeValue
                break
        else :
            repoutils.show_error( "No primary node within repomd file" )
            os.unlink( os.path.join( local_repodata[arch] , "repodata/repomd.xml" ) )
            sys.exit(255)
    
        del repodoc
    
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
    
        repoutils.show_error( "Scanning available packages for minor filters (not implemented yet !!!)" , False )
        # Most relevant for minor filter is   <format><rpm:group>...</rpm:group>
    
        for pkginfo in packages :
    
    # FIXME : If any minor filter is used, Packages file must be recreated for the exported repo
    #         Solution : Disable filtering on first approach
    #         In any case, the real problem is actually checksumming, reconstructiog Release and signing
    
            name = pkginfo['name']
            _arch = pkginfo['arch']
            pkg_key = "%s-%s" % ( name , _arch )
            if pkg_key in download_pkgs.keys() :
                if _arch != "noarch" :
                    repoutils.show_error( "Package '%s - %s' is duplicated in repositories" % ( name , _arch ) , False )
            else :
                href = pkginfo['href']
                pkgdict = {
                    'Filename':os.path.join( self.metadata_path(arch) , href ) ,
                    'size':pkginfo['size']
                    }
                download_pkgs[ pkg_key ] = pkgdict
                # FIXME : This might cause a ValueError exception ??
                download_size += pkgdict['size']
    
        repoutils.show_error( "Current download size : %.1f Mb" % ( download_size / 1024 / 1024 ) , False )
        fd.close()

        return download_size , download_pkgs

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
            return "%s/" % subrepo
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
            return "os/%s/" % subrepo
        if not partial :
            path += "repodata/"
        return path

class centos_update_repository ( centos_repository ) :

    def metadata_path ( self , subrepo=None , partial=True ) :
        path = ""
        if subrepo :
            return "updates/%s/" % subrepo
        if not partial :
            path += "repodata/"
        return path


import debian_bundle.deb822 , debian_bundle.debian_support

# FIXME : Include standard plain os.open??
extensions = {}

try :
    import gzip
    extensions['.gz'] = gzip.open
except :
    pass
    
try :
    import bz2
    extensions['.bz2'] = bz2.BZ2File
except :
    pass


class debian_repository ( abstract_repository ) :

    def __init__ ( self , config ) :
        abstract_repository.__init__( self , config )

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

    def get_master_file ( self , params ) :

        local_release = os.path.join( self.repo_path() , self.release )

        if params['usegpg'] :

            release_pgp_file = self._retrieve_file( urllib2.urlparse.urljoin( self.base_url() , "%s.gpg" % self.release ) )

            if not release_pgp_file :
                repoutils.show_error( "Release.gpg file for suite '%s' is not found." % ( self.version ) )
                return

            if os.path.isfile( local_release ) :
                errstr = repoutils.gpg_error( release_pgp_file , local_release )
                if errstr :
                    repoutils.show_error( errstr , False )
                    os.unlink( local_release )
                else :
                    # FIXME : If we consider that our mirror is complete, it is safe to exit here
                    if params['mode'] == "update" :
                        repoutils.show_error( "Release file unchanged, exiting" , False )
                        return
                    os.unlink( release_pgp_file )

        else :
            if os.path.isfile( local_release ) :
                os.unlink( local_release )

        if not os.path.isfile( local_release ) :

            release_file = self._retrieve_file( urllib2.urlparse.urljoin( self.base_url() , self.release ) )

            if not release_file :
                repoutils.show_error( "Release file for suite '%s' is not found." % ( self.version ) )
                if params['usegpg'] :
                    os.unlink( release_pgp_file )
                sys.exit(255)

            if params['usegpg'] :
                errstr = repoutils.gpg_error( release_pgp_file , release_file )
                os.unlink( release_pgp_file )
                if errstr :
                    repoutils.show_error( errstr )
                    os.unlink( release_file )
                    return

            release = debian_bundle.deb822.Release( sequence=open( release_file ) )

        else :

            release = debian_bundle.deb822.Release( sequence=open( local_release ) )

        if release['Suite'] !=  release['Codename'] :
            if release['Suite'].lower() == self.version.lower() :
                repoutils.show_error( "You have supplied suite '%s'. Please use codename '%s' instead" % ( self.version, release['Codename'] ) )
                os.unlink( release_file )
                return

        if release['Codename'].lower() != self.version.lower() :
            repoutils.show_error( "Requested version '%s' does not match with codename from Release file ('%s')" % ( self.version, release['Codename'] ) )
            os.unlink( release_file )
            return

        if release.has_key( "Components" ) :
            # NOTE : security and volatile repositories prepend a string to the actual component name
            release_comps = map( lambda s : s.rsplit("/").pop() , release['Components'].split() )

            if self.components :
                for comp in self.components :
                    if comp not in release_comps :
                        repoutils.show_error( "Component '%s' is not available ( %s )" % ( comp , " ".join(release_comps) ) )
                        return
            else :
                repoutils.show_error( "No components specified, selected all components from Release file" , False )
                self.components = release_comps

        elif self.components :
            repoutils.show_error( "There is no components entry in Release file for suite '%s', please fix your configuration" % self.version )
            return
        else :
            # FIXME : This policy is taken from scratchbox repository, with no explicit component and files located right under dists along Packages file
            repoutils.show_error( "Va que no, ni haskey, ni components" , False )
            self.components = ( "main" ,)

        release_archs = release['Architectures'].split()
        for arch in self.architectures :
            if arch not in release_archs :
                repoutils.show_error( "Architecture '%s' is not available ( %s )" % ( arch , " ".join(release_archs) ) )
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

    def get_package_list ( self , subrepo , suite_path , params , minor_filters ) :

        release = debian_bundle.deb822.Release( sequence=open( os.path.join( self.repo_path() , self.release ) ) )

        # NOTE : Downloading Package Release file is quite redundant

        download_size = 0
        download_pkgs = {}

        fd = False
        localname = None

        for ( extension , read_handler ) in extensions.iteritems() :

            _name = "%sPackages%s" % ( self.metadata_path(subrepo,True) , extension )
            localname = os.path.join( suite_path , _name )

            if os.path.isfile( localname ) :
                #
                # IMPROVEMENT : For Release at least, and _multivalued in general : Multivalued fields returned as dicts instead of lists
                #
                # FIXME : 'size' element should be a number !!!
                #
                # FIXME : What about other checksums (sha1, sha256)
                _item = {}
                for type in ( 'MD5Sum' , 'SHA1' , 'SHA256' ) :
                    if release.has_key(type) :
                        for item in release[type] :
                            if item['name'] == _name :
                                _item.update( item )
                if _item :
                    if params['usemd5'] :
                        error = repoutils.md5_error( localname , _item )
                        if error :
                            repoutils.show_error( error , False )
                            os.unlink( localname )
                            continue

                    # NOTE : force and unsync should behave different here? We could just force download if forced
                    if params['mode'] == "update" :
                        repoutils.show_error( "Local copy of '%s' is up-to-date, skipping." % _name , False )
                    else :
                        fd = read_handler( localname )

                    break

                else :
                    repoutils.show_error( "Checksum for file '%s' not found, go to next format." % _name , True )
                    continue

        else :

            repoutils.show_error( "No local Packages file exist for %s / %s. Downloading." % subrepo , True )

            for ( extension , read_handler ) in extensions.iteritems() :

                _name = "%sPackages%s" % ( self.metadata_path(subrepo,True) , extension )
                localname = os.path.join( suite_path , _name )
                url = urllib2.urlparse.urljoin( urllib2.urlparse.urljoin( self.base_url() , self.metadata_path() ) , _name )

                if self._retrieve_file( url , localname ) :
                    #
                    # IMPROVEMENT : For Release at least, and _multivalued in general : Multivalued fields returned as dicts instead of lists
                    #
                    # FIXME : 'size' element should be a number !!!
                    #
                    # FIXME : What about other checksums (sha1, sha256)
                    _item = {}
                    for type in ( 'MD5Sum' , 'SHA1' , 'SHA256' ) :
                        if release.has_key(type) :
                            for item in release[type] :
                                if item['name'] == _name :
                                    _item.update( item )
                    if _item :
                        if params['usemd5'] :
                            error = repoutils.md5_error( localname , _item )
                            if error :
                                repoutils.show_error( error , False )
                                os.unlink( localname )
                                continue

                        break

                    else :
                        repoutils.show_error( "Checksum for file '%s' not found, exiting." % _name ) 
                        continue

            else :
                repoutils.show_error( "No Valid Packages file found for %s / %s" % subrepo )
                sys.exit(0)

            fd = read_handler( localname )

        if fd :
            packages = debian_bundle.debian_support.PackageFile( localname , fd )

# FIXME : If any minor filter is used, Packages file must be recreated for the exported repo
#         Solution : Disable filtering on first approach
#         In any case, the real problem is actually checksumming, reconstructiog Release and signing

            repoutils.show_error( "Scanning available packages for minor filters" , False )
            for pkg in packages :
                pkginfo = debian_bundle.deb822.Deb822Dict( pkg )

                # NOTE : Is this actually a good idea ?? It simplifies, but I would like to mirror main/games but not contrib/games, for example
                # SOLUTION : Create a second and separate Category with the last part (filename) of Section
                # For now, we kept the simplest way
                if pkginfo['Section'].find( "%s/" % subrepo[1] ) == 0 :
                    pkginfo['Section'] = pkginfo['Section'][pkginfo['Section'].find("/")+1:]

                if minor_filters['sections'] and pkginfo['Section'] not in minor_filters['sections'] :
                    continue
                if minor_filters['priorities'] and pkginfo['Priority'] not in minor_filters['priorities'] :
                    continue
                if minor_filters['tags'] and 'Tag' in pkginfo.keys() and pkginfo['Tag'] not in minor_filters['tags'] :
                    continue

                pkg_key = "%s-%s" % ( pkginfo['Package'] , pkginfo['Architecture'] )
                if pkg_key in download_pkgs.keys() :
                    if pkginfo['Architecture'] != "all" :
                        repoutils.show_error( "Package '%s - %s' is duplicated in repositories" % ( pkginfo['Package'] , pkginfo['Architecture'] ) , False )
                else :
                    download_pkgs[ pkg_key ] = pkginfo
                    # FIXME : This might cause a ValueError exception ??
                    download_size += int( pkginfo['Size'] )

            repoutils.show_error( "Current download size : %.1f Mb" % ( download_size / 1024 / 1024 ) , False )
            fd.close()
        return download_size , download_pkgs


