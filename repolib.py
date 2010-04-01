
import os , sys

import urllib2
import ConfigParser


def read_config ( repo_name ) :

    config = ConfigParser.RawConfigParser()
    if not config.read( [ "/etc/repomirror.conf" , os.path.expanduser("~/.repomirror") ] ) :
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
    else :
        show_error( "Unknown repository type '%s'" % type )
    return repo

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

class fedora_update_repository ( yum_repository ) :

    def __init__ ( self , url , version ) :
        yum_repository.__init__( self , url , version )

    def base_url ( self ) :
        return urllib2.urlparse.urljoin( self.repo_url , "%s/" % self.version )

    def repo_path ( self , destdir ) :
        return os.path.join( destdir , self.version )

    def metadata_path ( self , arch ) :
        return "%s/" % arch


def show_error( str , error=True ) :
    if error :
        print "ERROR : %s" % str
    else :
        print "WARNING : %s" % str


