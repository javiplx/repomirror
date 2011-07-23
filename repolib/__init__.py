
import socket
socket.setdefaulttimeout(5)

import logging

console = logging.StreamHandler()
formatter = logging.Formatter("%(levelname)s : %(message)s")
console.setFormatter(formatter)

logger = logging.getLogger()
logger.addHandler( console )


from base import *

from yum import *
from debian import *
from feed import *

