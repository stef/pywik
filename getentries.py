#!/usr/bin/env python
# -*- coding: utf-8 -*-

# todo, enable and handle: $http_HEADER, $cookie_COOKIE in nginx logformat def

import csv, sys, os, datetime, re
from urllib2 import unquote
from dateutil.parser import parse
from pbs import host, ErrorReturnCode_1
from urlparse import urlparse, parse_qs
from operator import itemgetter
import GeoIP

geoipdb=None
torexits=None
agents=None
countries=None
ignorepaths=None
goodpaths=None
ignoremissing=None
ipcache={}
ownhosts=[]

basepath=os.path.dirname(os.path.abspath(__file__))
blocks = u' ▁▂▃▄▅▆▇██'

def init():
    global geoipdb, torexits, agents, countries, ignorepaths, goodpaths, ignoremissing, ownhosts
    # Load the database once and store it globally in interpreter memory.
    geoipdb = GeoIP.open('%s/data/GeoIP.dat' % basepath,GeoIP.GEOIP_STANDARD)

    fp=open('%s/data/torexits.csv' % basepath,'r')
    torexits=[x.strip() for x in fp]
    fp.close()

    fp=open('%s/data/agents.csv' % basepath,'r')
    agents={}
    for line in fp:
        line=' '.join(line.split())
        if not line: continue
        type,text=line.split(',',1)
        agents[text]=type.split()
    fp.close()

    countries=init_countrymap()

    fp=open('%s/data/%s/ignorepaths' % (basepath, sys.argv[1]),'r')
    ignorepaths=[re.compile(x.strip()) for x in fp]
    fp.close()

    fp=open('%s/data/%s/ignoremissing' % (basepath, sys.argv[1]),'r')
    ignoremissing=[re.compile(x.strip()) for x in fp]
    fp.close()

    fp=open('%s/data/%s/goodpaths' % (basepath, sys.argv[1]),'r')
    goodpaths=[re.compile(r"%s" % x.strip()) for x in fp]
    fp.close()

    fp=open('%s/data/%s/ownhosts' % (basepath, sys.argv[1]),'r')
    ownhosts=[re.compile("%s://%s/" % (scheme, host.strip())) for host in fp for scheme in ['http','https']]
    fp.close()

def UnicodeDictReader(utf8_data, **kwargs):
    csv_reader = csv.DictReader(utf8_data, **kwargs)
    for row in csv_reader:
        yield dict([(key, unicode(value or "", "utf8")) for key, value in row.iteritems()])

def init_countrymap():
    csvfile = open('%s/data/countrylist.csv' % basepath,'r')
    dialect = csv.Sniffer().sniff(csvfile.read(32768))
    csvfile.seek(0)
    headers = csv.reader(csvfile, dialect=dialect).next()
    reader = UnicodeDictReader(csvfile,
                               fieldnames=headers,
                               dialect=dialect)
    countrymap={}
    for line in reader:
        countrymap[line['ISO 3166-1 2 Letter Code']]=line
    csvfile.close()
    return countrymap

def uunquote(txt):
    try:
        return unquote(txt.encode('ascii')).decode('utf8')
    except:
        return unquote(txt)

# explode the request field into request_type, path and protocol
def explodereq(req):
    tmp=req.split()
    if len(tmp)<3:
        tmp.extend([''] * (3-len(tmp)))
    path=uunquote(' '.join(tmp[1:-1]))
    return [tmp[0], path, tmp[-1]]

def todate(s):
    date, time = s.split(':',1)
    try:
        tmp=parse("%s %s" % (date.replace('/','-'), time), dayfirst=True)
    except:
        tmp=parse(s)
    return tmp

def textfilterre(text, patterns=[], exclude=True):
    if type(text)!=unicode: return text
    for mask in patterns:
        if mask.match(text):
            return exclude
    return not exclude

def gethost(ip):
    if ip in ipcache: return ipcache[ip]
    try:
        ipcache[ip]=host(ip).split(' ')[-1][:-2]
        return ipcache[ip]
    except ErrorReturnCode_1:
        ipcache[ip]=''
        return ''

def get_query(url):
    url=str(url)
    urlobj=urlparse(url)
    query=parse_qs(urlobj.query)
    if (urlobj.netloc.startswith('www.google.') or
        (urlobj.netloc.endswith("bing.com") and urlobj.path.startswith('/search'))):
        return query.get('q',[''])[0].decode('utf8')
    return ''

def get_country(ip):
    return geoipdb.country_code_by_addr(ip) or ''

def count(d, e, l):
    cnt, elems=d.get(e,[0,[]])
    elems.append(l)
    d[e]=[cnt+1,elems]

headers = ["time_local","connection","remote_addr","https","http_host",
           "request","status","request_length","body_bytes_sent","request_time",
           "http_referer","remote_user","http_user_agent","http_x_forwarded_for","msec",
           "request_type", "path", "http_version", "ispage", "isbot",
           "hostname", "extref","search_query","country","year","month","day", "viator"]

init()

csv.register_dialect('nginx',
                     **{'lineterminator': '\r\n',
                        'skipinitialspace': False,
                        'quoting': 0,
                        'delimiter': ';',
                        'quotechar': '"',
                        'doublequote': False})
reader = UnicodeDictReader(sys.stdin, fieldnames=headers, dialect='nginx')
reader.next()

for line in reader:
    # request_type, path, http_version
    (line['request_type'],
     line['path'],
     line['http_version'])=explodereq(line['request'])

    date=todate(line['time_local'])

    if not sys.argv[3] in line[sys.argv[2]]:
        continue

    if line['remote_addr'] in torexits:
        line['viator']=True

    # extract query strings if any
    line['search_query']=get_query(line['http_referer'])

    # Referer
    # unquote http_referer
    tmp=unquote(line['http_referer'])
    # simplify referers
    urlobj=urlparse(tmp)
    if (tmp.startswith('http://www.facebook.com/l.php?u=') or
        tmp.startswith('http://m.facebook.com/l.php?u=')):
        line['http_referer']='http://www.facebook.com/'
    elif urlobj.netloc.startswith('www.google.') and urlobj.path=="/imgres":
        query=parse_qs(urlobj.query)
        line['image']=query.get('imgurl',[''])[0]
        line['imageref']=query.get('imgrefurl',[''])[0]
        line['http_referer']='%s://%s/imgres?imgurl=%s' % (urlobj.scheme,
                                                           urlobj.netloc,
                                                           line['image'])
    elif urlobj.netloc.startswith('www.google.') and urlobj.path=="/url":
        query=parse_qs(urlobj.query)
        line['http_referer']='%s://%s/url=%s' % (urlobj.scheme,
                                                 urlobj.netloc,
                                                 uunquote(query.get('url',[''])[0]))
    elif urlobj.netloc.startswith('webcache.googleusercontent.') and urlobj.path=="/search":
        query=parse_qs(urlobj.query)
        try:
            u=uunquote(query.get('q',[':'])[0]).split(':',1)[1].decode('utf8')
        except:
            u=uunquote(query.get('q',[':'])[0]).split(':',1)[1]
        line['http_referer']='%s://%s/url=%s' % (urlobj.scheme,
                                                 urlobj.netloc,
                                                 u)
    else:
        line['http_referer']=tmp
    # extref?
    line['extref']=not textfilterre(line['http_referer'],
                                    patterns=ownhosts)

    # is page?
    line['ispage']=textfilterre(line['path'], patterns=goodpaths)

    # append Country
    if not line['country']: line['country']=get_country(line['remote_addr'])

    # isbot?
    # B = Browser
    # C = Link-, bookmark-, server- checking
    # D = Downloading tool
    # P = Proxy server, web filtering
    # R = Robot, crawler, spider
    # S = Spam or bad bot
    line['agent']=agents.get(line['http_user_agent'],['?'])

    line['msec']=float(line['msec'])
    line['request_time']=float(line['request_time'])
    line['connection']=int(line['connection'])
    line['body_bytes_sent']=int(line['body_bytes_sent'])
    line['request_length']=int(line['request_length'])
    line['year']=date.year
    line['month']=date.month
    line['day']=date.day
    line['https']=True if line['https']=='1' else False
    line['status']=int(line['status'])

    # domain name
    line['hostname']=gethost(line['remote_addr'])

    print "%s  %s\t%s" % (countries[line['country']]['Common Name'], line['remote_addr'], line['hostname'])
    print date
    print line['http_user_agent'].encode('utf8')
    if line.get('search_query'):
        print line['search_query'].encode('utf8')
    print line['http_referer'].encode('utf8')
    print line['path'].encode('utf8')
    print

