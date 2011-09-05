
import socket
socket.setdefaulttimeout(5)

import logging

console = logging.StreamHandler()
formatter = logging.Formatter("%(levelname)s : %(message)s")
console.setFormatter(formatter)

logger = logging.getLogger()
logger.addHandler( console )


import pwd

webserver_user = "apache"
webuid , webgid = pwd.getpwnam( webserver_user )[2:4]
apache_prefix = "/mirror"
apache_root = "/etc/httpd"


from base import *

from yum import *
from debian import *
from feed import *

