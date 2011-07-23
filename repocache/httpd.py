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

    def log_error ( self , msg , severity="ERROR" ) :
        BaseHTTPRequestHandler.log_error( self , "%s : %s" % ( severity , msg ) )

    def do_GET ( self ) :

        uri = os.path.normpath(self.path).strip('/')
        local_path = os.path.join( server_conf['docroot'] , uri )

        remote_url = server_conf['source_url']

        if not remote_url.endswith('/') :
            remote_url += "/"
            req.log_error( "Fix configuration, source_url should have a trailing '/'" , "INFO" ) # apache.APLOG_INFO )

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


def get_file ( req , local_path , remote_url ) :

    if not os.path.isdir( os.path.dirname(local_path) ) :
        try :
            os.makedirs( os.path.dirname(local_path) )
        except OSError , ex :
            req.log_error( "Cannot create destination hierarchy %s" % os.path.dirname(local_path) )
            req.status = 500 # apache.HTTP_INTERNAL_SERVER_ERROR
            return False # apache.DONE

    if not os.path.exists( local_path ) :
        try :
            req.log_error( "Downloading %s" % remote_url , "INFO" ) # apache.APLOG_INFO )
            remote = urllib2.urlopen( remote_url )
        except Exception , ex :
            req.log_error( "Cannot download remote %s : %s" % ( remote_url , ex ) )
            return 404 # apache.HTTP_NOT_FOUND
        try :
            local = open( local_path , 'wb' )
        except Exception , ex :
            req.log_error( "Cannot write local copy %s : %s" % ( local_path , ex ) )
            return 404 # apache.HTTP_NOT_FOUND

        # Block from http://stackoverflow.com/questions/22676/how-do-i-download-a-file-over-http-using-python
        file_size = int( remote.info().getheaders("Content-Length")[0] )
        if 'content-type' in remote.info().keys() :
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

    return 200 # apache.OK


try :
    server = HTTPServer( ('',8080) , Handler )
    server.serve_forever()
except KeyboardInterrupt , ex :
    server.socket.close()

