
from django.conf.urls.defaults import *

from django.http import HttpResponse

import ConfigParser
import os

def index ( request ) :

    response = HttpResponse()
    config = ConfigParser.RawConfigParser()
    if not config.read( [ "/etc/repomirror.conf" , os.path.expanduser("~/.repomirror") ] ) :
        response.write( "Server Error\n" )
        return response
    sections = config.sections()
    if config.has_section( "global" ) :
        sections.pop( sections.index( "global" ) )
        response.write( "<h3>global</h3>\n" )
        response.write( "<ul>\n" )
        for item in config.items('global') :
            response.write( "<li><b>%s</b> - %s\n" % item )
        response.write( "</ul>\n" )
    for section in sections :
        response.write( "<h3>%s</h3>\n" % section )
        response.write( "<ul>\n" )
        for item in config.items( section ) :
            response.write( "<li><b>%s</b> - %s\n" % item )
        response.write( "</ul>\n" )

    return response


urlpatterns = patterns('',
    (r'^.*$', index),
)

