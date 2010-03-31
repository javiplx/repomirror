
pgpkey = "archive-key-5.0.asc"
import GnuPGInterface

scheme = "http"
server = "ftp.es.debian.org"
base_path = "debian"

codename = "lenny"
components = [ "main" , "contrib" ]
architectures = [ "i386" , "amd64" ]
#
sections = None
priorities = None
tags = None
priorities = "optional"
"""
From the default importing values, we get

All sects ['utils', 'games', 'net', 'x11', 'perl', 'text', 'libdevel', 'libs', 'graphics', 'doc', 'devel', 'kde', 'sound', 'math', 'science', 'editors', 'tex', 'mail', 'admin', 'gnome', 'misc', 'hamradio', 'web', 'python', 'interpreters', 'otherosfs', 'comm', 'electronics', 'news', 'shells', 'oldlibs', 'embedded', 'contrib/net', 'contrib/games', 'contrib/sound', 'contrib/x11', 'contrib/otherosfs', 'contrib/text', 'contrib/doc', 'contrib/devel', 'contrib/libs', 'contrib/utils', 'contrib/electronics', 'contrib/graphics', 'contrib/misc', 'contrib/science', 'contrib/perl', 'contrib/python', 'contrib/tex', 'contrib/kde', 'contrib/admin', 'contrib/libdevel', 'contrib/editors', 'contrib/mail', 'contrib/math', 'contrib/web']
All prios ['optional', 'extra', 'required', 'important', 'standard']
All tags __INFINITE__

After purging the component name, sections get as
All sects ['utils', 'games', 'net', 'x11', 'perl', 'text', 'libdevel', 'libs', 'graphics', 'doc', 'devel', 'kde', 'sound', 'math', 'science', 'editors', 'tex', 'mail', 'admin', 'gnome', 'misc', 'hamradio', 'web', 'python', 'interpreters', 'otherosfs', 'comm', 'electronics', 'news', 'shells', 'oldlibs', 'embedded']
"""

import debian_bundle.deb822 , debian_bundle.debian_support

import urllib2

import sys


def show_error( str , error=True ) :
    if error :
        print "ERROR : %s" % str
    else :
        print "WARNING : %s" % str


base_url = "%s://%s/%s/dists/%s" % ( scheme , server , base_path , codename )

# NOTE : We need this block because there is no debian_bundle.debian_support.downloadLines block
try :
    #release_fd = open( "Release" )
    release_fd = urllib2.urlopen( "%s/Release" % base_url )
except urllib2.URLError , ex :
    print "Exception : %s" % ex
    sys.exit(255)
except urllib2.HTTPError , ex :
    print "Exception : %s" % ex
    sys.exit(255)

# FIXME : Verify gpg signature. Easier if file gets downloaded.

release = debian_bundle.deb822.Release( sequence=release_fd )

if release['Suite'].lower() == codename.lower() :
    show_error( "You have supplied suite '%s'. Please use codename '%s' instead\n" % ( codename, release['Codename'] ) )
    sys.exit(1)

release_comps = release['Components'].split()
for comp in components :
    if comp not in release_comps :
        show_error( "Component '%s' is not available ( %s )" % ( comp , " ".join(release_comps) ) )
        sys.exit(1)

release_archs = release['Architectures'].split()
for arch in architectures :
    if arch not in release_archs :
        show_error( "Architecture '%s' is not available ( %s )" % ( arch , " ".join(release_archs) ) )
        sys.exit(1)

print """Mirroring %(Label)s %(Version)s (%(Codename)s)
%(Origin)s %(Suite)s , %(Date)s""" % release
print "Components : %s\nArchitectures : %s" % ( " ".join(components) , " ".join(architectures) )


download_pkgs = {}
download_size = 0

release_sections = []
release_priorities = []
release_tags = []

for arch in architectures :
    for comp in components :

        print "Scanning %s / %s" % ( comp , arch )

        # Downloading Release file is quite redundant

        packages_file = "%s/binary-%s/Packages" % ( comp , arch  )
#        packages = debian_bundle.debian_support.PackageFile( debian_bundle.debian_support.downloadGunzipLines( "%s/%s" % ( base_url , packages_file ) ) )
        import tempfile , os
        temprelease , tempname = tempfile.mkstemp()
        os.close( temprelease )
        debian_bundle.debian_support.downloadFile( "%s/%s" % ( base_url , packages_file ) , tempname )
        #
        # IMPROVEMENT : For Release at least, and _multivalued in general : Multivalued fields returned as dicts instead of lists
        #
        for item in release['MD5Sum'] :
            if item['name'] == packages_file + ".gz" :
                # FIXME : Verify checksum of Pacakges.gz
                show_error( "Verify checksum '%s' for '%s'" % ( item['md5sum'] , item['name'] ) , False )
                break
        else :
            show_error( "File '%s.gz' not found" % ( packages_file ) )
            sys.exit(0)
        #
        packages = debian_bundle.debian_support.PackageFile( tempname )
        os.unlink( tempname )

        for pkg in packages :
            info = {}
            for i,j in pkg :
                info[i] = j

            # NOTE : Is this actually a good idea ?? It simplifies, but I would like to mirror main/games but not contrib/games, for example
            # SOLUTION : Create a Category with the last part (filename) of Section
            # For now, we kept the simplest way
            if info['Section'].find("%s/"%comp) == 0 :
                info['Section'] = info['Section'][info['Section'].find("/")+1:]

            if info['Section'] not in release_sections :
                release_sections.append( info['Section'] )
            if info['Priority'] not in release_priorities :
                release_priorities.append( info['Priority'] )
            if 'Tag' in info.keys() and info['Tag'] not in release_tags :
                release_tags.append( info['Tag'] )

            if sections and info['Section'] not in sections :
                continue
            if priorities and info['Priority'] not in priorities :
                continue
            if tags and 'Tag' in info.keys() and info['Tag'] not in tags :
                continue

            pkg_key = "%s-%s" % ( info['Package'] , info['Architecture'] )
            if pkg_key in download_pkgs.keys() :
                if info['Architecture'] != "all" :
                    show_error( "Package '%s - %s' is duplicated in repositories" % ( info['Package'] , info['Architecture'] ) , False )
                continue
            download_pkgs[ pkg_key ] = info
            # FIXME : This might cause a ValueError exception ??
            download_size += int( info['Size'] )

# print "All sects",release_sections
# print "All prios",release_priorities
# # print "All tags",release_tags


print "Total size to download : %.1f Gb" % ( download_size / 1024 / 1024 )

for pkg in download_pkgs.values() :
    print "Downloading file '%s'" % ( pkg['Filename'] )
    #debian_bundle.debian_support.downloadFile( pkg['Filename'] )

