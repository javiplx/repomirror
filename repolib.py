
import os , sys

import urllib2
import ConfigParser

import repoutils


def read_config ( repo_name ) :

    config = ConfigParser.RawConfigParser()
    if not config.read( [ "/etc/repomirror.conf" , os.path.expanduser("~/.repomirror") , "repomirror.conf" ] ) :
        repoutils.show_error( "Could not find a valid configuration file" )
        sys.exit(255)

    if "global" not in config.sections() :
        repoutils.show_error( "Broken configuration, missing global section" )
        sys.exit(255)

    if not config.has_option( "global", "destdir" ) :
        repoutils.show_error( "Broken configuration, missing destination directory" )
        sys.exit(255)

    if repo_name not in config.sections() :
        repoutils.show_error( "Repository '%s' is not configured" % repo_name )
        sys.exit(255)

    conf = {}
    conf['destdir'] = config.get( "global" , "destdir" )

    conf['type'] = config.get( repo_name , "type" )
    if config.has_option ( repo_name , "url" ) :
        conf['url'] = config.get( repo_name , "url" )
    else :
        conf['scheme'] = config.get( repo_name , "scheme" )
        conf['server'] = config.get( repo_name , "server" )
        conf['base_path'] = config.get( repo_name , "base_path" )
    conf['version'] = config.get( repo_name , "version" )
    conf['architectures'] = config.get( repo_name , "architectures" ).split()
    if config.has_option( repo_name , "components" ) :
        conf['components'] = config.get( repo_name , "components" ).split()

    return conf


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

        if config.has_key( "url" ) :
            self.repo_url = urllib2.urlparse.urljoin( "%s/" % config[ "url" ] , "" )
        else :
            scheme = config[ "scheme" ]
            server = config[ "server" ]
            base_path = config[ "base_path" ]
            self.repo_url = urllib2.urlparse.urlunsplit( ( scheme , server , "%s/" % base_path , None , None ) )

	self.destdir = config[ "destdir" ]
        self.version = config[ "version" ]

        self.architectures = config[ "architectures" ]

class yum_repository ( abstract_repository ) :

    def base_url ( self ) :
        return urllib2.urlparse.urljoin( self.repo_url , "%s/Fedora/" % self.version )

    def repo_path ( self ) :
        return os.path.join( os.path.join( self.destdir , self.version ) , "Fedora" )

    def metadata_path ( self , subrepo ) :
        return "%s/os/" % subrepo

    def get_master_file ( self , params ) :

        repomd_files = {}
        for arch in self.architectures :

            try :
                repomd_files[arch] = repoutils.downloadRawFile( urllib2.urlparse.urljoin( self.base_url() , "%s/repodata/repomd.xml" % self.metadata_path(arch) ) )
            except urllib2.URLError , ex :
                repoutils.show_error( "Exception : %s" % ex )
                for file in repomd_files.values :
                    os.unlink( file )
                return
            except urllib2.HTTPError , ex :
                repoutils.show_error( "Exception : %s" % ex )
                for file in repomd_files.values :
                    os.unlink( file )
                return

            if not repomd_files[arch] :
                repoutils.show_error( "Architecture '%s' is not available for version %s" % ( arch , self.version ) )
                for file in repomd_files.values :
                    os.unlink( file )
                return

        return repomd_files

    def build_local_tree( self ) :

        suite_path = self.repo_path()

        if not os.path.exists( suite_path ) :
            os.makedirs( suite_path )

        for arch in self.architectures :
            packages_path = os.path.join( self.metadata_path(arch) , "repodata" )
            if not os.path.exists( os.path.join( suite_path , packages_path ) ) :
                os.makedirs( os.path.join( suite_path , packages_path ) )

    def get_package_list ( self , arch , local_repodata , params ) :

        download_size = 0
        download_pkgs = {}

        item = False

        repodoc = xml.dom.minidom.parse( os.path.join( local_repodata , "repodata/repomd.xml" ) )
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
            os.unlink( os.path.join( local_repodata , "repodata/repomd.xml" ) )
            sys.exit(255)
    
        del repodoc
    
        # FIXME : On problems, exit or continue next arch ???
    
        localname = os.path.join( local_repodata , item['href'] )
    
        if os.path.isfile( localname ) :
            error = repoutils.md5_error( localname , item , item.has_key('size') )
            if error :
                repoutils.show_error( error , False )
                os.unlink( localname )
            else :
                if params['mode'] == "update" :
                    return 0 , {}
    
        if not os.path.isfile( localname ) :
    
            repoutils.show_error( "No local Packages file exist for %s-%s. Downloading." % ( self.version , arch ) , True )
    
            url = urllib2.urlparse.urljoin( self.base_url() , "%s/%s" % ( self.metadata_path(arch) , item['href'] ) )
    
            if repoutils.downloadRawFile( url , localname ) :
                error = repoutils.md5_error( localname , item , item.has_key('size') )
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
                    'sourcename':urllib2.urlparse.urljoin( self.metadata_path(arch) , href ) ,
                    'destname':os.path.join( self.metadata_path(arch) , href ) ,
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

    def metadata_path ( self , subrepo ) :
        return "%s/" % subrepo

class centos_repository ( yum_repository ) :

    def base_url ( self ) :
        return urllib2.urlparse.urljoin( self.repo_url , "%s/" % self.version )

    def repo_path ( self ) :
        return os.path.join( self.destdir , self.version )

    def metadata_path ( self , subrepo ) :
        return "os/%s/" % subrepo

class centos_update_repository ( centos_repository ) :

    def metadata_path ( self , subrepo ) :
        return "updates/%s/" % subrepo


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

        self.components = config[ "components" ]

    def base_url ( self , subrepo=None ) :
        if subrepo :
            arch , comp = subrepo
            return urllib2.urlparse.urljoin( self.repo_url , self.metadata_path() )
        return self.repo_url

    def repo_path ( self ) :
        return self.destdir

    def metadata_path ( self , subrepo=None ) :
    #def metadata_path ( self , arch=None , comp=None ) :
        if subrepo :
            arch , comp = subrepo
            return "%s/binary-%s/" % ( comp , arch )
        return "dists/%s/" % self.version

    def get_master_file ( self , params ) :

        release_path = os.path.join( self.metadata_path() , "Release" )
        local_release = os.path.join( self.repo_path() , release_path )

        if params['usegpg'] :

            try :
                release_pgp_file = repoutils.downloadRawFile( urllib2.urlparse.urljoin( self.base_url() , "%s.gpg" % release_path ) )
            except urllib2.URLError , ex :
                repoutils.show_error( "Exception : %s" % ex )
                return
            except urllib2.HTTPError , ex :
                repoutils.show_error( "Exception : %s" % ex )
                return

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
            try :
                release_file = repoutils.downloadRawFile( urllib2.urlparse.urljoin( self.base_url() , release_path ) )
            except urllib2.URLError , ex :
                repoutils.show_error( "Exception : %s" % ex )
                return
            except urllib2.HTTPError , ex :
                repoutils.show_error( "Exception : %s" % ex )
                return

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

        # FIXME : Why not check also against release['Codename'] ??
        if release['Suite'].lower() == repo.version.lower() :
            repoutils.show_error( "You have supplied suite '%s'. Please use codename '%s' instead" % ( repo.version, release['Codename'] ) )
            os.unlink( release_file )
            return

        # NOTE : security and volatile repositories prepend a string to the actual component name
        release_comps = map( lambda s : s.rsplit("/").pop() , release['Components'].split() )

        for comp in repo.components :
            if comp not in release_comps :
                repoutils.show_error( "Component '%s' is not available ( %s )" % ( comp , " ".join(release_comps) ) )
                return

        release_archs = release['Architectures'].split()
        for arch in repo.architectures :
            if arch not in release_archs :
                repoutils.show_error( "Architecture '%s' is not available ( %s )" % ( arch , " ".join(release_archs) ) )
                return

        return release_file

    def build_local_tree( self ) :

        suite_path = os.path.join( self.repo_path() , self.metadata_path() )

        if not os.path.exists( suite_path ) :
            os.makedirs( suite_path )

        for comp in self.components :
            if not os.path.exists( os.path.join( suite_path , comp ) ) :
                os.mkdir( os.path.join( suite_path , comp ) )
            for arch in self.architectures :
                subrepo = ( arch , comp )
                packages_path = self.metadata_path( subrepo )
                if not os.path.exists( os.path.join( suite_path , packages_path ) ) :
                    os.mkdir( os.path.join( suite_path , packages_path ) )

        pool_path = os.path.join( self.repo_path() , "pool" )

        if not os.path.exists( pool_path ) :
            os.mkdir( pool_path )

        for comp in self.components :
            pool_com_path = os.path.join( pool_path , comp )
            if not os.path.exists( pool_com_path ) :
                os.mkdir( pool_com_path )

    def get_package_list ( self , subrepo , suite_path , params , release , sections , priorities , tags ) :

        # NOTE : Downloading Release file is quite redundant

        download_size = 0
        download_pkgs = {}

        fd = False
        localname = None

        for ( extension , read_handler ) in extensions.iteritems() :

            _name = "%sPackages%s" % ( self.metadata_path(subrepo) , extension )
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
                    if release[type].has_key( _name ) :
                        _item.update( release[type][_name] )
                if _item :
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

                _name = "%sPackages%s" % ( self.metadata_path(subrepo) , extension )
                localname = os.path.join( suite_path , _name )
                url = urllib2.urlparse.urljoin( self.base_url(subrepo) , _name )

                if repoutils.downloadRawFile( url , localname ) :
                    #
                    # IMPROVEMENT : For Release at least, and _multivalued in general : Multivalued fields returned as dicts instead of lists
                    #
                    # FIXME : 'size' element should be a number !!!
                    #
                    # FIXME : What about other checksums (sha1, sha256)
                    _item = {}
                    for type in ( 'MD5Sum' , 'SHA1' , 'SHA256' ) :
                        if release[type].has_key( _name ) :
                            _item.update( release[type][_name] )
                    if _item :
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

                if sections and pkginfo['Section'] not in sections :
                    continue
                if priorities and pkginfo['Priority'] not in priorities :
                    continue
                if tags and 'Tag' in pkginfo.keys() and pkginfo['Tag'] not in tags :
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


