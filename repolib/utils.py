
__all__ = [ 'with_gpg' , 'gpg_verify' ,
            'integrity_check' , 'cksum_handles' , 'SKIP_NONE' , 'SKIP_SIZE' , 'SKIP_CKSUM' , 'SKIP_ALL' ,
            'urljoin' , 'unsplit' , 'download_head' , 'download' ]

from repolib import logger

try :
    import GnuPGInterface
    with_gpg = True
except :
    with_gpg = False

import os

import tempfile


import urllib2

urljoin = urllib2.urlparse.urljoin

def unsplit ( scheme , server , path ) :
    urltuple = ( scheme , server , path , None , None )
    return urllib2.urlparse.urlunsplit( urltuple )

# Thanks to http://stackoverflow.com/questions/107405/how-do-you-send-a-head-http-request-in-python/2070916#2070916
class download_head ( urllib2.Request ) :
    def get_method(self):
        return "HEAD"

def download ( remote , handle=None , request=None ) :
    response = False
    try:
        response = urllib2.urlopen( remote )

        if handle :
            while True:
                buffer = response.read(512)
                if not buffer:
                    break
                os.write(handle,buffer)
                if request : request.write(buffer)
            os.close(handle)

    except Exception , ex :
        if request :
            request.log_error( "Exception : %s" % ex )
        else :
            logger.error( "Exception : %s" % ex )

    if response :
        response.close()

    return response


SKIP_NONE = 0
SKIP_SIZE = 1
SKIP_CKSUM = 2
SKIP_ALL = SKIP_SIZE | SKIP_CKSUM

def integrity_check ( filename , item , skip_check=SKIP_NONE , bsize=128 ) :
    """Checks integrity of the given file with values supplied on a dictionary.
Will return False on failure of any check, and True if no verification fails.
If all checks are skipped or no checksum can be verified, string "OK" is
returned, which still evaluates to boolean true, but serves to detect partial
verification if required."""

    keysout = ( "name" , "href" , "filename" , "arch" , "size" ,
                "group" , "provides" , "requires" )

    checksums = filter( lambda x : x not in keysout ,
                        map( lambda x : x.lower() , item.keys() )
                        )

    name = os.path.basename(filename)

    if skip_check == SKIP_ALL :
        logger.warning( "No check selected for '%s'" % name )
        return "OK"

    res = True

    if not ( skip_check & SKIP_SIZE ) :
        if os.stat( filename ).st_size != int( item['size'] ) :
            logger.warning( "Bad size on file '%s'" % name )
            return False

    # Policy is to verify all the available checksums
    if not ( skip_check & SKIP_CKSUM ) :
        res = "OK"
        for cktype in cksum_handles.keys() :
            if item.has_key( cktype ) :
                if cksum_handles[cktype]( filename , bsize ) == item[cktype] :
                    res = True
                else :
                    logger.warning( "Bad %s checksum '%s'" % ( cktype , name ) )
                    return False

        if res == "OK" :
          if not checksums :
            logger.warning( "No checksum defined for %s" % name )
          else :
            logger.warning( "Unknown checksum types available for %s : %s" % ( name , checksums ) )

    return res

import hashlib

def calc_md5(filename, bsize=128):
    f = open( filename , 'rb' )
    _md5 = hashlib.md5()
    data = f.read(bsize)
    while data :
        _md5.update(data)
        data = f.read(bsize)
    f.close()
    return _md5.hexdigest()

def calc_sha1(filename, bsize=128):
    f = open( filename , 'rb' )
    _sha = hashlib.sha1()
    data = f.read(bsize)
    while data :
        _sha.update(data)
        data = f.read(bsize)
    f.close()
    return _sha.hexdigest()

def calc_sha256(filename, bsize=128):
    f = open( filename , 'rb' )
    _sha256 = hashlib.sha256()
    data = f.read(bsize)
    while data :
        _sha256.update(data)
        data = f.read(bsize)
    f.close()
    return _sha256.hexdigest()

cksum_handles = { 'md5sum':calc_md5 , 'sha1':calc_sha1 , 'sha256':calc_sha256 }


# NOTE : full_verification is never used. What was the purpose ??
def gpg_verify( signature , file , reporter=None , full_verification=False ) :
    """Function to verify a file signature.
If a reporter callback is supplied, it is used to send back any relevant
output messages in case of error. If the signature was made with multiple
keys, success in a single verification is reported as global success unless
full verification is requested, which means that every single signature
must be sucessfully verified"""

    if full_verification :
        err = gpg_error( signature , file )
        if not err :
            return True
        if reporter : reporter( err )
        return False

    (sigfd, signature_file ) = tempfile.mkstemp()
    fd = open( signature )
    line = fd.readline()
    while line :
        os.write( sigfd , line )
        if line[:-1] == "-----END PGP SIGNATURE-----" :
            os.close( sigfd )
            if not gpg_error( signature_file , file ) :
                fd.close()
                os.unlink( signature_file )
                return True
            sigfd = os.open( signature_file , os.O_WRONLY | os.O_TRUNC )
        line = fd.readline()
    else :
        os.close( sigfd )
    fd.close()
    if reporter : reporter( "All signatures failed" )
    os.unlink( signature_file )
    return False

def gpg_error( signature , file ) :
    """This function returns the error occurred during GPG verification. In case of
success, it returns False. The reason behind this reversed logic is to make
easy reporting back a descriptive string for the error"""

    gpgerror = "Not verified"
    try :
        result = GnuPGInterface.GnuPG().run( [ "--verify", signature , file ] , create_fhs=['stdin', 'stdout', 'logger'])
        result.wait()
        gpgerror = False
    except IOError , ex :
        gpgerror = "Bad signatute : %s" % ex
    return gpgerror


