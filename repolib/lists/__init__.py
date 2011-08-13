
__all__ = [ "PackageList" , "DownloadList" , "DownloadThread" ]

import os

from repolib import logger
import repolib.utils


class AbstractMethodException ( Exception ) :

    def __init__ ( self , source , method ) :
        Exception.__init__( self , "Calling abstract %s.%s" % ( source.__class__.__name__ , method ) )


class PackageListInterface :
    """This Interface is just a partial defintion of a list. It is included
as root for inheritance tree"""

    weight = 0

    def __repr__ ( self ) :
        return "<%s pkgs:%d %d Mb>" % ( self.__class__.__name__ , len(self) , self.weight/1024/1024 )

    def append ( self , item ) :
        raise AbstractMethodException( self , "append" )

    def extend ( self , itemlist ) :
        raise Exception( "Calling %s.extend on %s" % self.__class__.__name__ )

    def __iter__ ( self ) :
        raise AbstractMethodException( self , "__iter__" )

class PackageList ( PackageListInterface , list ) :
    __iter__ = list.__iter__

    def append ( self , item ) :
        self.weight += int( item['size'] )
        list.append( self , item )


class DownloadInterface ( PackageListInterface ) :
    """Interface for download lists.
Primary difference is the behaviour respect to iterations, that cannot be
started at any time and whose finalization is not controlled by standard
list exhaustion. Also deviates from standard list in boolean evaluations.
Mainly useful in multi-threading contexts."""

    def __init__ ( self , repo ) :
        self.repo = repo
        self.started = False
        self.closed = False
        self.index = 0

    def __repr__ ( self ) :
        return "<%s pkgs:%d/%d %d Mb>" % ( self.__class__.__name__ , self.index , len(self) , self.weight/1024/1024 )

    def start ( self ) :
        """Method to signal when the object becomes a non iterable one, in the sense that iteration cannot be started.
It requires an explicit check on iterator/generator instantiation"""
        raise AbstractMethodException( self , "start" )

    def finish ( self ) :
        """Method to signals when the list becomes a non extendable one, in the sense that no newcomers are allowed.
It requires an explicit check on append/extend methods"""
        raise AbstractMethodException( self , "finish" )

    # This is a final method
    def queue ( self , itemlist ) :
        for item in itemlist :
            self.push( item )

    def push ( self , item ) :
        raise AbstractMethodException( self , "push" )

    def __nonzero__ ( self ) :
        """Method to evaluate in boolean context the existence of available items.
Used in while loop context to enable element extraction"""
        raise AbstractMethodException( self , "__nonzero__" )

    # This is a redefinition of PackageListInterface, to stress requirement of specific implemenation
    def __iter__ ( self ) :
        raise AbstractMethodException( self , "__iter__" )

    def join ( self ) :
        """Wait until the queue gets cleared"""
        raise AbstractMethodException( self , "join" )

    # This is a final method
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

    def join ( self ) :
        pass

# FIXME : DownloadList is usable, but has some reporting issues under iterations
class DownloadList ( AbstractDownloadList , list ) :

    def __init__ ( self , repo ) :
        AbstractDownloadList.__init__( self , repo )
        list.__init__( self )

    def __nonzero__ ( self ) :
        return not bool(list(self))

    def push ( self , item ) :
        if self.closed :
            raise Exception( "Trying to push into a closed queue" )
        self.append( item )

    def append ( self , item ) :
        self.weight += int( item['size'] )
        list.append( self , item )

    def __iter__ ( self ) :
        if self.started :
            raise Exception( "Trying to iterate over a running list" )
        return list.__iter__( self )


import threading

class AbstractDownloadThread ( DownloadInterface , threading.Thread ) :
    start = threading.Thread.start
    join = threading.Thread.join

    def __init__ ( self , repo ) :
        # Check for methods required on the underlying container
        if not 'append' in dir(self) or not '__len__' in dir(self) :
            raise Exception ("Implementation of AbstractDownloadThread required sized objects with append method")
        self.cond = threading.Condition()
        DownloadInterface.__init__( self , repo )
        threading.Thread.__init__( self , name=repo.name )

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

class DownloadThread ( AbstractDownloadThread , list ) :
    """File download thread. It is build around a threaded list where files
are appended. Once the thread starts, the actual file download begins"""

    def __hash__ ( self ) :
        return AbstractDownloadThread.__hash__( self )

    def __init__ ( self , repo ) :
        AbstractDownloadThread.__init__( self , repo )
        list.__init__( self )

    def __iter__ ( self ) :
        if self.started :
            raise Exception( "Trying to iterate over a running list" )
        return list.__iter__( self )

    def append ( self , item ) :
        self.weight += int( item['size'] )
        list.append( self , item )

