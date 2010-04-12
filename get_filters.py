#!/usr/bin/python

# FIXME : Allow reading from a sources.list file, parsing into scheme, server, path, codename and components

params = {}
# mode (update|init) - decides if we stop processing for unchanged metadata files
params['mode'] = "init"

# usegpg. To disable verification of PGP signatures. Forces the download of Release file every run
# FIXME : Add an ignore all verifications? (pgp+md5)
params['usegpg'] = False


# usemd5. To disable size & checksums verification for broken repositories
params['usemd5'] = False


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

config = repoutils.read_config( repo_name )

repo = repolib.instantiate_repo( config )

base_url = repo.base_url()


meta_files = repo.get_master_file( params )

# FIXME : debian - identify error from updated repositories
# FIXME : yum - only errors produce empty output
if not meta_files :
    repoutils.show_error( "Cannot process, exiting" )
    sys.exit(255)

# After verify all the mirroring parameters, it is safe to create directory tree

repo.build_local_tree()

# Once created, we move in the primary metadata file

local_repodata = repo.write_master_file( meta_files )

print repo.info( local_repodata )


download_pkgs = {}
download_size = 0

for subrepo in repo.get_subrepos() :

    print "Scanning %s" % ( subrepo , )

    _size , _pkgs = repo.get_package_list( subrepo , local_repodata , params , {} )
    download_size += _size
    download_pkgs.update( _pkgs )


sections = {}
priorities = {}
tags = {}

for pkg in download_pkgs.values() :

    if pkg.has_key('Section') :
        sections[ pkg['Section'] ] = True
    if pkg.has_key('group') :
        sections[ pkg['group'] ] = True

    if pkg.has_key( 'Tag' ) :
        for tag in pkg['Tag'].split(', ') :
            key , val = tag.split('::',1)
            if not tags.has_key( key ) :
                tags[ key ] = {}
            tags[ key ][ val ] = True

    if pkg.has_key( 'Priority' ) :
        priorities[ pkg['Priority'] ] = True

print
print

if sections : print "sections :",sections.keys()
if priorities : print "priorities :",priorities.keys()
if tags : print "tags :",map ( lambda x : "%s - %s" % ( x , tags[x].keys() ) , tags.keys() )

