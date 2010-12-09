
import os


def show_error( str , error=True ) :
    if error :
        print "ERROR : %s" % str
    else :
        print "WARNING : %s" % str


import threading

class DownloadThread ( threading.Thread ) :
    """File download thread. It is build around a threaded list where files
are appended. Once inserted, the files are downloaded by the main loop"""

    def __init__ ( self , repo ) :
        self.repo = repo
        # FIXME : Set to true when started, not during initialization
        self.running = False
        self.closed = False
        self.list=[]
        self.cond = threading.Condition()
        threading.Thread.__init__(self)

    def download_pkg ( self , pkg ) :

        destname = os.path.join( self.repo.repo_path() , pkg['Filename'] )

        # FIXME : Perform this check while appending to download_pkgs ???
        if os.path.isfile( destname ) :
            error = repolib.utils.md5_error( destname , pkg )
            if error :
                show_error( error , False )
                os.unlink( destname )
            else :
                return
        else :
            path , name = os.path.split( destname )
            if not os.path.exists( path ) :
                os.makedirs( path )

        if not self.repo.downloadRawFile ( pkg['Filename'] , destname ) :
            show_error( "Failure downloading file '%s'" % ( pkg['Filename'] ) , False )

    def start(self):
        if not self.running :                                                   
            threading.Thread.start(self)
            self.running = True

    def run(self):
        """Main thread loop. Runs over the item list, downloading every file"""

        while self.running:
            self.cond.acquire()
            pkginfo = None
            if not self.list :
                if self.closed :
                   self.running = False
                   continue
                self.cond.wait()
            if self.running and self.list :
                pkginfo = self.list.pop(0)
            self.cond.release()
            if pkginfo :
                self.download_pkg( pkginfo )

    def append ( self , item ) :
        """Adds an item to the download queue"""
        self.cond.acquire()
        # FIXME : Raise exception if not running !!!
        try:
            if not self.list :
                # FIXME : Notification takes effect now or after release ???
                self.cond.notify()
            if self.closed :
                show_error( "Trying to append file '%s' to a closed thread" % item['Filename'] , False )
            else :
                self.list.append( item.copy() )
        finally:
            self.cond.release()

    def destroy(self):
        """Ends the main loop"""
        self.cond.acquire()
        try:
            self.closed=True
            # FIXME : Notification takes effect now or after release ???
            self.cond.notify()
        finally:
            self.cond.release()

