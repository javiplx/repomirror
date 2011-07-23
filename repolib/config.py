
import os
import glob

import utils , repolib
import ConfigParser


mirrorconf = "/etc/repomirror.conf"
mirrordir  = "/etc/repomirror.d"

buildconf = "/etc/buildrepo.conf"
builddir  = "/etc/buildrepo.d"

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


# NOTE : if a section name is duplicated in the same file, ConfigParser does not allow to detect it
def get_file ( section , conffiles ) :
    filename = []
    for file in conffiles :
        config = ConfigParser.RawConfigParser()
        config.read( file )
        if config.has_section( section ) :
            filename.append( file )
    if not filename :
        raise Exception( "Definition for '%s' not found" % section )
    if len(filename) > 1 :
        raise Exception( "Multiple definitions of '%s' in %s" % ( section , " , ".join(filename) ) )
    return filename[0]


class RepoConf ( dict ) :

    def __init__ ( self , reponame , config , filename ) :
        self.__file__ = filename
        self.name = reponame
        dict.__init__( self )
        self.read( config )

    def read ( self , config ) :

        self['type'] = None
        self['destdir'] = None
        self['detached'] = False
        self['version'] = None
        self['architectures'] = None
        self['components'] = None

        if self.name not in config.sections() :
            raise Exception( "Repository '%s' is not configured" % self.name )

        if config.has_option( self.name , "destdir" ) :

            self['destdir'] = config.get( self.name , "destdir" )
            self['detached'] = True

        else :

            if "global" not in config.sections() :
                raise Exception( "Broken configuration, missing global section" )

            if not config.has_option( "global", "destdir" ) :
                raise Exception( "Broken configuration, missing destination directory" )

            self['destdir'] = config.get( "global" , "destdir" )

        self['type'] = config.get( self.name , "type" )

        self['version'] = config.get( self.name , "version" )
        self['architectures'] = config.get( self.name , "architectures" ).split()
        if config.has_option( self.name , "components" ) :
            self['components'] = config.get( self.name , "components" ).split()


class MirrorConf ( RepoConf ) :

    def set_url ( self , scheme , server , base_path ) :
        self.url_parts = ( scheme , server , base_path )
        self['url'] = utils.unsplit( scheme , server , "%s/" % base_path )

    def read ( self , config ) :

        RepoConf.read( self , config )

        self['url'] = None
        self.url_parts = None
        self['mode'] = default_mode
        self['filters'] = {}
        self['params'] = {}
        self['params'].update( default_params )

        if config.has_option ( self.name , "mode" ) :
            self['mode'] = config.get( self.name , "mode" )

        if config.has_option ( self.name , "url" ) :
            self['url'] = config.get( self.name , "url" )
            if not self['url'].endswith("/") :
                repolib.logger.warning( "Appending trailing '/' to url, missing on configuration file" )
                self['url'] += "/"
        else :
            if config.has_option( self.name , "scheme" ) :
                scheme = config.get( self.name , "scheme" )
            else :
                scheme = "http"
            server = config.get( self.name , "server" )
            if config.has_option( self.name , "base_path" ) :
                base_path = config.get( self.name , "base_path" )
            else :
                base_path = ""
            self.set_url( scheme , server , base_path )

        if config.has_option( self.name , "filters" ) :
            for subfilter in config.get( self.name , "filters" ).split() :
                if config.has_option( self.name , subfilter ) :
                    self['filters'][subfilter] = map( lambda x : x.replace("_"," ") , config.get( self.name , subfilter ).split() )

        for key in self['params'].keys() :
            if config.has_option( "global" , key ) :
                try :
                    self['params'][ key ] = config.getboolean( "global" , key )
                except ValueError , ex :
                    self['params'][ key ] = config.get( "global" , key )
            if config.has_option( self.name , key ) :
                try :
                    self['params'][ key ] = config.getboolean( self.name , key )
                except ValueError , ex :
                    self['params'][ key ] = config.get( self.name , key )

        self['params']['pkgvflags'] = eval( "utils.%s" % self['params']['pkgvflags'] )

def read_mirror_config ( repo_name ) :

    conffiles = [ mirrorconf ]
    conffiles.extend( glob.glob( os.path.join( mirrordir , "*" ) ) )

    config = ConfigParser.RawConfigParser()
    if not config.read( conffiles ) :
        raise Exception( "Could not find a valid configuration file" )

    return MirrorConf( repo_name , config , get_file( repo_name , conffiles ) )


def get_all_configs ( key=None , value=None ) :

    conffiles = [ mirrorconf ]
    conffiles.extend( glob.glob( os.path.join( mirrordir , "*" ) ) )

    config = ConfigParser.RawConfigParser()
    if not config.read( conffiles ) :
        raise Exception( "Could not find a valid configuration file" )

    conflist = []

    for name in config.sections() :
        if name != "global" :
            try :
                conf = MirrorConf( name , config , get_file( name , conffiles ) )
                if not key or conf[key] == value :
                    conflist.append( conf )
            except Exception , ex :
                repolib.logger.error( ex )

    return conflist


class BuildConf ( RepoConf ) :

    def read ( self , config ) :
        RepoConf.read( self , config )

        if config.has_option( self.name , "extensions" ) :
            self['extensions'] = map ( lambda s : ".%s" % s.lstrip('.') , config.get( self.name , "extensions" ).split() )

def read_build_config ( repo_name ) :

    conffiles = [ buildconf ]
    conffiles.extend( glob.glob( os.path.join( builddir , "*" ) ) )

    config = ConfigParser.RawConfigParser()
    if not config.read( conffiles ) :
        raise Exception( "Could not find a valid configuration file" )

    return BuildConf( repo_name , config , get_file( repo_name , conffiles ) )

if __name__ == "__main__" :
    print get_all_configs()
    print 
    print get_all_configs( 'type' , 'deb' )

