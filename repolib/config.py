
import os , pwd
import getpass
import glob

import repolib

import ConfigParser


# Names of main configuration files and configuration subdirectories

mirrorconf = "/etc/repomirror.conf"
mirrordir  = "/etc/repomirror.d"

buildconf = "/etc/buildrepo.conf"
builddir  = "/etc/buildrepo.d"



# mimetypes dictionary includes extension and open handlers for available
#   metadata file formats. Only meaningful for debian & feed repositories.

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



# Values stored on default_params dictionary decides the verifications to be
#   done on metadata files after downloading. All knwon parameters are
#   included here, despite of the type of object they affect. Hardcoded values
#   are overriden by definitions at global section, and later modified by
#   settings within the repository definition.
# Currently known parameters are:
#   usegpg (MirrorRepository, boolean) - enable verification of PGP signatures
#   pkgvflags (MirrorComponent) - verifications to be skipped. Must be a
#     combination of SKIP_* names defined at utils.py. Only used on yum type.

default_params = {}

default_params['usegpg'] = repolib.with_gpg

default_params['pkgvflags'] = "SKIP_NONE"



# Webserver related values. Default values are for stock debian systems
web = { 'uid':33 , 'gid':33 , 'uri':"/mirror" , 'conf':"/etc/apache2" }


# NOTE : if a section name is duplicated in the same file,
#   ConfigParser does not allow to detect it
def get_file ( section , conffiles ) :
    filename = []
    for file in conffiles :
        config = ConfigParser.RawConfigParser()
        config.read( file )
        if config.has_section( section ) :
            filename.append( file )
    if not filename :
        raise Exception( "Definition not found" )
    if len(filename) > 1 :
        raise Exception( "Multiple definitions of '%s' in %s" % ( section , " , ".join(filename) ) )
    return filename[0]


def write_build ( reponame , values , filter=None ) :
    filename = os.path.join( builddir , reponame + ".conf" )
    if os.path.exists( filename ) :
        raise Exception( "Configuration file %s already exists" % filename )
    cfg = ConfigParser.RawConfigParser()
    cfg.add_section( reponame )
    for k,v in values.iteritems() :
        if filter and key in filter :
            continue
        cfg.set( reponame , k , v )
    fd = open( filename , "w" )
    cfg.write(fd)
    fd.close()


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

        if config.has_option( self.name , "architectures" ) :
            self['architectures'] = config.get( self.name , "architectures" ).split()
        if config.has_option( self.name , "components" ) :
            self['components'] = config.get( self.name , "components" ).split()

        if config.has_option( self.name , "usegpg" ) :
            self['usegpg'] = config.get( self.name , "usegpg" )
        else :
            self['usegpg'] = False

class MirrorConf ( RepoConf ) :

    def set_url ( self , scheme , server , base_path ) :
        self.url_parts = ( scheme , server , base_path )
        self['url'] = repolib.unsplit( scheme , server , "%s/" % base_path )

    def read ( self , config ) :

        RepoConf.read( self , config )

        self['url'] = None
        self.url_parts = None
        self['class'] = "standard"
        self['subdir'] = False
        self['filters'] = {}
        self['params'] = {}
        self['params'].update( default_params )

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
            if config.has_option( self.name , "server" ) :
                server = config.get( self.name , "server" )
                if config.has_option( self.name , "base_path" ) :
                    base_path = config.get( self.name , "base_path" )
                else :
                    base_path = ""
                self.set_url( scheme , server , base_path )
        if not self['url'] :
            raise Exception( "Broken configuration, no source url given" )

        if config.has_option( self.name , "class" ) :
            self['class'] = config.get( self.name , "class" )

        if config.has_option( self.name , "components" ) :
            if not self['type'] == "apt" :
                repolib.logger.warning( "Specifying components for a non-debian repository" )
            self['components'] = config.get( self.name , "components" ).split()

        if config.has_option( self.name , "subdir" ) :
            self['subdir'] = config.get( self.name , "subdir" )

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

        self['params']['pkgvflags'] = eval( "repolib.%s" % self['params']['pkgvflags'] )

        if config.has_section( "global" ) :
            if config.has_option( "global" , "webuser" ) :
                webuser = config.get( "global" , "webuser" )
                web['uid'] , web['gid'] = pwd.getpwnam( webuser )[2:4]
            if config.has_option( "global" , "weburi" ) :
                web['uri'] = config.get( "global" , "weburi" )
            if config.has_option( "global" , "webconf" ) :
                web['conf'] = config.get( "global" , "webconf" )

def read_mirror_config ( repo_name ) :

    conffiles = [ mirrorconf ]
    conffiles.extend( glob.glob( os.path.join( mirrordir , "*.conf" ) ) )

    config = ConfigParser.RawConfigParser()
    if not config.read( conffiles ) :
        raise Exception( "Could not find a valid configuration file" )

    return MirrorConf( repo_name , config , get_file( repo_name , conffiles ) )


def get_all_mirror_configs ( key=None , value=None ) :

    conffiles = [ mirrorconf ]
    conffiles.extend( glob.glob( os.path.join( mirrordir , "*.conf" ) ) )

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

    def read ( self , config ) :

        RepoConf.read( self , config )

        self['source'] = None
        self['force'] = False

        if config.has_option( self.name , "force" ) :
            self['force'] = True

        if config.has_option( self.name , "source" ) :
            self['source'] = config.get( self.name , "source" )

        if config.has_option( self.name , "gpgpass" ) :
            self['gpgpass'] = config.get( self.name , "gpgpass" )
        elif self['usegpg'] :
            self['gpgpass'] = getpass.getpass( "Supply passphrase for %s required on %s" % ( self['usegpg'] , self.name ) )

        if config.has_section( "global" ) :
            if config.has_option( "global" , "weburi" ) :
                web['uri'] = config.get( "global" , "weburi" )
            if config.has_option( "global" , "webconf" ) :
                web['conf'] = config.get( "global" , "webconf" )

def read_build_config ( repo_name , confdata=None ) :

    conffiles = [ buildconf ]
    conffiles.extend( glob.glob( os.path.join( builddir , "*.conf" ) ) )

    config = ConfigParser.RawConfigParser()
    if not config.read( conffiles ) :
        raise Exception( "Could not find a valid configuration file" )

    if confdata :
        for name in config.sections() :
            if name != "global" :
                config.remove_section( name )
        config.add_section( repo_name )
        for k,v in confdata.iteritems() :
            config.set( repo_name , k , v )
        infile = None
    else :
        infile = get_file( repo_name , conffiles )

    return BuildConf( repo_name , config , infile )


def get_all_build_repos () :

    conffiles = [ buildconf ]
    conffiles.extend( glob.glob( os.path.join( builddir , "*.conf" ) ) )

    config = ConfigParser.RawConfigParser()
    if not config.read( conffiles ) :
        raise Exception( "Could not find a valid configuration file" )

    names = config.sections()
    names.remove( 'global' )
    return names


def get_all_build_configs ( key=None , value=None ) :

    conffiles = [ buildconf ]
    conffiles.extend( glob.glob( os.path.join( builddir , "*.conf" ) ) )

    config = ConfigParser.RawConfigParser()
    if not config.read( conffiles ) :
        raise Exception( "Could not find a valid configuration file" )

    conflist = []

    for name in config.sections() :
        if name != "global" :
            try :
                conf = BuildConf( name , config , get_file( name , conffiles ) )
                if not key or conf[key] == value :
                    conflist.append( conf )
            except Exception , ex :
                repolib.logger.error( ex )

    return conflist


if __name__ == "__main__" :
    print get_all_build_repos()
    print 
    print get_all_mirror_configs()
    print 
    print get_all_mirror_configs( 'type' , 'apt' )

