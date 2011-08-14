
__all__ = [ "xml_filelist" , "xml_package_list" , "xml_files_list" ]

import xml.sax
import xml.dom.pulldom

class xml_handler ( xml.dom.pulldom.DOMEventStream , xml.sax.handler.ContentHandler ) :

    def __init__ ( self , stream , parser ) :
        xml.dom.pulldom.DOMEventStream.__init__( self , stream , parser , parser._bufsize )
        self._pkg = {}
        
    def erase ( self , node , attrs ) :
        self._pkg.clear()

    def expandNode ( self , node ) :
        event = self.getEvent()
        while event:
            token, cur_node = event
            if cur_node is node:
                return
            if token == xml.dom.pulldom.START_ELEMENT:
                self.startElement( cur_node.tagName , cur_node._get_attributes() )
            elif token == xml.dom.pulldom.END_ELEMENT:
                self.endElement( cur_node.tagName )
            elif token == xml.dom.pulldom.CHARACTERS:
                self.characters( cur_node.nodeValue )
            event = self.getEvent()

    def next ( self ) :
        event,node = xml.dom.pulldom.DOMEventStream.next( self )
        # NOTE : searching for 'package' as tagName is ok for primary and filelists, but maybe not for others
        if not event == "START_ELEMENT" or not node.tagName == "package" :
            return self.next()
        self.erase( node , node._get_attributes() )
        self.expandNode( node )
        return self._pkg


class yum_packages_handler ( xml_handler ) :

    def __init__ ( self , stream , parser ) :
        xml_handler.__init__( self , stream , parser )
        self._key = None
        self._list = None
        self._ns = ""

    def startElement ( self , name , attrs ) :

        if name == 'name' :     
             self._key = str(name)
        elif name == 'arch' :     
             self._key = str(name)
        elif name == 'size':     
          self._pkg['size'] = 0
          if attrs.has_key('package') :
              self._pkg['size'] = int( attrs['package'].nodeValue )
        elif name == 'location':     
          self._pkg['href'] = ""
          if attrs.has_key('href') :
              self._pkg['href'] = str( attrs['href'].nodeValue )
        elif name == 'poolfile':     
          self._pkg['Filename'] = ""
          if attrs.has_key('href') :
              self._pkg['Filename'] = str( attrs['href'].nodeValue )
        elif name == 'checksum':     
          self.key = ""
          if attrs.has_key('type') :
              self._key = str( attrs['type'].nodeValue )
        elif name == 'format':     
          self._ns = "rpm:"
        elif name == self._ns + 'group':     
          self._key = 'group'
        elif name == self._ns + 'provides':     
          self._list = 'provides'
          self._pkg[ self._list ] = []
        elif name == self._ns + 'requires':     
          self._list = 'requires'
          self._pkg[ self._list ] = []
        elif name == self._ns + 'entry':     
          if self._list :
              if attrs.has_key('name') :
                  self._pkg[ self._list ].append( attrs['name'].nodeValue )
              if attrs.has_key('type') :
                  self._pkg[ self._list ].append( "" )
        else :
          self._dict = None
          self._key = None

    def characters ( self , ch ) :
        if self._key :
          self._pkg[ self._key ] = str( ch )
          self._key = None

    def endElement ( self , name ) :
        if name == self._ns + 'provides':     
          self._list = None
        elif name == self._ns + 'requires':     
          self._list = None
        elif name == 'format':     
          self._ns = ""


class yum_files_handler ( xml_handler ) :                                                                                                     

    def __init__ ( self , stream , parser ) :
        xml_handler.__init__( self , stream , parser )
        self._list = None

    def erase ( self , node , attrs ) :
        xml_handler.erase( self , node , attrs )
        self._pkg['name'] = str( attrs['name'].nodeValue )

    def startElement ( self , name , attrs ) :

        if name == 'file' :     
             # We only care about files, neither dirs nor ghosts
             if attrs.get('type', "file") == "file" :
                 self._list = 'file'

    def characters ( self , ch ) :
        if self._list :
            # FIXME : There are some issue that makes ch not arriving a proper node content, causing false duplicates on incomplete path names
            if not self._pkg.has_key( self._list ) :
                self._pkg[ self._list ] = [ ch ]
            else :
                self._pkg[ self._list ].append( ch )

    def endElement ( self , name ) :
        if name == 'file' :     
            self._list = False


def xml_package_list ( fd ) :
    return yum_packages_handler( fd , xml.sax.make_parser() )

def xml_files_list ( fd ) :
    return yum_files_handler( fd , xml.sax.make_parser() )

def xml_filelist ( metafile ) :

    repodoc = xml.dom.pulldom.parse( metafile )

    _name , _item = None , {}
    _key , _content = None , None

    for event,node in repodoc :
        if event == "START_ELEMENT" :
            if node.nodeName == "data" :
                _name = node.getAttribute( "type" )
                _item[_name] = {}
            if node.nodeName == "location" :
                _item[_name]["href"] = node.getAttribute( "href" )
            if node.nodeName == "size" :
                _key = node.nodeName
            if node.nodeName == "checksum" :
                _key = node.getAttribute( "type" )
        elif event == "END_ELEMENT" :
            if node.nodeName == "data" :
                _data = None
            if node.nodeName == "size" :
                _item[_name][_key] = int(_content)
                _key , _content = None , None
            if node.nodeName == "checksum" :
                _item[_name][_key] = _content
                _key , _content = None , None
        elif event == "CHARACTERS" :
            _content = node.nodeValue

    return _item['primary'] , _item['filelists']

