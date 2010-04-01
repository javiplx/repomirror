
import os , sys

import urllib2
import ConfigParser


def read_config ( repo_name ) :

    config = ConfigParser.RawConfigParser()
    if not config.read( [ "/etc/repomirror.conf" , os.path.expanduser("~/.repomirror") , "repomirror.conf" ] ) :
        show_error( "Could not find a valid configuration file" )
        sys.exit(255)

    if "global" not in config.sections() :
        show_error( "Broken configuration, missing global section" )
        sys.exit(255)

    if not config.has_option( "global", "destdir" ) :
        show_error( "Broken configuration, missing destination directory" )
        sys.exit(255)

    if repo_name not in config.sections() :
        show_error( "Repository '%s' is not configured" % repo_name )
        sys.exit(255)

    conf = {}
    conf['destdir'] = config.get( "global" , "destdir" )

    conf['type'] = config.get( repo_name , "type" )
    conf['scheme'] = config.get( repo_name , "scheme" )
    conf['server'] = config.get( repo_name , "server" )
    conf['base_path'] = config.get( repo_name , "base_path" )
    conf['version'] = config.get( repo_name , "version" )
    conf['architectures'] = config.get( repo_name , "architectures" ).split()
    if config.has_option( repo_name , "components" ) :
        conf['components'] = config.get( repo_name , "components" ).split()

    return conf


def instantiate_repo ( type , repo_url , version ) :
    repo = None
    if type == "yum" :
        repo = yum_repository( repo_url , version )
    elif type == "yum_upd" :
        repo = fedora_update_repository( repo_url , version )
    elif type == "deb" :
        repo = debian_repository( repo_url , version )
    else :
        show_error( "Unknown repository type '%s'" % type )
    return repo

import gzip
import xml.dom.minidom

class yum_repository :

    def __init__ ( self , url , version ) :
        self.repo_url = url
        self.version = version

    def base_url ( self ) :
        return urllib2.urlparse.urljoin( self.repo_url , "%s/Fedora/" % self.version )

    def repo_path ( self , destdir ) :
        return os.path.join( os.path.join( destdir , self.version ) , "Fedora" )

    def metadata_path ( self , arch ) :
        return "%s/os/" % arch

    def get_package_list ( self , arch , local_repodata , md5_error , repostate , force , downloadRawFile ) :

        download_size = 0
        download_pkgs = {}

        item = False

        repodoc = xml.dom.minidom.parse( os.path.join( local_repodata , "repodata/repomd.xml" ) )
        doc = repodoc.documentElement
        for node in doc.getElementsByTagName( "data" ) :
            if node.getAttribute( "type" ) == "primary" :
                location = node.getElementsByTagName( "location" )
                if not location :
                    show_error( "No location element within repomd file" )
                    continue
                # FIXME : Produce an error if multiple locations ?
                size = node.getElementsByTagName( "size" )
                item = { 'href':location[0].getAttribute( "href" ) , 'size':int(size[0].firstChild.nodeValue) }
                for _node in node.getElementsByTagName( "checksum" ) :
                    item[ _node.getAttribute( "type" ) ] = _node.firstChild.nodeValue
                break
        else :
            show_error( "No primary node within repomd file" )
            os.unlink( os.path.join( local_repodata , "repodata/repomd.xml" ) )
            sys.exit(255)
    
        del repodoc
    
        # FIXME : On problems, exit or continue next arch ???
    
        localname = os.path.join( local_repodata , item['href'] )
    
        if os.path.isfile( localname ) :
            error = md5_error( localname , item )
            if error :
                show_error( error , False )
                os.unlink( localname )
            else :
                if repostate == "synced" and not force :
                    return 0 , {}
    
        if not os.path.isfile( localname ) :
    
            show_error( "No local Packages file exist for %s-%s. Downloading." % ( self.version , arch ) , True )
    
            url = urllib2.urlparse.urljoin( self.base_url() , "%s/%s" % ( self.metadata_path(arch) , item['href'] ) )
    
            if downloadRawFile( url , localname ) :
                error = md5_error( localname , item )
                if error :
                    show_error( error )
                    os.unlink( localname )
                    sys.exit(255)
            else :
                show_error( "Problems downloading primary file for %s-%s" % ( self.version , arch ) )
                sys.exit(255)
    
        fd = gzip.open( localname )
        packages = xml.dom.minidom.parse( fd )
        # FIXME : What about gettint doc root and so ...
    
        print "Scanning available packages for minor filters (not implemented yet !!!)"
        # Most relevant for minor filter is   <format><rpm:group>...</rpm:group>
    
        for pkginfo in packages.getElementsByTagName( "package" ) :
    
            # FIXME : A XML -> Dict class is quite helpful here !!
    
    # FIXME : If any minor filter is used, Packages file must be recreated for the exported repo
    #         Solution : Disable filtering on first approach
    #         In any case, the real problem is actually checksumming, reconstructiog Release and signing
    
            name = pkginfo.getElementsByTagName('name')[0].firstChild.nodeValue
            _arch = pkginfo.getElementsByTagName('arch')[0].firstChild.nodeValue
            pkg_key = "%s-%s" % ( name , _arch )
            if pkg_key in download_pkgs.keys() :
                if _arch != "noarch" :
                    show_error( "Package '%s - %s' is duplicated in repositories" % ( name , _arch ) , False )
            else :
                href = pkginfo.getElementsByTagName('location')[0].getAttribute( "href" )
                pkgdict = {
                    'sourcename':urllib2.urlparse.urljoin( self.metadata_path(arch) , href ) ,
                    'destname':os.path.join( self.metadata_path(arch) , href ) ,
                    'size':pkginfo.getElementsByTagName('size')[0].getAttribute( "package" )
                    }
                download_pkgs[ pkg_key ] = pkgdict
                # FIXME : This might cause a ValueError exception ??
                download_size += int( pkgdict['size'] )
    
            pkginfo.unlink()
            del pkginfo
    
        del packages
    
        print "Current download size : %.1f Mb" % ( download_size / 1024 / 1024 )
        fd.close()

        return download_size , download_pkgs

class fedora_update_repository ( yum_repository ) :

    def __init__ ( self , url , version ) :
        yum_repository.__init__( self , url , version )

    def base_url ( self ) :
        return urllib2.urlparse.urljoin( self.repo_url , "%s/" % self.version )

    def repo_path ( self , destdir ) :
        return os.path.join( destdir , self.version )

    def metadata_path ( self , arch ) :
        return "%s/" % arch

class debian_repository :

    def __init__ ( self , url , version ) :
        self.repo_url = url
        self.version = version

    def base_url ( self , arch=None , comp=None ) :
        if arch and comp :
            return urllib2.urlparse.urljoin( self.repo_url , self.metadata_path() )
        return self.repo_url

    def repo_path ( self , destdir ) :
        return destdir

    def metadata_path ( self , arch=None , comp=None ) :
        if arch and comp :
            return "%s/binary-%s/" % ( comp , arch )
        return "dists/%s/" % self.version


def show_error( str , error=True ) :
    if error :
        print "ERROR : %s" % str
    else :
        print "WARNING : %s" % str


