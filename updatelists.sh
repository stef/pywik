#!/bin/sh
mkdir -p data
curl 'http://torstatus.blutmagie.de/ip_list_exit.php/Tor_ip_list_EXIT.csv' -o data/torexits.csv
#curl 'http://www.user-agents.org/allagents.xml' | xmlstarlet sel -t -m '//user-agent' -v 'Type' -o ',' -v 'String' -n >data/agents.csv
curl 'http://geolite.maxmind.com/download/geoip/database/GeoLiteCountry/GeoIP.dat.gz' | gzip -dc >data/GeoIP.dat
