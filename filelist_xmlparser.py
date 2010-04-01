
import xml.sax

class yum_packages_handler ( xml.sax.handler.ContentHandler ) :

    def __init__ ( self ) :
        self.pkgs = []
        self._key = None
        self._pkg = None
        
    def startElement ( self , name , attrs ) :

        if name == 'package':     
          if attrs.get('type', False) :
             self._pkg = {}
        elif name == 'name' :     
             self._key = str(name)
        elif name == 'arch' :     
             self._key = str(name)
        elif name == 'size':     
          self._pkg[ 'size' ] = int( attrs.get('package',"0") )
        elif name == 'location':     
          self._pkg[ 'href' ] = str( attrs.get('href',"") )
        elif name == 'checksum':     
          self._key = str( attrs.get('sha256',"") )
        else :
          self._key = None

    def characters ( self , ch ) :
        if self._key :
          self._pkg[ self._key ] = str( ch )
          self._key = None

    def endElement ( self , name ) :
        if name == 'package':
          self.pkgs.append( self._pkg )
          self._pkg = None


def get_package_list ( fd ) :

    pkg_handler = yum_packages_handler()

    parser = xml.sax.make_parser()   
    parser.setContentHandler( pkg_handler )

    parser.parse( fd )

    return pkg_handler.pkgs

