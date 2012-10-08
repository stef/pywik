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

def spark(data):
    blocks = u' ▁▂▃▄▅▆▇█'
    lo = float(min(data))
    hi = float(max(data))
    incr = (hi - lo)/(len(blocks)-1) or 1
    return ''.join([(blocks[int((float(n) - lo)/incr)]
                     if n else
                     ' ')
                    for n in data])

class GMT1(datetime.tzinfo):
    def __init__(self):         # DST starts last Sunday in March
        d = datetime.datetime(2012, 4, 1)   # ends last Sunday in October
        self.dston = d - datetime.timedelta(days=d.weekday() + 1)
        d = datetime.datetime(2012, 11, 1)
        self.dstoff = d - datetime.timedelta(days=d.weekday() + 1)
    def utcoffset(self, dt):
        return datetime.timedelta(hours=1) + self.dst(dt)
    def dst(self, dt):
        if self.dston <=  dt.replace(tzinfo=None) < self.dstoff:
            return datetime.timedelta(hours=1)
        else:
            return datetime.timedelta(0)
    def tzname(self,dt):
         return "GMT +1"

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

def printset(title,items):
    print title
    print u'\n'.join(items).encode('utf8')
    print

def cnt2lst(cnt):
    return [u"%s\t%s" % (val[0], key) for key, val in sorted(cnt.items(),reverse=True, key=itemgetter(1))]

headers = ["time_local","connection","remote_addr","https","http_host",
           "request","status","request_length","body_bytes_sent","request_time",
           "http_referer","remote_user","http_user_agent","http_x_forwarded_for","msec",
           "request_type", "path", "http_version", "ispage", "isbot",
           "hostname", "extref","search_query","country","year","month","day"]
notoks={}
notfounds={}
unknowns={}
bots={}
refs={}
pages={}
nations={}
hosts={}
days={}
months={}
searches={}
fromtor={}

now=datetime.datetime.now(GMT1())
span=None
if len(sys.argv)>2:
    if sys.argv[1]=="today":
        span = now - datetime.timedelta(days=1)
        del sys.argv[1]
    elif sys.argv[1]=="yesterday":
        span = now - datetime.timedelta(days=2)
        del sys.argv[1]
    elif sys.argv[1]=="recently":
        span = now - datetime.timedelta(days=3)
        del sys.argv[1]
    elif sys.argv[1]=="week":
        span = now - datetime.timedelta(days=7)
        del sys.argv[1]
    elif sys.argv[1]=="month":
        span = now - datetime.timedelta(days=30)
        del sys.argv[1]
    elif sys.argv[1]=="quarter":
        span = now - datetime.timedelta(days=121)
        del sys.argv[1]
if not span:
    span = now - datetime.timedelta(days=1)

init()

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

print "Starting from", span

for line in reader:
    # skip 1st line, 304 and anything outside timespan
    if (line['status'] in ['304'] or
        line['time_local']=="time_local"): continue
    date=todate(line['time_local'])
    if date<span: continue

    # request_type, path, http_version
    (line['request_type'],
     line['path'],
     line['http_version'])=explodereq(line['request'])

    # skip all requests to robots.txt
    if line['path']=='/robots.txt': continue

    if line['remote_addr'] in torexits:
        tmp=' '.join([line['path'].decode('utf8'),
                      line['status'],
                      line['http_referer'],
                      line['http_user_agent']
                      ])
        count(fromtor,tmp,line)
        continue

    # not ok?
    if ('200'>line['status'] or
        line['status']>='400' and
        line['status']!='404'):
        count(notoks,' '.join([line['status'], line['request']]),line)
        continue

    # extract query strings if any
    line['search_query']=get_query(line['http_referer'])
    if line['search_query']:
        count(searches,line['search_query'],line)

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
    if line['status']=='404':
        if not textfilterre(line['path'],ignoremissing):
            count(notfounds,line['path'],line)
        continue
    if not line['ispage'] and not textfilterre(line['path'],ignorepaths):
        count(unknowns,line['path'],line)
        continue

    # domain name
    line['hostname']=gethost(line['remote_addr'])

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
    if set(line['agent']).intersection(['S', 'P', 'R', 'C']):
        tmp=' '.join([''.join(line['agent']), line['http_user_agent']])
        count(bots,tmp,line)
        continue

    if line['extref'] and not line['search_query']:
        count(refs,line['http_referer'],line)

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

    # count pages, hosts, days and months for pages
    if not line['isbot'] and line['ispage']:
        count(pages,line['path'],line)

        cnt, elems=nations.get(line['country'],[0,[]])
        elems.append(line)
        nations[line['country']]=[cnt+1,elems]

        tmp=' '.join([line['country'],
                      line['hostname'] or line['remote_addr'],
                      line['http_user_agent']
                      ])
        count(hosts,tmp,line)

        count(days,line['day'],line)

        count(months,line['month'],line)

printset("Errors",cnt2lst(notoks))
printset("Unknown",cnt2lst(unknowns))
printset("Bots",cnt2lst(bots))
printset("Referers",cnt2lst(refs))
printset("Pages",cnt2lst(pages))
printset("Countries",[u"%s\t%s" % (val[0],
                                   countries.get(key,
                                                 {'Common Name': key})['Common Name'] if key else '-')
                      for key, val
                      in sorted(nations.items(),
                                reverse=True,
                                key=itemgetter(1))])
printset("Searches",cnt2lst(searches))
printset("From TOR",cnt2lst(fromtor))
print spark([val[0]
             for key, val
             in sorted(days.items(),
                       reverse=True)]).encode('utf8')
printset("Days",cnt2lst(days))
print spark([val[0]
             for key, val
             in sorted(months.items(),
                       reverse=True)]).encode('utf8')
printset("Months",cnt2lst(months))
printset("Not founds",cnt2lst(notfounds))
printset("Hosts",cnt2lst(hosts))

