
import socket
socket.setdefaulttimeout(5)

import logging

console = logging.StreamHandler()
formatter = logging.Formatter("%(levelname)s : %(message)s")
console.setFormatter(formatter)

logger = logging.getLogger()
logger.addHandler( console )


from utils import *

from base import *

from yum import *
from repodeb import *
from feed import *

