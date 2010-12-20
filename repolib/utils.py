
import os

import tempfile


SKIP_NONE = 0
SKIP_SIZE = 1
SKIP_CKSUM = 2

def md5_error ( filename , item , skip_check = 0 , bsize=128 ) :
    if skip_check == ( SKIP_SIZE | SKIP_CKSUM ) :
        return "No check selected for '%s'" % filename
        return None

    if not ( skip_check & SKIP_SIZE ) :
        if os.stat( filename ).st_size != int( item['size'] ) :
            return "Bad file size '%s'" % filename

    # Policy is to verify all the checksums
    if not ( skip_check & SKIP_CKSUM ) :
        for type in cksum_handles.keys() :
            if item.has_key( type ) :
                if cksum_handles[type]( filename , bsize ) != item[type] :
                    return "Bad %s checksum '%s'" % ( type , filename )

    return None

def calc_md5(filename, bsize=128):
    f = open( filename , 'rb' )
    _md5 = md5.md5()
    data = f.read(bsize)
    while data :
        _md5.update(data)
        data = f.read(bsize)
    f.close()
    return _md5.hexdigest()

def calc_sha(filename, bsize=128):
    f = open( filename , 'rb' )
    _sha = sha.sha()
    data = f.read(bsize)
    while data :
        _sha.update(data)
        data = f.read(bsize)
    f.close()
    return _sha.hexdigest()

import md5 , sha

cksum_handles = { 'md5sum':calc_md5 , 'sha1':calc_sha , 'sha':calc_sha }


def gpg_error( signature , file , full_verification=False ) :

    if full_verification :
        return _gpg_error( signature , file )

    (sigfd, signature_file ) = tempfile.mkstemp()
    fd = open( signature )
    line = fd.readline()
    while line :
        os.write( sigfd , line )
        if line[:-1] == "-----END PGP SIGNATURE-----" :
            os.close( sigfd )
            if not _gpg_error( signature_file , file ) :
                fd.close()
                os.unlink( signature_file )
                return False
            sigfd = os.open( signature_file , os.O_WRONLY | os.O_TRUNC )
        line = fd.readline()
    else :
        os.close( sigfd )
    fd.close()
    os.unlink( signature_file )
    return "All signatures failed"

def _gpg_error( signature , file ) :
    gpgerror = "Not verified"
    try :
        result = GnuPGInterface.GnuPG().run( [ "--verify", signature , file ] )
        result.wait()
        gpgerror = False
    except IOError , ex :
        gpgerror = "Bad signatute : %s" % ex
    return gpgerror


def show_error( str , error=True ) :
    if error :
        print "ERROR : %s" % str
    else :
        print "WARNING : %s" % str


