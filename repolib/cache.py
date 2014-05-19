
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
    class apache :

        DONE = False

        APLOG_CRITICAL = "CRITICAL"
        APLOG_ERROR    = "ERROR"
        APLOG_INFO     = "INFO"
        APLOG_DEBUG    = "DEBUG"

        # BaseHTTPServer.BaseHTTPRequestHandler.responses
        OK = 200
        HTTP_INTERNAL_SERVER_ERROR = 500
        HTTP_NOT_FOUND = 404

import os , time
import repolib


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
            local = os.open( local_path , os.O_CREAT | os.O_RDWR )
        except Exception , ex :
            req.log_error( "Cannot write local copy %s : %s" % ( local_path , ex ) )
            return apache.HTTP_NOT_FOUND
        req.log_error( "Downloading %s" % remote_url , apache.APLOG_INFO )
        remote = repolib.download( remote_url , local , req )
        if not remote :
            req.log_error( "Cannot download remote %s" % remote_url )
            os.unlink( local_path )
            return apache.HTTP_NOT_FOUND

        for key in ( 'Content-Length' , 'Content-Type' , 'Last-Modified' ) :
            req.headers_out[key] = remote.headers[key]
            if key == 'Last-Modified' :
                mtime = time.strptime( remote.headers['Last-Modified'] , '%a, %d %b %Y %H:%M:%S %Z' )
                mstamp = time.mktime( mtime )
                os.utime( local_path , (mstamp,mstamp))
        req.fd = os.fdopen( local )
        req.fd.seek(0)

    else :
        req.fd = open( local_path )
        fileinfo = os.fstat( req.fd.fileno() )
        req.headers_out['Content-Length'] = fileinfo.st_size
        req.headers_out['Last-Modified'] = time.strftime( '%a, %d %b %Y %T GMT' , time.gmtime( fileinfo.st_mtime ) )

    return apache.OK


def handler ( req ) :

    local_path = req.filename
    subpath = local_path.replace( req.hlist.directory , "" , 1 )
    remote_url = req.get_options().get('source_url')
    if not remote_url.endswith('/') :
        remote_url += "/"
        req.log_error( "Fix configuration, source_url should have a trailing '/'" , apache.APLOG_INFO )

    if req.used_path_info :
        local_path += req.path_info
        remote_url = repolib.urljoin( remote_url , subpath + req.path_info )

    return get_file( req , local_path , remote_url )

