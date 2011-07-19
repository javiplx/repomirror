
import tempfile

from package_lists import AbstractDownloadThread , PackageListInterface , AbstractDownloadList


class _YumPackageFile :
    """This pretends to be a file base storage for package lists, to reduce memory footprint.
Is an actual complete implementation of PackageListInterface, but it is not declared
to avoid inheritance problems"""

    out_template = """name=%s
sha256=%s
size=%s
href=%s
Filename=%s

"""

    def __init__ ( self ) :
        self.pkgfd = tempfile.NamedTemporaryFile()
        self.__cnt = 0

    def __len__ ( self ) :
        return self.__cnt

    def __iter__ ( self ) :
        _pkg = {}
        self.rewind()
        line = self.pkgfd.readline()
        while line :
            if line == '\n' :
                yield _pkg
                _pkg = {}
            else :
                k,v = line[:-1].split('=',1)
                _pkg[k] = v
            line = self.pkgfd.readline()
        if _pkg :
            yield _pkg

    def rewind ( self ) :
        if self.pkgfd :
            self.pkgfd.seek(0)

    def append ( self , pkg ) :
        self.pkgfd.write( self.out_template % ( pkg['name'] , pkg.get( 'sha256' , pkg.get( 'sha' ) ) , pkg['size'] , pkg['href'] , pkg['Filename'] ) )
        self.__cnt += 1

class _YumPackageList ( list ) :

    def __repr__ ( self ) :
        return "<_YumPackageList items:%d>" % len(self)

class YumPackageFile ( _YumPackageFile , PackageListInterface ) :

    def extend ( self , values_list ) :
        self.pkgfd.seek(0,2)
        for pkg in values_list :
            self.append( pkg )

class YumDownloadList ( _YumPackageFile , AbstractDownloadList ) :

    def __init__ ( self , repo ) :
        _YumPackageFile.__init__( self )
        AbstractDownloadList.__init__( self , repo )

    def push ( self , item ) :
        if self.closed :
            raise Exception( "Trying to push into a closed queue" )
        _YumPackageFile.append( self , item )

class YumDownloadThread ( _YumPackageFile , AbstractDownloadThread ) :

    def __init__ ( self , repo ) :
        _YumPackageFile.__init__( self )
        AbstractDownloadThread.__init__( self , repo )

    def __iter__ ( self ) :
        if self.started :
            raise Exception( "Trying to iterate over a running list" )
        return _YumPackageFile.__iter__( self )


# NOTE : The xml version seems more attractive, but we cannot use it until
#        we get a way to build an iterable XML parser, maybe availeble
#        using xml.etree.ElementTree.iterparse
class YumXMLPackageList ( _YumPackageFile ) :

    out_template = """<package type="rpm">
  <name>%s</name>
  <checksum type="sha256" pkgid="YES">%s</checksum>
  <size package="%s"/>
  <location href="%s"/>
  <poolfile href="%s"/>
</package>
"""

    def __init__ ( self ) :
        """Input uses a list interface, and output a sequence interface taken from original PackageFile"""
        _YumPackageFile.__init__( self )
        self.pkgfd.write( '<?xml version="1.0" encoding="UTF-8"?>\n' )
        self.pkgfd.write( '<metadata xmlns="http://linux.duke.edu/metadata/common" xmlns:rpm="http://linux.duke.edu/metadata/rpm">\n' )

    def __iter__ ( self ) :
        raise Exception( "Iterable parser not yet implemented" )

    # NOTE : The flush methods move this object somewhat between a simple and a download list
    def flush ( self ) :
        self.pkgfd.write( '</metadata>\n' )


