
from django.shortcuts import render_to_response

from repolib.config import MirrorConf

from django.http import HttpResponse

import ConfigParser
import os

def index ( request ) :

    config = ConfigParser.RawConfigParser()
    if not config.read( [ "/etc/repomirror.conf" , os.path.expanduser("~/.repomirror") ] ) :
        response = HttpResponse()
        response.write( "Server Error\n" )
        return response
    sections = config.sections()
    if config.has_section( "global" ) :
        sections.pop( sections.index( "global" ) )
    keylist =  ( 'type' , 'url' , 'version' , 'architectures' )
    response = render_to_response( 'templates/index.html' , { 'keylist':keylist } )
    response.write( "<tbody>\n" )
    for section in sections :
        repo = MirrorConf( section )
        repo.read( config )
        response.write( "<tr>\n" )
        response.write( "<td><a href=%s>%s</a></td>\n" % ( section , repo.__name__ ) )
        for key in keylist :
            response.write( "<td>%s</td>\n" % repo[key] )
        response.write( "</tr>\n" )
    response.write( "</tbody>\n" )
    response.write( "</table>\n" )

    return response


def detail ( request , repo_name ) :

    response = HttpResponse()
    config = ConfigParser.RawConfigParser()
    if not config.read( [ "/etc/repomirror.conf" , os.path.expanduser("~/.repomirror") ] ) :
        response.write( "Server Error\n" )
        return response
    repo = MirrorConf( repo_name )
    repo.read( config )
    response.write( "<h3>%s</h3>\n" % repo.__name__ )
    response.write( "<ul>\n" )
    keys = [ 'type' , 'mode' ]
    if repo['detached'] :
        keys.extend( ( 'detached' , 'destdir' ) )
    keys.extend( ( 'version' , 'architectures' , 'components' ) )
    for key in keys :
        response.write( "<li><b>%s</b> - %s\n" % ( key , repo[key] ) )
    extra = ""
    if repo.url_parts :
        _keys = ( 'scheme' , 'server' , 'base_path' )
        for i in range(3) :
            response.write( "<li><b>%s</b> - %s\n" % ( _keys[i] , repo.url_parts[i] ) )
        extra = " (ro) "
    response.write( "<li><b>url%s</b> - %s\n" % ( extra , repo['url'] ) )
    keys.append( 'url' )
    if not repo['detached'] :
        keys.extend( ( 'detached' , 'destdir' ) )
    response.write( "</ul>\n" )
    response.write( "<h4>Extra values</h4>\n" )
    response.write( "<ul>\n" )
    for key in repo.keys() :
        if key not in keys :
            response.write( "<li><b>%s</b> - %s\n" % ( key , repo[key] ) )
    response.write( "</ul>\n" )

    response.write( "<a href=./>Go to main page</a>\n" )

    return response

