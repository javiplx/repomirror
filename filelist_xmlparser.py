
import xml.sax
import xml.dom.minidom

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

    repodoc = xml.dom.minidom.parse( metafile )
    doc = repodoc.documentElement

    primary_item , filelist_item = None , None

    for node in doc.getElementsByTagName( "data" ) :
        if node.getAttribute( "type" ) == "primary" :
            location = node.getElementsByTagName( "location" )
            if not location :
                repoutils.show_error( "No location element within repomd file" )
                continue
            primary_item = { 'href':location[0].getAttribute( "href" ) }
            # FIXME : Produce an error if multiple locations ?
            size = node.getElementsByTagName( "size" )
            if size :
                primary_item['size'] = int(size[0].firstChild.nodeValue)
            for _node in node.getElementsByTagName( "checksum" ) :
                primary_item[ _node.getAttribute( "type" ) ] = _node.firstChild.nodeValue
        elif node.getAttribute( "type" ) == "filelists" :
            location = node.getElementsByTagName( "location" )
            if not location :
                repoutils.show_error( "No location element within repomd file" )
                continue
            filelist_item = { 'href':location[0].getAttribute( "href" ) }
            # FIXME : Produce an error if multiple locations ?
            size = node.getElementsByTagName( "size" )
            if size :
                filelist_item['size'] = int(size[0].firstChild.nodeValue)
            for _node in node.getElementsByTagName( "checksum" ) :
                filelist_item[ _node.getAttribute( "type" ) ] = _node.firstChild.nodeValue

    return primary_item , filelist_item

