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
countries=None
ignorepaths=None
goodpaths=None
ignoremissing=None
filters=None
headers = ["time_local","connection","remote_addr","https","http_host",
           "request","status","request_length","body_bytes_sent","request_time",
           "http_referer","remote_user","http_user_agent","http_x_forwarded_for","msec",
           # below are computed fields
           "request_type", "path", "http_version", "hostname", "search_query",
           "country","year","month","day", "tags", 'bot'
           ]

basepath=os.path.dirname(os.path.abspath(__file__))

db=None

def init():
    global geoipdb, countries, ignorepaths, goodpaths, ignoremissing, filters
    # Load the database once and store it globally in interpreter memory.
    geoipdb = GeoIP.open('%s/data/GeoIP.dat' %
                         basepath,GeoIP.GEOIP_STANDARD)

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
        try:
            yield dict([(key, unicode(value or "", "utf8")) for key, value in row.iteritems()])
        except:
            print row.items()
            print row
            raise

def uunquote(txt):
    try:
        return unquote(txt.encode('ascii')).decode('utf8')
    except:
        return unquote(txt)

def todate(s):
    date, time = s.split(':',1)
    try:
        tmp=parse(s)
    except:
        tmp=parse("%s %s" % (date.replace('/','-'), time), dayfirst=True)
    return tmp

# explode the request field into request_type, path and protocol
def explodereq(req):
    tmp=req.split()
    if len(tmp)<3:
        tmp.extend([''] * (3-len(tmp)))
    path=uunquote(' '.join(tmp[1:-1]))
    return [tmp[0], path, tmp[-1]]

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
        try:
            return query.get('q',[''])[0].decode('utf8')
        except UnicodeDecodeError:
            return query.get('q',[''])[0].decode('raw_unicode_escape')
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

        # extract query strings if any
        line['search_query']=get_query(line['http_referer'])

        # is page?
        if (line['path'].strip() and
            textfilterre(line['path'], patterns=goodpaths) and
            not textfilterre(line['path'], patterns=ignorepaths)):
            line['tags'].append('page')
        if (line['status']==200 and
            not 'page' in line['tags'] and
            not textfilterre(line['path'],ignorepaths)):
            line['tags'].append('unknown')
        # append Country
        line['country']=get_country(line['remote_addr'])
        line['msec']=float(line['msec']) if line['msec'] else ''
        line['request_time']=float(line['request_time']) if line['request_time'] else ''
        line['connection']=int(line['connection']) if line['connection'] else ''
        line['body_bytes_sent']=int(line['body_bytes_sent']) if line['body_bytes_sent'] else ''
        line['request_length']=int(line['request_length']) if line['request_length'] else ''
        line['year']=date.year
        line['month']=date.month
        line['day']=date.day
        if line['https']=='1':
            line['tags'].append('https')
        line['status']=int(line['status'])

        if line['status']==404:
            if not textfilterre(line['path'],ignoremissing):
                line['tags'].append('notfound')
            if not 'page' in line['tags'] and not textfilterre(line['path'],ignorepaths):
                line['tags'].append('unknown')

        handle(line, filters)
        if not db.__getitem__(sys.argv[1]).find_one({'connection': line['connection']}):
            i+=1
            db.__getitem__(sys.argv[1]).save(line)
    print '\ntotal new', i

if __name__ == "__main__":
    #db=pymongo.Connection().pywik
    db=pymongo.Connection().ncsatest
    db.__getitem__(sys.argv[1]).ensure_index([('connection', 1)])
    db.__getitem__(sys.argv[1]).ensure_index([('tags', 1)])
    db.__getitem__(sys.argv[1]).ensure_index([('status', 1)])
    db.__getitem__(sys.argv[1]).ensure_index([('time_local', 1)])
    db.__getitem__(sys.argv[1]).ensure_index([('timestamp', 1)])

    process()
