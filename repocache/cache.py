
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


try :
    from mod_python import apache
except :
    import apcompat as apache

import os
from repolib import utils


def get_file ( req , local_path , remote_url ) :

    if not os.path.isdir( os.path.dirname(local_path) ) :
        try :
            os.makedirs( os.path.dirname(local_path) )
        except OSError , ex :
            req.log_error( "Cannot create destination hierarchy %s" % os.path.dirname(local_path) )
            req.status = apache.HTTP_INTERNAL_SERVER_ERROR
            return apache.DONE

    if not os.path.exists( local_path ) :
        try :
            local = os.open( local_path , os.O_CREAT | os.O_WRONLY )
        except Exception , ex :
            req.log_error( "Cannot write local copy %s : %s" % ( local_path , ex ) )
            return apache.HTTP_NOT_FOUND
        req.log_error( "Downloading %s" % remote_url , apache.APLOG_INFO )
        remote = utils.download( remote_url , local , req )
        if not remote :
            req.log_error( "Cannot download remote %s" % remote_url )
            return apache.HTTP_NOT_FOUND

        file_size = int( remote.info().getheaders("Content-Length")[0] )
        if 'content-type' in remote.info().keys() :
            req.content_type = remote.info().getheader('Content-Type')

    else :
        req.sendfile(local_path)

    return apache.OK

