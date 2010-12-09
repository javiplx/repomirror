
import os

import utils , repolib
import ConfigParser


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


default_params = {}

# mode (update|init) - decides if we stop processing for unchanged metadata files
default_params['mode'] = "update"

# usegpg. To disable verification of PGP signatures, and force the download of master file every run
default_params['usegpg'] = True
try :
    import GnuPGInterface
    default_params['usegpg'] = True
except :
    default_params['usegpg'] = False


# usemd5. To disable size & checksums verification for broken repositories
default_params['usemd5'] = True


# pkgvflags. To specify special flags for verification of downloaded packages
default_params['pkgvflags'] = "SKIP_NONE"


def __config ( repo_name , config ) :

    if repo_name not in config.sections() :
        print "Repository '%s' is not configured" % repo_name
        return False

    conf = {}
    conf['name'] = repo_name

    if config.has_option( repo_name , "destdir" ) :

        conf['destdir'] = config.get( repo_name , "destdir" )
        conf['detached'] = True

    else :

        if "global" not in config.sections() :
            print "Broken configuration, missing global section"
            return False

        if not config.has_option( "global", "destdir" ) :
            print "Broken configuration, missing destination directory"
            return False

        conf['destdir'] = config.get( "global" , "destdir" )
        conf['detached'] = False

    conf['type'] = config.get( repo_name , "type" )

    conf['version'] = config.get( repo_name , "version" )
    conf['architectures'] = config.get( repo_name , "architectures" ).split()
    if config.has_option( repo_name , "components" ) :
        conf['components'] = config.get( repo_name , "components" ).split()

    return conf


def read_mirror_config ( repo_name ) :

    config = ConfigParser.RawConfigParser()
    if not config.read( [ "/etc/repomirror.conf" , os.path.expanduser("~/.repomirror") ] ) :
        print "Could not find a valid configuration file"
        return False

    conf = __config( repo_name , config )

    if config.has_option ( repo_name , "url" ) :
        conf['url'] = config.get( repo_name , "url" )
    else :
        scheme = config.get( repo_name , "scheme" )
        server = config.get( repo_name , "server" )
        base_path = config.get( repo_name , "base_path" )
        conf['url'] = repolib.unsplit( scheme , server , "%s/" % base_path )

    conf['filters'] = {}
    if config.has_option( repo_name , "filters" ) :
        for subfilter in config.get( repo_name , "filters" ).split() :
            if config.has_option( repo_name , subfilter ) :
                conf['filters'][subfilter] = map( lambda x : x.replace("_"," ") , config.get( repo_name , subfilter ).split() )

    conf['params'] = {}
    conf['params'].update( default_params )
    for key in conf['params'].keys() :
        if config.has_option( "global" , key ) :
            try :
                conf['params'][ key ] = config.getboolean( "global" , key )
            except ValueError , ex :
                conf['params'][ key ] = config.get( "global" , key )
        if config.has_option( repo_name , key ) :
            try :
                conf['params'][ key ] = config.getboolean( repo_name , key )
            except ValueError , ex :
                conf['params'][ key ] = config.get( repo_name , key )

    conf['params']['pkgvflags'] = eval( "utils.%s" % conf['params']['pkgvflags'] )

    return conf

def read_build_config ( repo_name ) :

    config = ConfigParser.RawConfigParser()
    if not config.read( [ "/etc/buildrepo.conf" , os.path.expanduser("~/.buildrepo") ] ) :
        print "Could not find a valid configuration file"
        return False

    if repo_name not in config.sections() :
        print "Repository '%s' is not configured" % repo_name
        return False

    conf = __config( repo_name , config )

    return conf

