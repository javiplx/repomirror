
__all__ = [ "DebianPackageFile" , "DebianDownloadFile" , "DebianDownloadThread" ]

import debian_bundle.deb822 , debian_bundle.debian_support

import tempfile

from repolib.lists import PackageListInterface , AbstractDownloadList , AbstractDownloadThread


def safe_encode ( str ) :
    try :
        out = "%s" % str.encode('utf-8')
    except UnicodeDecodeError , ex :
        out = "%s" % str
    return out

# Derived from Deb822.dump()
def dump_package(deb822 , fd):
    _multivalued_fields = ( "Description" , "Conffiles" )
    for key, value in deb822.iteritems():
        if not value or ( value[0] == '\n' and key not in _multivalued_fields ) :
            # Avoid trailing whitespace after "Field:" if it's on its own
            # line or the value is empty
            # XXX Uh, really print value if value == '\n'?
            fd.write('%s:%s\n' % (key, safe_encode(value)))
        else :
            values = value.split('\n')
            fd.write('%s: %s\n' % (key, safe_encode(values.pop(0))))
            for v in values:
                _v = values.pop(0)
                if _v == '' :
                    fd.write(' .\n')
                else :
                    fd.write(' %s\n' % safe_encode(_v))
    fd.write('\n')

class PackageFile ( debian_bundle.debian_support.PackageFile ) :
    """Implements of a read & write PackageFile."""

    def __init__ ( self ) :
        self.pkgfd = tempfile.NamedTemporaryFile()
        debian_bundle.debian_support.PackageFile.__init__( self , self.pkgfd.name , self.pkgfd )
        self.index = 0
        self.__cnt = 0

    def __len__ ( self ) :
        return self.__cnt

    def __iter__ ( self ) :
        self.rewind()
        _pkg = debian_bundle.debian_support.PackageFile.__iter__( self )
        while _pkg :
            pkg = debian_bundle.deb822.Deb822()
            pkg.update( _pkg.next() )
            self.index += 1
            yield pkg
            _pkg = debian_bundle.debian_support.PackageFile.__iter__( self )

    # This is a final method, not overridable
    def rewind ( self ) :
        if self.pkgfd :
            self.pkgfd.seek(0)
            self.index = 0

    def append ( self , pkg ) :
        dump_package( pkg , self.pkgfd )
        self.__cnt += 1

class DebianPackageFile ( PackageListInterface , PackageFile ) :
    __iter__ = PackageFile.__iter__

    def __init__ ( self ) :
        PackageFile.__init__( self )

    def append ( self , pkg ) :
        self.weight += int( pkg['size'] )
        PackageFile.append( self , pkg )

class DebianDownloadFile ( AbstractDownloadList , PackageFile ) :
    __iter__ = PackageFile.__iter__

    def __init__ ( self , repo ) :
        PackageFile.__init__( self )
        AbstractDownloadList.__init__( self , repo )

    def append ( self , pkg ) :
        self.weight += int( pkg['size'] )
        PackageFile.append( self , pkg )

    def __nonzero__ ( self ) :
        return self.index != len(self)

    def push ( self , item ) :
        if self.closed :
            raise Exception( "Trying to push into a closed queue" )
        self.append( item )

class DebianDownloadThread ( AbstractDownloadThread , list ) :
 
    def __hash__ ( self ) :
        return AbstractDownloadThread.__hash__( self )

    def __init__ ( self , repo=None ) :
        AbstractDownloadThread.__init__( self , repo )
        list.__init__( self )

    def __iter__ ( self ) :
        if self.started :
            raise Exception( "Trying to iterate over a running list" )
        return list.__iter__( self )

    def append ( self , item ) :
        self.weight += int( item['size'] )
        list.append( self , item )

