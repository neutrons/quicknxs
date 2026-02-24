#!/bin/bash
SESSION_DIR=${1:-output_dir}
QUICKNXS_DIR=${QUICKNXS_DIR:-/usr/local/pixi/quicknxs}
PNG1=$(ls ${SESSION_DIR}/*.png | head -1)
DAT1=$(ls ${SESSION_DIR}/*.dat | head -1)

if [ ! -z "${PNG1}" ] ; then
	xdg-open ${PNG1} &
fi
if [ ! -z "${DAT1}" ] ; then
	tmpd=$(mktemp -d)
	for f in $(ls ${SESSION_DIR}/*.dat) ; do
		echo $f
		( cd ${QUICKNXS_DIR} ; pixi run python test/show.py $f 2>&1 > ${tmpd}/$(basename $f) & )
	done
fi
