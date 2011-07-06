#!/bin/sh

mkdir -p debian/dists
cd debian/dists

for suite in lenny squeeze ; do
  wget -q -r -nH --cut-dirs=3 -P ${suite} ftp://ftp.es.debian.org/debian/dists/${suite}
  done

cd ..

