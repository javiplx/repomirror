
from repolib import logger

try :
    import GnuPGInterface
except :
    pass

import os

import tempfile


import urllib2

urljoin = urllib2.urlparse.urljoin

def unsplit ( scheme , server , path ) :
    urltuple = ( scheme , server , path , None , None )
    return urllib2.urlparse.urlunsplit( urltuple )


SKIP_NONE = 0
SKIP_SIZE = 1
SKIP_CKSUM = 2

def integrity_check ( filename , item , skip_check=0 , bsize=128 ) :
    """Checks integrity of the given file with values supplied on a dictionary, skipping some if requested.
Returns true for successfull checks, and false when some check fails. If no checksums were actually performed, returns None.

NOTE : None could be returned if size is verified but no known checksum type exists. This counter-intuitive result can
be avoided specifying SKIP_CKSUM for those cases where the absence of valid checksums is known in advance, but cannot be
globally fixed.
"""

    checksums = map( lambda x : x.lower() , item.keys() )

    # Remove file name, unrelated to checksum types
    name = False
    for key in ( "href" , "name" ) : # What about removing also filename ?
                                     # and others as in
# WARNING : Unknonw checksum types available for file : ['sha256', 'filename', 'name']
        if item.has_key( key ) :
            name = item[key]
            checksums.remove( key )
            break
    else :
        name = os.path.basename(filename)

    if skip_check == ( SKIP_SIZE | SKIP_CKSUM ) :
        logger.warning( "No check selected for '%s'" % name )
        # FIXME : This return should n't be required if setting res=None in advance
        return None

    if not ( skip_check & SKIP_SIZE ) :
        if os.stat( filename ).st_size != int( item['size'] ) :
            logger.warning( "Bad size on file '%s'" % name )
            return False
        res = True
        checksums.remove( "size" )

    # Policy is to verify all the available checksums
    if not ( skip_check & SKIP_CKSUM ) :
        res = None
        for type in cksum_handles.keys() :
            if item.has_key( type ) :
                if cksum_handles[type]( filename , bsize ) == item[type] :
                    res = True
                else :
                    logger.warning( "Bad %s checksum '%s'" % ( type , name ) )
                    return False

        if res is None :
            logger.warning( "Unknonw checksum types available for file : %s" % checksums )

    return res

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


