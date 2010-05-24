
import xml.sax
import xml.dom.pulldom
import repoutils

class yum_packages_handler ( xml.sax.handler.ContentHandler ) :

    def __init__ ( self ) :
        self.pkgs = []
        self._key = None
        self._list = None
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
        elif name == 'poolfile':     
          self._pkg[ 'Filename' ] = str( attrs.get('href',"") )
        elif name == 'checksum':     
          self._key = str( attrs.get('type',"") )
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
              self._pkg[ self._list ].append( attrs.get('name',""))
        else :
          self._dict = None
          self._key = None

    def characters ( self , ch ) :
        if self._key :
          self._pkg[ self._key ] = str( ch )
          self._key = None

    def endElement ( self , name ) :
        if name == 'package':
          self.pkgs.append( self._pkg )
          self._pkg = None
        elif name == self._ns + 'provides':     
          self._list = None
        elif name == self._ns + 'requires':     
          self._list = None
        elif name == 'format':     
          self._ns = ""


class yum_files_handler ( xml.sax.handler.ContentHandler ) :

    def __init__ ( self ) :
        self.files = {}
        self._pkg = None
        self._key = False

    def startElement ( self , name , attrs ) :

        if name == 'package':     
            self._pkg = attrs.get('name')
        elif name == 'file' :     
             # We only care about files, neither dirs nor ghosts
             if attrs.get('type', "file") == "file" :
                 self._key = True

    def characters ( self , ch ) :
        if self._key :
            # FIXME : There are some issue that makes ch not arriving a proper node content, causing false duplicates on incomplete path names
            #if self.files.has_key( ch ) :
            #    print "Duplicated filename : %s" % ch
            self.files[ ch ] = self._pkg

    def endElement ( self , name ) :
        if name == 'package':
            self._pkg = None
        elif name == 'file' :     
            self._key = False


def get_package_list ( fd ) :

    pkg_handler = yum_packages_handler()

    parser = xml.sax.make_parser()   
    parser.setContentHandler( pkg_handler )

    parser.parse( fd )

    return pkg_handler.pkgs

def get_files_list ( fd ) :

    files_handler = yum_files_handler()

    parser = xml.sax.make_parser()   
    parser.setContentHandler( files_handler )

    parser.parse( fd )

    return files_handler.files

def get_filelist ( metafile ) :

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
                if not _item[_name].has_key( "href" ) :
                    repoutils.show_error( "No location element within repomd '%s' entry"  % _name )
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

