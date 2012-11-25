#!/usr/bin/env python
# -*- coding: utf-8 -*-

# todo, enable and handle: $http_HEADER, $cookie_COOKIE in nginx logformat def

import csv, sys, os, datetime, re
from urllib2 import unquote
from dateutil.parser import parse
from pbs import host, ErrorReturnCode_1
from urlparse import urlparse, parse_qs
from operator import itemgetter
from plugins import init_plugins, handle
import GeoIP
import pymongo

geoipdb=None
agents=None
countries=None
ignorepaths=None
goodpaths=None
ignoremissing=None
filters=None
headers = ["time_local","connection","remote_addr","https","http_host",
           "request","status","request_length","body_bytes_sent","request_time",
           "http_referer","remote_user","http_user_agent","http_x_forwarded_for","msec",
           # below are computed fields
           "request_type", "path", "http_version", "from_tor", "ispage", "isbot",
           "hostname", "extref","search_query","country","year","month","day", "tags"
           ]

basepath=os.path.dirname(os.path.abspath(__file__))

db=None

def init():
    global geoipdb, agents, countries, \
           ignorepaths, goodpaths, ignoremissing, \
           filters
    # Load the database once and store it globally in interpreter memory.
    geoipdb = GeoIP.open('%s/data/GeoIP.dat' %
                         basepath,GeoIP.GEOIP_STANDARD)

    fp=open('%s/data/agents.csv' % basepath,'r')
    agents={}
    for line in fp:
        line=' '.join(line.split())
        if not line: continue
        type,text=line.split(',',1)
        agents[text]=type.split()
    fp.close()

    csvfile = open('%s/data/countrylist.csv' % basepath,'r')
    dialect = csv.Sniffer().sniff(csvfile.read(32768))
    csvfile.seek(0)
    headers = csv.reader(csvfile, dialect=dialect).next()
    reader = UnicodeDictReader(csvfile,
                               fieldnames=headers,
                               dialect=dialect)
    countries={}
    for line in reader:
        countries[line['ISO 3166-1 2 Letter Code']]=line
    csvfile.close()

    fp=open('%s/data/%s/ignorepaths' % (basepath, sys.argv[1]),'r')
    ignorepaths=[re.compile(x.strip()) for x in fp]
    fp.close()

    fp=open('%s/data/%s/ignoremissing' % (basepath, sys.argv[1]),'r')
    ignoremissing=[re.compile(x.strip()) for x in fp]
    fp.close()

    fp=open('%s/data/%s/goodpaths' % (basepath, sys.argv[1]),'r')
    goodpaths=[re.compile(r"%s" % x.strip()) for x in fp]
    fp.close()

    filters, queries=init_plugins(sys.argv[1])

def UnicodeDictReader(utf8_data, **kwargs):
    csv_reader = csv.DictReader(utf8_data, **kwargs)
    for row in csv_reader:
        yield dict([(key, unicode(value or "", "utf8")) for key, value in row.iteritems()])

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

def process():
    init()
    db=pymongo.Connection().pywik

    csv.register_dialect('nginx',
                         **{'lineterminator': '\r\n',
                            'skipinitialspace': False,
                            'quoting': 0,
                            'delimiter': ';',
                            'quotechar': '"',
                            'doublequote': False})
    reader = UnicodeDictReader(sys.stdin, fieldnames=headers, dialect='nginx')
    # skip headers
    reader.next()

    last=None
    if 'import' not in sys.argv:
        last=(db.__getitem__(sys.argv[1]).find_one({},['time_local'],sort=[('time_local',-1)]) or {}).get('time_local')
        print 'skipping to', last

    i=0
    for line in reader:
        if last and line['time_local']<last:
            continue
        date=todate(line['time_local'])
        line['timestamp']=date

        line['tags']=[]
        # request_type, path, http_version
        (line['request_type'],
         line['path'],
         line['http_version'])=explodereq(line['request'])

        # sig based detection... :/
        # TODO plugin
        if '?address=' in line['path']:
            line['bad']=['appaddr']

        # extract query strings if any
        line['search_query']=get_query(line['http_referer'])

        # is page?
        if textfilterre(line['path'], patterns=goodpaths):
            line['tags'].append('page')
        if not 'page' in line['tags'] and not textfilterre(line['path'],ignorepaths):
            line['tags'].append('unknown')
        # append Country
        line['country']=get_country(line['remote_addr'])
        # isbot?
        # B = Browser
        # C = Link-, bookmark-, server- checking
        # D = Downloading tool
        # P = Proxy server, web filtering
        # R = Robot, crawler, spider
        # S = Spam or bad bot
        line['agent']=agents.get(line['http_user_agent'],['?'])
        if set(line['agent']).intersection(['S', 'P', 'R', 'C']):
            line['tags'].append('bot')
        line['agent']=agents.get(line['http_user_agent'],['?'])
        line['msec']=float(line['msec'])
        line['request_time']=float(line['request_time'])
        line['connection']=int(line['connection'])
        line['body_bytes_sent']=int(line['body_bytes_sent'])
        line['request_length']=int(line['request_length'])
        line['year']=date.year
        line['month']=date.month
        line['day']=date.day
        if line['https']=='1':
            line['tags'].append('https')
        line['status']=int(line['status'])

        if line['status']=='404':
            if not textfilterre(line['path'],ignoremissing):
                line['tags'].append('notfound')
            if not line['ispage'] and not textfilterre(line['path'],ignorepaths):
                line['tags'].append('unknown')

        handle(line, filters)
        if not db.__getitem__(sys.argv[1]).find_one({'connection': line['connection']}):
            i+=1
            #print sorted([(k,v) for k,v in line.items() if v])
            #print sorted(line['tags'])
            db.__getitem__(sys.argv[1]).save(line)
    print '\ntotal new', i

if __name__ == "__main__":
    db=pymongo.Connection().pywik
    db.__getitem__(sys.argv[1]).ensure_index([('connection', 1)])
    db.__getitem__(sys.argv[1]).ensure_index([('tags', 1)])
    db.__getitem__(sys.argv[1]).ensure_index([('status', 1)])
    db.__getitem__(sys.argv[1]).ensure_index([('time_local', 1)])

    process()
