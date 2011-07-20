
__all__ = [ "PackageList" , "DownloadThread" ]

import os

import repolib.utils


class PackageListInterface :
    """This Interface is just a partial defintion of a list. It is included
as root for inheritance tree"""

    def append ( self , item ) :
        raise Exception( "Calling abstract PackageListInterface.append on %s" % self )

    # NOTE : In a strict sense, this method is not required for list interface, and is actually not used anywhere
    def extend ( self , itemlist ) :
        raise Exception( "Calling abstract PackageListInterface.extend on %s" % self )

    def __iter__ ( self ) :
        raise Exception( "Calling abstract PackageListInterface.__iter__ on %s" % self )

class PackageList ( list , PackageListInterface ) :

    # Avoid representation of full list
    def __repr__ ( self ) :
        return "<PackageList items:%d>" % len(self)


class DownloadInterface ( PackageListInterface ) :
    """Interface for complex download lists, which increase simple list functionality
by allowing appending during iteration"""

    def __init__ ( self , repo ) :
        self.repo = repo
        self.started = False
        self.closed = False

    def start ( self ) :
        """Method to signal when the object becomes a non iterable one, in the sense that iteration cannot be started.
It requires an explicit check on iterator/generator instantiation"""
        raise Exception( "Calling abstract DownloadInterface.start on %s" % self )

    def finish ( self ) :
        """Method to signals when the list becomes a non extendable one, in the sense that no newcomers are allowed.
It requires an explicit check on append/extend methods"""
        raise Exception( "Calling abstract DownloadInterface.finish on %s" % self )

    # This is a final method
    def queue ( self , itemlist ) :
        for item in itemlist :
            self.push( item )

    def push ( self , item ) :
        raise Exception( "Calling abstract DownloadInterface.push on %s" % self )

    def __nonzero__ ( self ) :
        """Method to evaluate in boolean context the existence of available items.
Used in while loop context to enable element extraction"""
        raise Exception( "Calling abstract DownloadInterface.__nonzero_ on %s" % self )

    # This is a redefinition of PackageListInterface, to stress requirement of specific implemenation
    def __iter__ ( self ) :
        raise Exception( "Calling abstract DownloadInterface.__iter__ on %s" % self )

    def download_pkg ( self , pkg ) :

        destname = os.path.join( self.repo.repo_path() , pkg['Filename'] )

        # FIXME : Perform this check while appending to download_pkgs ???
        if os.path.isfile( destname ) :
            if repolib.utils.integrity_check( destname , pkg ) is False :
                os.unlink( destname )
            else :
                return
        else :
            path , name = os.path.split( destname )
            if not os.path.exists( path ) :
                os.makedirs( path )

        if not self.repo.downloadRawFile ( pkg['Filename'] , destname ) :
            logger.warning( "Failure downloading file '%s'" % os.path.basename(pkg['Filename']) )


class AbstractDownloadList ( DownloadInterface ) :

    def start ( self ) :

        for pkg in self :
            self.started = True
            self.download_pkg( pkg )

    def finish ( self ) :
        self.closed = True

class DownloadList ( list , AbstractDownloadList ) :

    # Avoid representation of full list
    def __repr__ ( self ) :
        return "<DownloadList items:%d>" % len(self)

    def __init__ ( self , repo ) :
        list.__init__( self )
        AbstractDownloadList.__init__( self , repo )

    def push ( self , item ) :
        if self.closed :
            raise Exception( "Trying to push into a closed queue" )
        list.append( self , item )

    def __iter__ ( self ) :
        if self.started :
            raise Exception( "Trying to iterate over a running list" )
        return list.__iter__( self )


import threading

class AbstractDownloadThread ( threading.Thread , DownloadInterface ) :

    def __init__ ( self , repo ) :
        # Check for methods required on the underlying container
        if not 'append' in dir(self) or not '__len__' in dir(self) :
            raise Exception ("Implementation of AbstractDownloadThread required sized objects with append method")
        self.cond = threading.Condition()
        threading.Thread.__init__( self , name=repo.name )
        DownloadInterface.__init__( self , repo )
        self.index = 0

    def finish(self):
        """Ends the main loop"""
        self.cond.acquire()
        try:
            self.closed=True
            # FIXME : Notification takes effect now or after release ???
            self.cond.notify()
        finally:
            self.cond.release()

    def __nonzero__ ( self ) :
        return self.index != len(self)

    def push ( self , item ) :
        """Adds an item to the download queue"""
        self.cond.acquire()
        try:
            if not self :
                # FIXME : Notification takes effect now or after release ???
                self.cond.notify()
            if self.closed :
                raise Exception( "Trying to push into a closed queue" )
            else :
                self.append( item )
        finally:
            self.cond.release()

    def run(self):
        """Main thread loop. Runs over the item list, downloading every file"""

        pkginfo = None
        __iter = self.__iter__()
        self.started = True
        while self.started:
            self.cond.acquire()
            if not self :
                if self.closed :
                   self.started = False
                   continue
                self.cond.wait()
            elif self.started :
                pkginfo = __iter.next()
            self.cond.release()
            if pkginfo :
                self.download_pkg( pkginfo )
                pkginfo = None
                self.index += 1

class DownloadThread ( list , AbstractDownloadThread ) :
    """File download thread. It is build around a threaded list where files
are appended. Once the thread starts, the actual file download begins"""

    # Avoid representation of full list
    def __repr__ ( self ) :
        return "<DownloadThread(%s) items:%d>" % ( self.getName() , len(self) )

    def __hash__ ( self ) :
        return AbstractDownloadThread.__hash__( self )

    def __init__ ( self , repo ) :
        list.__init__( self )
        AbstractDownloadThread.__init__( self , repo )

    def __iter__ ( self ) :
        if self.started :
            raise Exception( "Trying to iterate over a running list" )
        return list.__iter__( self )

