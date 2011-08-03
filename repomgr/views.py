
from django.shortcuts import render_to_response

from repolib.config import read_mirror_config , get_all_configs

from django.http import HttpResponse

import ConfigParser
import os

def index ( request ) :

    keylist =  ( 'type' , 'url' , 'version' , 'architectures' )
    repos = []
    for repo in get_all_configs() :
        repodesc = { 'name':repo.name , 'values':[] }
        for key in keylist :
            repodesc['values'].append( repo[key] )
        repos.append( repodesc )
    return render_to_response( 'templates/index.html' , { 'keylist':keylist , 'repos':repos } )


def detail ( request , repo_name ) :

    repo = read_mirror_config( repo_name )
    keys = [ 'name' , 'type' , 'detached' , 'destdir' , 'version' , 'architectures' , 'components' , 'url' ]
    if not repo['detached'] :
        repo['destdir'] += " (ro)"
    if repo.url_parts :
        keys.extend( ( 'scheme' , 'server' , 'base_path' ) )
        repo['url'] += " (ro)"
    extras = {}
    for key in repo.keys() :
        if key not in keys :
            extras[ key ] = repo[key]
    return render_to_response( 'templates/detail.html' , { 'repo':repo , 'keys':keys , 'extras':extras } )

