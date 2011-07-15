
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

source_url = {}
source_url['debian'] = "http://ftp.es.debian.org/"
source_url['debian-security'] = "http://security.debian.org/"


def handler ( req ) :

    local_path = req.filename
    subpath = local_path.replace( req.hlist.directory , "" , 1 )
    reponame = subpath.split("/")[0]
    remote_url = source_url[reponame]

    if req.used_path_info :
        local_path += req.path_info
        remote_url = urllib2.urlparse.urljoin( remote_url , subpath + req.path_info )

    if not os.path.isdir( os.path.dirname(local_path) ) :
        try :
            os.makedirs( os.path.dirname(local_path) )
        except OSError , ex :
            req.log_error( "Cannot create destination hierarchy %s" % os.path.dirname(local_path) )
            req.status = apache.HTTP_INTERNAL_SERVER_ERROR
            return apache.DONE

    if not os.path.exists( local_path ) :
        try :
            req.log_error( "Downloading %s" % remote_url , apache.APLOG_INFO )
            remote = urllib2.urlopen( remote_url )
        except Exception , ex :
            req.log_error( "Cannot download remote %s : %s" % ( remote_url , ex ) )
            return apache.HTTP_NOT_FOUND
        local = open( local_path , 'wb' )

        # Block from http://stackoverflow.com/questions/22676/how-do-i-download-a-file-over-http-using-python
        file_size = int( remote.info().getheaders("Content-Length")[0] )
        req.content_type = remote.info().getheader('Content-Type')

        file_size_dl = 0
        block_sz = 8192
        while True:
            buffer = remote.read(block_sz)
            if not buffer:
                break

            file_size_dl += block_sz
            local.write(buffer)
            req.write(buffer)

        remote.close()
        local.close()
    else :
        req.sendfile(local_path)

    return apache.OK

