#!/usr/bin/python

# FIXME : Allow reading from a sources.list file, parsing into scheme, server, path, codename and components

params = {}


import urllib2

import os , sys


import repoutils

import repolib

if sys.argv[1:] :
    if len(sys.argv) > 2 :
        print "Too many arguments"
        print "Usage : %s repo_name" % os.path.basename( sys.argv[0] )
        sys.exit(2)
    repo_name = sys.argv[1]
else :
    print "Usage : %s repo_name" % os.path.basename( sys.argv[0] )
    sys.exit(1)

config = repoutils.read_build_config( repo_name )

repo = repolib.instantiate_repo( config , False )

print "Building configuration :",config
