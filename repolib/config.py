
import os

import utils , repolib
import ConfigParser


# FIXME : Include standard plain os.open??
mimetypes = {}

try :
    import gzip
    mimetypes['.gz'] = gzip.open
except :
    pass
    
try :
    import bz2
    mimetypes['.bz2'] = bz2.BZ2File
except :
    pass


default_params = {}

# mode (update|init) - decides if we stop processing for unchanged metadata files
default_mode = "update"

# usegpg. To disable verification of PGP signatures, and force the download of master file every run
default_params['usegpg'] = True
try :
    import GnuPGInterface
    default_params['usegpg'] = True
except :
    default_params['usegpg'] = False


# pkgvflags. To specify special flags for verification of downloaded packages
default_params['pkgvflags'] = "SKIP_NONE"


class RepoConf ( dict ) :

    def __init__ ( self , reponame , filename=None ) :
        self.__file__ = filename
        self.__name__ = reponame
        dict.__init__( self )
        self['type'] = None
        self['destdir'] = None
        self['detached'] = None
        self['version'] = None
        self['architectures'] = None
        self['components'] = None

    def read ( self , config ) :

        if self.__name__ not in config.sections() :
            raise Exception( "Repository '%s' is not configured" % self.__name__ )

        if config.has_option( self.__name__ , "destdir" ) :

            self['destdir'] = config.get( self.__name__ , "destdir" )
            self['detached'] = True

        else :

            if "global" not in config.sections() :
                raise Exception( "Broken configuration, missing global section" )

            if not config.has_option( "global", "destdir" ) :
                raise Exception( "Broken configuration, missing destination directory" )

            self['destdir'] = config.get( "global" , "destdir" )
            self['detached'] = False

        self['type'] = config.get( self.__name__ , "type" )

        self['version'] = config.get( self.__name__ , "version" )
        self['architectures'] = config.get( self.__name__ , "architectures" ).split()
        if config.has_option( self.__name__ , "components" ) :
            self['components'] = config.get( self.__name__ , "components" ).split()


class MirrorConf ( RepoConf ) :

    def __init__ ( self , reponame , filename=None ) :
        RepoConf.__init__( self , reponame , filename )
        self['url'] = None
        self.url_parts = None
        self['mode'] = default_mode
        self['filters'] = {}
        self['params'] = {}
        self['params'].update( default_params )

    def set_url ( self , scheme , server , base_path ) :
        self.url_parts = ( scheme , server , base_path )
        self['url'] = utils.unsplit( scheme , server , "%s/" % base_path )

    def read ( self , config ) :
        RepoConf.read( self , config )

        if config.has_option ( self.__name__ , "mode" ) :
            self['mode'] = config.get( self.__name__ , "mode" )

        if config.has_option ( self.__name__ , "url" ) :
            self['url'] = config.get( self.__name__ , "url" )
            if not self['url'].endswith("/") :
                repolib.logger.warning( "Appending trailing '/' to url, missing on configuration file" )
                self['url'] += "/"
        else :
            scheme = config.get( self.__name__ , "scheme" )
            server = config.get( self.__name__ , "server" )
            base_path = config.get( self.__name__ , "base_path" )
            self.set_url( scheme , server , base_path )

        if config.has_option( self.__name__ , "filters" ) :
            for subfilter in config.get( self.__name__ , "filters" ).split() :
                if config.has_option( self.__name__ , subfilter ) :
                    self['filters'][subfilter] = map( lambda x : x.replace("_"," ") , config.get( self.__name__ , subfilter ).split() )

        for key in self['params'].keys() :
            if config.has_option( "global" , key ) :
                try :
                    self['params'][ key ] = config.getboolean( "global" , key )
                except ValueError , ex :
                    self['params'][ key ] = config.get( "global" , key )
            if config.has_option( self.__name__ , key ) :
                try :
                    self['params'][ key ] = config.getboolean( self.__name__ , key )
                except ValueError , ex :
                    self['params'][ key ] = config.get( self.__name__ , key )

        self['params']['pkgvflags'] = eval( "utils.%s" % self['params']['pkgvflags'] )

def read_mirror_config ( repo_name ) :

    config = ConfigParser.RawConfigParser()
    if not config.read( [ "/etc/repomirror.conf" , os.path.expanduser("~/.repomirror") ] ) :
        repolib.logger.error( "Could not find a valid configuration file" )
        return False

    conf = MirrorConf( repo_name )
    try :
        conf.read( config )
    except Exception , ex :
        repolib.logger.error( "Exception while reading mirror configuration : %s" % ex )
        return False

    return conf


def get_all_configs ( key=None , value=None ) :

    config = ConfigParser.RawConfigParser()
    for file in ( "/etc/repomirror.conf" , os.path.expanduser("~/.repomirror") ) :
        config.read( file )
    if not config.sections() :
        repolib.logger.error( "Could not find a valid configuration file" )
        return False

    conflist = []

    for name in config.sections() :
        if name != "global" :
            try :
                conf = MirrorConf( name )
                conf.read( config )
                if not key or conf[key] == value :
                    conflist.append( conf )
            except Exception , ex :
                repolib.logger.error( "Exception while reading configuration : %s" % ex )

    return conflist


class BuildConf ( RepoConf ) :

    def __init__ ( self , reponame , filename=None ) :
        RepoConf.__init__( self , reponame , filename )

    def read ( self , config ) :
        RepoConf.read( self , config )

        if config.has_option( self.__name__ , "extensions" ) :
            self['extensions'] = map ( lambda s : ".%s" % s.lstrip('.') , config.get( self.__name__ , "extensions" ).split() )

def read_build_config ( repo_name ) :

    config = ConfigParser.RawConfigParser()
    if not config.read( [ "/etc/buildrepo.conf" , os.path.expanduser("~/.buildrepo") ] ) :
        repolib.logger.error( "Could not find a valid configuration file" )
        return False

    conf = BuildConf( repo_name )
    try :
        conf.read( config )
    except Exception , ex :
        repolib.logger.error( "Exception while reading build configuration : %s" % ex )
        return False

    return conf

if __name__ == "__main__" :
    print get_all_configs()
    print 
    print get_all_configs( 'type' , 'deb' )

