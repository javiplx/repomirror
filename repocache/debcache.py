
# Copyright (C) 2011 Javier Palacios
# 
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License Version 2
# as published by the Free Software Foundation.
# 
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.


from cache import *

import urllib2


def handler ( req ) :

    local_path = req.filename
    subpath = local_path.replace( req.hlist.directory , "" , 1 )
    remote_url = req.get_options().get('source_url')
    if not remote_url.endswith('/') :
        remote_url += "/"
        req.log_error( "Fix configuration, source_url should have a trailing '/'" , apache.APLOG_INFO )

    if req.used_path_info :
        local_path += req.path_info
        remote_url = urllib2.urlparse.urljoin( remote_url , subpath + req.path_info )

    return get_file( req , local_path , remote_url )

