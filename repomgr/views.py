
from django.shortcuts import render_to_response

from repolib.config import MirrorConf , get_all_configs

from django.http import HttpResponse

import ConfigParser
import os

def index ( request ) :

    keylist =  ( 'type' , 'url' , 'version' , 'architectures' )
    repos = []
    for repo in get_all_configs() :
        repodesc = { 'name':repo.__name__ , 'values':[] }
        for key in keylist :
            repodesc['values'].append( repo[key] )
        repos.append( repodesc )
    return render_to_response( 'templates/index.html' , { 'keylist':keylist , 'repos':repos } )


def detail ( request , repo_name ) :

    config = ConfigParser.RawConfigParser()
    if not config.read( [ "/etc/repomirror.conf" , os.path.expanduser("~/.repomirror") ] ) :
        response = HttpResponse()
        response.write( "Server Error\n" )
        return response
    repo = MirrorConf( repo_name )
    repo.read( config )
    repo['name'] = repo.__name__
    keys = [ 'name' , 'type' , 'mode' , 'detached' , 'destdir' , 'version' , 'architectures' , 'components' , 'url' ]
    if repo.url_parts :
        keys.extend( ( 'scheme' , 'server' , 'base_path' ) )
        repo['url'] += " (ro)"
    response = render_to_response( 'templates/detail.html' , { 'repo':repo , 'keys':keys } )
    for key in repo.keys() :
        if key not in keys :
            response.write( "<li><b>%s</b> - %s\n" % ( key , repo[key] ) )
    response.write( "</ul>\n" )

    response.write( "<a href=./>Go to main page</a>\n" )

    return response

