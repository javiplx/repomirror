
import xml.sax
import xml.dom.minidom

class yum_packages_handler ( xml.sax.handler.ContentHandler ) :

    def __init__ ( self ) :
        self.pkgs = []
        self._key = None
        self._pkg = None
        self._ns = ""
        
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
        elif name == 'format':     
          self._ns = "rpm:"
        elif name == self._ns + 'group':     
          self._key = 'group'
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
        elif name == 'format':     
          self._ns = ""


def get_package_list ( fd ) :

    pkg_handler = yum_packages_handler()

    parser = xml.sax.make_parser()   
    parser.setContentHandler( pkg_handler )

    parser.parse( fd )

    return pkg_handler.pkgs

def get_filelist ( metafile ) :

    repodoc = xml.dom.minidom.parse( metafile )
    doc = repodoc.documentElement

    for node in doc.getElementsByTagName( "data" ) :
        if node.getAttribute( "type" ) == "primary" :
            location = node.getElementsByTagName( "location" )
            if not location :
                repoutils.show_error( "No location element within repomd file" )
                continue
            item = { 'href':location[0].getAttribute( "href" ) }
            # FIXME : Produce an error if multiple locations ?
            size = node.getElementsByTagName( "size" )
            if size :
                item['size'] = int(size[0].firstChild.nodeValue)
            for _node in node.getElementsByTagName( "checksum" ) :
                item[ _node.getAttribute( "type" ) ] = _node.firstChild.nodeValue
            return item

    return

