#!/usr/bin/python

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


from BaseHTTPServer import BaseHTTPRequestHandler , HTTPServer

from cache import *

try :
    from mod_python import apache
except :
    import apcompat as apache

import os , urllib2


server_conf = { 
    'docroot' : "/home/repomirror" ,
    'source_url' : "http://ftp.es.debian.org/debian/"
    }


class Handler ( BaseHTTPRequestHandler ) :

    status = None
    content_type = None

    def sendfile ( self , path ) :
        fd = open( path )
        self.wfile.write( fd.read() )
        fd.close()

    def write ( self , msg ) :
        self.wfile.write( msg )

    def log_error ( self , msg , severity=apache.APLOG_ERROR ) :
        BaseHTTPRequestHandler.log_error( self , "%s : %s" % ( severity , msg ) )

    def do_GET ( self ) :

        uri = os.path.normpath(self.path).strip('/')
        local_path = os.path.join( server_conf['docroot'] , uri )

        remote_url = server_conf['source_url']

        if not remote_url.endswith('/') :
            remote_url += "/"
            req.log_error( "Fix configuration, source_url should have a trailing '/'" , apache.APLOG_INFO )

        remote_url = urllib2.urlparse.urljoin( remote_url , uri )

        retcode = get_file( self , local_path , remote_url )

        if not retcode :
            self.send_response( self.status )
        else :
            if self.status and self.status != retcode :
                self.log_error( "Return code '%s' didn't match status '%s'" % ( retcode , self.status ) )
            self.send_response( retcode )

        if self.content_type :
            self.send_header( "Content-Type" , self.content_type )

        self.end_headers()


try :
    server = HTTPServer( ('',8080) , Handler )
    server.serve_forever()
except KeyboardInterrupt , ex :
    server.socket.close()

