
__all__ = [ "YumPackageFile" , "YumDownloadFile" ]

import tempfile

from repolib.lists import safe_encode
from repolib.lists import PackageListInterface , AbstractDownloadList


class PackageFile :
    """File based storage for package lists, to reduce memory footprint.
It is a full implementation of PackageListInterface, but it is not declared
to avoid inheritance problems"""

    out_template = """name=%(name)s
arch=%(arch)s
sha256=%(sha256)s
size=%(size)s
href=%(href)s
Filename=%(Filename)s
group=%(group)s
provides=%(provlist)s
requires=%(reqlist)s

"""

    def __init__ ( self ) :
        self.pkgfd = tempfile.NamedTemporaryFile()
        self.index = 0
        self.__cnt = 0

    def __len__ ( self ) :
        return self.__cnt

    def __iter__ ( self ) :
        _pkg = {}
        self.rewind()
        line = self.pkgfd.readline()
        while line :
            if line == '\n' :
                self.index += 1
                yield _pkg
                _pkg.clear()
            else :
                k,v = line[:-1].split('=',1)
                if k in ( "provides" , "requires" ) :
                  if v :
                    _pkg[k] = v.split(",")
                else :
                  _pkg[k] = v
            line = self.pkgfd.readline()
        if _pkg :
            self.index += 1
            yield _pkg

    def rewind ( self ) :
        if self.pkgfd :
            self.index = 0
            self.pkgfd.seek(0)

    def append ( self , pkg ) :
        self.__cnt += 1
        pkg['provlist'] = ",".join( map( safe_encode , pkg.get("provides",()) ) )
        pkg['reqlist'] = ",".join( map( safe_encode , pkg.get("requires",()) ) )
        self.pkgfd.write( self.out_template % pkg )

class YumPackageFile ( PackageListInterface , PackageFile ) :
    __iter__ = PackageFile.__iter__

    def __init__ ( self ) :
        PackageFile.__init__( self )

    def append ( self , item ) :
        self.weight += int( item['size'] )
        PackageFile.append( self , item )

class YumDownloadFile ( AbstractDownloadList , PackageFile ) :
    append = PackageFile.append

    def __init__ ( self , repo ) :
        PackageFile.__init__( self )
        AbstractDownloadList.__init__( self , repo )

    def __nonzero__ ( self ) :
        return self.index != len(self)

    def __iter__ ( self ) :
        if self.started :
            raise Exception( "Trying to iterate over a running list" )
        return PackageFile.__iter__( self )

    def append ( self , item ) :
        if self.closed :
            raise Exception( "Trying to append into a closed queue" )
        self.weight += int( item['size'] )
        PackageFile.append( self , item )

# NOTE : YumXMLPackageList is not usable yet
# NOTE : The xml version seems more attractive, but we cannot use it until
#        we get a way to build an iterable XML parser, maybe availeble
#        using xml.etree.ElementTree.iterparse
class YumXMLPackageList ( YumPackageFile ) :

    out_template = """<package type="rpm">
  <name>%(name)s</name>
  <checksum type="sha256" pkgid="YES">%(sha256)s</checksum>
  <size package="%(size)s"/>
  <location href="%(href)s"/>
  <poolfile href="%(Filename)s"/>
</package>
"""

    def __init__ ( self ) :
        """Input uses a list interface, and output a sequence interface taken from original PackageFile"""
        YumPackageFile.__init__( self )
        self.pkgfd.write( '<?xml version="1.0" encoding="UTF-8"?>\n' )
        self.pkgfd.write( '<metadata xmlns="http://linux.duke.edu/metadata/common" xmlns:rpm="http://linux.duke.edu/metadata/rpm">\n' )

    def __iter__ ( self ) :
        raise Exception( "Iterable parser not yet implemented" )

    # NOTE : The flush methods move this object somewhat between a simple and a download list
    def flush ( self ) :
        self.pkgfd.write( '</metadata>\n' )


