
# Copyright (C) 2011 Javier Palacios
# 
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License Version 2
# as published by the Free Software Foundation.
# 
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.


from mod_python import apache

import urllib2
import os

source_url = "http://ftp.es.debian.org/"

def headerparserhandler ( req ) :

    local_path = req.filename
    remote_url = source_url

    if req.used_path_info :
        local_path += req.path_info
        remote_url = urllib2.urlparse.urljoin( remote_url , local_path.replace( req.hlist.directory , "" , 1 ) )

    if not os.path.isdir( os.path.dirname(local_path) ) :
        try :
            os.makedirs( os.path.dirname(local_path) )
        except OSError , ex :
            req.log_error( "Cannot create destination hierarchy" )
            req.status = apache.HTTP_INTERNAL_SERVER_ERROR
            return apache.DONE

    if not os.path.exists( local_path ) :
        try :
            remote = urllib2.urlopen( remote_url )
        except :
            return apache.HTTP_NOT_FOUND
        local = open( local_path , 'w' )
# Instead of redirecting, we could also perform a buffered double write to speed up
        local.write( remote.read() )
        remote.close()
        local.close()
        req.internal_redirect( req.uri )

    return apache.OK

