#!/usr/bin/ksh

rsync -vzcaE -e ssh "$1":/var/log/nginx/*.csv logs
