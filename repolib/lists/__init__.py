
"""
Repomirror lists submodule

Defines and exports basic list structures to store package information.
There are are two types of objects, one standard package lists associated
to subrepos, and one in charge for actual package download that is used
at the repository level.

The module defines three classes, PackageList of the first kind, and two
classes of the second type: DownloadList and DownloadThread. All of them
use a real python list as backend storage.

The module also defines abstract base clases required to implement the
exported objects, that can be used to build custom lists using different
storage backends. Derived classes should use those defined here as first
base class, to enforce implementation of required methods.


PackageListInterface

Gives a python-list alike interface for package groups, accounting for the
size of the included packages. Derived classes must explictly implement
append() and __iter__() methods, while extend() not requires implementation.


DownloadListInterface

Extends PackageListInterface, attempting to become a thread-safe list. They
must implement a join() method, taken from threading objects, that is used
as an anchor to wait until the underlying list gets fully exhausted. There
are two methods controlling the list behaviour of the object, both requiring
implementation on derived classes. Once finish() is called, the underlying
list gets closed and no extra elements can be added. Calling start() method
will start the iteration over the underlying list, and disables instantiation
of further iterators from the object. These two methods are strongly related
to the join method and object instantiation respectively, but are kept as
distinct to make objects more versatile. Derived classes must also implement
a __nonzero__() method because in boolean context they cannot evaluate False
unless the list it is both empty and closed.
The class implements two final methods, standard extend() and download_pkg()
which cares about package download and verification.


AbstractDownloadThread

Is a combination of DownloadListInterface and Thread object, being the base
for thread-safe download lists. Is close to a full implementation of the
download list interface, except for the methods giving access to the underlying
list object.
Derived classes must only implement __iter__() method, and a push() method
that is used as interface to access to the actual append() method on underlying
list object. Depending on the type of the backed storage object, it could be
required to implement a __hash__() method, requires by threading module.


AbstractDownloadList

Is a partial implementation of DownloadListInterface. Implements most of the
non-list methods, and its primary purpose is to make easier the creation of
custom download lists in a non-threading way.

"""

__all__ = [ "PackageList" , "DownloadList" , "DownloadThread" ]

import os

import repolib


def safe_encode ( str ) :
    try :
        out = "%s" % str.encode('utf-8')
    except UnicodeDecodeError , ex :
        out = "%s" % str
    return out


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


class DownloadListInterface ( PackageListInterface ) :
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
    def extend ( self , itemlist ) :
        for item in itemlist :
            self.append( item )

    def __nonzero__ ( self ) :
        """Method to evaluate in boolean context the existence of available items.
Used in while loop context to enable element extraction"""
        raise AbstractMethodException( self , "__nonzero__" )

    def join ( self ) :
        """Wait until the queue gets cleared"""
        raise AbstractMethodException( self , "join" )

    # This is a final method
    def download_pkg ( self , pkg ) :

        destname = os.path.join( self.repo.repo_path() , pkg['Filename'] )

        # FIXME : Perform this check while appending to download_pkgs ???
        if os.path.isfile( destname ) :
            if repolib.integrity_check( destname , pkg , params['pkgvflags'] ) :
                return
            os.unlink( destname )
        else :
            path , name = os.path.split( destname )
            if not os.path.exists( path ) :
                os.makedirs( path )

        if not self.repo.downloadRawFile ( pkg['Filename'] , destname ) :
            repolib.logger.warning( "Failure downloading file '%s'" % os.path.basename(pkg['Filename']) )


class AbstractDownloadList ( DownloadListInterface ) :

    def start ( self ) :
        if self.started :
            raise Exception( "%s already started" % self )

    def finish ( self ) :
        for pkg in self :
            self.started = True
            self.download_pkg( pkg )
        # If list is empty, is never set
        if not self.started :
            self.started = True
        self.closed = True

    def join ( self ) :
        if not self.started :
            raise Exception( "cannot join %s before starting" % self )

# FIXME : DownloadList is usable, but has some reporting issues under iterations
class DownloadList ( AbstractDownloadList , list ) :

    def __init__ ( self , repo ) :
        AbstractDownloadList.__init__( self , repo )
        list.__init__( self )

    def __nonzero__ ( self ) :
        return not bool(list(self))

    def append ( self , item ) :
        if self.closed :
            raise Exception( "Trying to append into a closed queue" )
        self.weight += int( item['size'] )
        list.append( self , item )

    def __iter__ ( self ) :
        if self.started :
            raise Exception( "Trying to iterate over a running list" )
        return list.__iter__( self )


import threading

class AbstractDownloadThread ( DownloadListInterface , threading.Thread ) :
    start = threading.Thread.start
    join = threading.Thread.join

    def __init__ ( self , repo ) :
        # Check for methods required on the underlying container
        self.cond = threading.Condition()
        DownloadListInterface.__init__( self , repo )
        threading.Thread.__init__( self , name=repo.name )

    def finish(self):
        """Ends the main loop"""
        self.cond.acquire()
        try:
            self.closed = True
            self.cond.notify()
        finally:
            self.cond.release()

    def push ( self , item ) :
        """Real append to the underlying list object, to allow easier subclassing"""
        raise AbstractMethodException( self , "push" )

    # This is a final method
    def append ( self , item ) :
        """Adds an item to the download queue"""
        self.cond.acquire()
        try:
            if self.closed :
                raise Exception( "Trying to append to a closed queue" )
            else :
                self.weight += int( item['size'] )
                self.push( item )
                self.cond.notify()
        finally:
            self.cond.release()

    def run(self):
        """Main thread loop. Runs over the item list, downloading every file"""

        # NOTE : protect against race condition under empty lists
        self.cond.acquire()
        if len(self) == 0 :
            self.cond.wait()
        self.cond.release()
        pkginfo = None
        __iter = self.__iter__()
        self.started = True
        while self.started:
            self.cond.acquire()
            if not self :
                break
            elif self.started :
                # NOTE : protect against StopIteration on open lists
                if self.index == len(self) :
                    self.cond.wait()
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

    def __nonzero__ ( self ) :
        if not self.closed :
            return True
        return self.index != len(self)

    def push ( self , item ) :
        list.append( self , item )

