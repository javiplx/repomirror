
import debian_bundle.debfile

import os


from repolib import abstract_build_repository


class feed_build_repository ( abstract_build_repository ) :

    def __init__ ( self , config ) :

        abstract_build_repository.__init__( self , config )

        self.components = config.get( "components" , None )

    def build ( self ) :

        packages = open( os.path.join( self.destdir , "Packages" ) , 'w' )

        for filename in filter( lambda x : x.endswith( ".opk" ) , os.listdir( self.destdir ) ) :
            pkg = debian_bundle.debfile.DebFile( os.path.join( self.destdir , filename ) )
            control = pkg.control.debcontrol()
            if not control.has_key("Filename") :
                control["Filename"] = filename
            packages.write( "%s\n" % control )

        packages.close()


