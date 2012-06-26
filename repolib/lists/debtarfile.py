
__all__ = [ "DebTarFile" ]

# DebTarFile: a Python representation for tar based packages
# Copyright (C) 2011    Javier Palacios     <javiplx@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import gzip
import tarfile

import debian.debfile

DATA_PART = './data.tar.gz'
CTRL_PART = './control.tar.gz'
INFO_PART = './debian-binary'


class DebTarFile(tarfile.TarFile):

    def __init__(self, filename=None, mode='r', compresslevel=9, fileobj=None):
        """Opens as gzip compressed tar archive"""
        if len(mode) > 1 or mode not in "rw":
            raise ValueError("mode must be 'r' or 'w'")

        if fileobj is None:
            fileobj = file(filename, mode + "b")

        tarfile.TarFile.__init__(self, filename, mode, gzip.GzipFile(filename, mode, compresslevel, fileobj))

        required_names = set([INFO_PART, CTRL_PART, DATA_PART])
        actual_names = set(self.getnames())
        if not (required_names <= actual_names):
            raise DebError(
                    "the following required .deb members are missing: " \
                            + string.join(required_names - actual_names))

        self.__parts = {}
        self.__parts[CTRL_PART] = debian.debfile.DebControl(self.extractfile(CTRL_PART))
        self.__parts[DATA_PART] = debian.debfile.DebData(self.extractfile(DATA_PART))
        self.__pkgname = None   # updated lazily by __updatePkgName

        f = self.extractfile(INFO_PART)
        self.__version = f.read().strip()
        f.close()

    version = property(lambda self: self.__version)
    data = property(lambda self: self.__parts[DATA_PART])
    control = property(lambda self: self.__parts[CTRL_PART])

    def __updatePkgName(self):
        self.__pkgname = self.debcontrol()['package']

    # proxy methods for the appropriate parts

    def debcontrol(self):
        """ See .control.debcontrol() """
        return self.control.debcontrol()

    def scripts(self):
        """ See .control.scripts() """
        return self.control.scripts()

    def md5sums(self):
        """ See .control.md5sums() """
        return self.control.md5sums()

    def changelog(self):
        """ Return a Changelog object for the changelog.Debian.gz of the
        present .deb package. Return None if no changelog can be found. """

        if self.__pkgname is None:
            self.__updatePkgName()

        for fname in [ CHANGELOG_DEBIAN % self.__pkgname,
                CHANGELOG_NATIVE % self.__pkgname ]:
            if self.data.has_file(fname):
                gz = gzip.GzipFile(fileobj=self.data.get_file(fname))
                raw_changelog = gz.read()
                gz.close()
                return Changelog(raw_changelog)
        return None


if __name__ == '__main__':
    import sys
    deb = DebTarFile(filename=sys.argv[1])
    tgz = deb.control.tgz()
    print tgz.getmember('./control')

