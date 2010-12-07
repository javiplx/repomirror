
import debian_bundle.debfile

import os


from repolib import abstract_build_repository


class feed_build_repository ( abstract_build_repository ) :

    def __init__ ( self , config , name , extensions=( ".opk" , ".ipk" ) ) :

        abstract_build_repository.__init__( self , config )

        self.name = name
        self.detached = config['detached']
        self.valid_extensions = extensions

	if not os.path.isdir( self.repo_path() ) :
            raise Exception( "Repository directory %s does not exists" % self.repo_path() )

        self.components = config.get( "components" , None )

    def repo_path ( self ) :
        if self.detached :
            return self.destdir
        return os.path.join( self.destdir , self.name )

    def build ( self ) :

        packages = open( os.path.join( self.repo_path() , "Packages" ) , 'w' )

        for filename in filter( lambda x : os.path.splitext(x)[1] in self.valid_extensions , os.listdir( self.repo_path() ) ) :
            pkg = debian_bundle.debfile.DebFile( os.path.join( self.repo_path() , filename ) )
            control = pkg.control.debcontrol()
            if not control.has_key("Filename") :
                control["Filename"] = filename
            if not control.has_key("Size") :
                control["Size"] = "%s" % os.stat( os.path.join( self.repo_path() , filename ) ).st_size
            packages.write( "%s\n" % control )

        packages.close()


