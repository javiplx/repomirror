
import socket
socket.setdefaulttimeout(5)

import logging

console = logging.StreamHandler()
formatter = logging.Formatter("%(levelname)s : %(message)s")
console.setFormatter(formatter)

logger = logging.getLogger()
logger.addHandler( console )


import config
from base import *


class MirrorRepository ( mirror_repository ) :

    def new ( name ) :
        _config = config.read_mirror_config( name )
        if _config['type'] == "yum" :
            return yum_repository( _config )
        elif _config['type'] == "fedora" :
            return fedora_repository( _config )
        elif _config['type'] == "centos" :
            return centos_repository( _config )
        elif _config['type'] == "fedora_upd" :
            return fedora_update_repository( _config )
        elif _config['type'] == "centos_upd" :
            return centos_update_repository( _config )
        elif _config['type'] == "deb" :
            return debian_repository( _config )
        elif _config['type'] == "feed" :
            return feed_repository( _config )
        else :
            Exception( "Unknown repository type '%s'" % _config['type'] )
    new = staticmethod( new )

class MirrorComponent ( mirror_component ) :
    pass

class BuildRepository ( build_repository ) :

    def new ( name ) :
        _config = config.read_build_config( name )
        if _config['type'] == "deb" :
            return debian_build_repository( _config )
        elif _config['type'] == "feed" :
            return feed_build_repository( _config , name )
        else :
            Exception( "Unknown repository build type '%s'" % _config['type'] )
    new = staticmethod( new )


from yum import *

from debian import *

from feed import *

