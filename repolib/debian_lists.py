
import debian_bundle.deb822 , debian_bundle.debian_support

import tempfile

from package_lists import AbstractDownloadThread , PackageListInterface , AbstractDownloadList


def safe_encode ( str ) :
    try :
        out = "%s" % str.encode('utf-8')
    except UnicodeDecodeError , ex :
        out = "%s" % str
    return out

# Derived from Deb822.dump()
def dump_package(deb822 , fd):
    _multivalued_fields = [ "Description" ]
    for key, value in deb822.iteritems():
        if not value or value[0] == '\n':
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

class _DebianPackageList ( list ) :

    def __repr__ ( self ) :
        return "<_DebianPackageList items:%d>" % len(self)

    def start ( self ) :
        pass

    def rewind ( self ) :
        pass

class _DebianPackageFile ( debian_bundle.debian_support.PackageFile ) :
    """This implements a read & write PackageFile.
Input uses a list interface, and output a sequence interface taken from original PackageFile"""

    def __init__ ( self ) :
        self.pkgfd = tempfile.NamedTemporaryFile()
        debian_bundle.debian_support.PackageFile.__init__( self , self.pkgfd.name , self.pkgfd )
        self.__cnt = 0

    def __len__ ( self ) :
        return self.__cnt

    def __iter__ ( self ) :
        self.rewind()
        _pkg = debian_bundle.debian_support.PackageFile.__iter__( self )
        while _pkg :
            pkg = debian_bundle.deb822.Deb822()
            pkg.update( _pkg.next() )
            yield pkg
            _pkg = debian_bundle.debian_support.PackageFile.__iter__( self )

    # This is a final method, not overridable
    def rewind ( self ) :
        if self.pkgfd :
            self.pkgfd.seek(0)

    def append ( self , pkg ) :
        dump_package( pkg , self.pkgfd )
        self.__cnt += 1

class DebianPackageList ( _DebianPackageList , PackageListInterface ) :

    def extend ( self , values_list ) :
        self.pkgfd.seek(0,2)
        for pkg in values_list :
            self.append( pkg )

class DebianDownloadList ( _DebianPackageList , AbstractDownloadList ) :

    def __init__ ( self , repo ) :
        _DebianPackageList.__init__( self )
        AbstractDownloadList.__init__( self , repo )

    def __iter__ ( self ) :
        if self.started :
            raise Exception( "Trying to iterate over a running list" )
        return _DebianPackageList.__iter__( self )

    def push ( self , pkg ) :
        if self.closed :
            raise Exception( "Trying to push into a closed queue" )
        _DebianPackageList.append( self , pkg )

class DebianDownloadThread ( _DebianPackageList , AbstractDownloadThread ) :
 
    def __init__ ( self , repo=None ) :
        AbstractDownloadThread.__init__( self , repo )
        _DebianPackageList.__init__( self )

    def __iter__ ( self ) :
        if self.started :
            raise Exception( "Trying to iterate over a running list" )
        return _DebianPackageList.__iter__( self )


