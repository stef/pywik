# -*- coding: utf-8 -*-

import csv, sys, os
from urllib import unquote
from dateutil.parser import parse
from pbs import host, ErrorReturnCode_1
from urlparse import urlparse, parse_qs
import pygeoip

# Load the database once and store it globally in interpreter memory.
GEOIP = pygeoip.Database('%s/GeoIP.dat' % os.path.dirname(os.path.abspath(__file__)))

# Filter out bots
botagents = ['Superfeedr: Superparser bot',
             'Baiduspider',
             'ezooms.bot@gmail.com',
             'http://www.google.com/bot.html',
             'http://yandex.com/bots',
             'https://code.google.com/p/feedparser/',
             'magpie-crawler',
             'http://www.majestic12.co.uk/bot.php',
             'http://www.openindex.io/en/webmasters/spider.html',
             'http://blekko.com/about/blekkobot',
             'http://discoveryengine.com/discobot.html',
             'http://ahrefs.com/robot/',
             'http://www.commoncrawl.org/bot.html',
             'http://www.bing.com/bingbot.htm',
             'http://www.exabot.com/go/robot',
             'http://tt-rss.org/',
             'http://www.acoon.de/robot.asp',
             'http://www.facebook.com/externalhit_uatext.php',
             ]

# explode the request field into request_type, path and protocol
def explodereq(req):
    tmp=req.split()
    return [tmp[0], unquote(' '.join(tmp[1:-1])), tmp[-1]]

def todate(s):
    date, time = s.split(':',1)
    s="%s %s" % (date.replace('/','-'), time)
    return parse(s, dayfirst=True)

def textfilterend(text, patterns=[], exclude=True):
    if type(text)!=str: return text
    for mask in patterns:
        if text.endswith(mask):
            return exclude
    return not exclude

def textfilter(text, patterns=[], exclude=False):
    if type(text)!=str: return text
    for mask in patterns:
        if mask in text:
            return exclude
    return not exclude

def textfilterstart(text, patterns=[], exclude=False):
    if type(text)!=str: return text
    for mask in patterns:
        if text.startswith(mask):
            return exclude
    return not exclude

def gethost(ip):
    try:
        return host(ip).split(' ')[-1][:-2]
    except ErrorReturnCode_1:
        return ''

def get_query(url):
    urlobj=urlparse(url)
    query=parse_qs(urlobj.query)
    if (url.startswith('http://www.google.') or
        (urlobj.netloc.endswith("bing.com") and urlobj.path.startswith('/search'))):
        return query.get('q',[''])[0]
    return ''

def get_country(ip):
    tmp = GEOIP.lookup(ip)
    if not tmp.country:
        return ''
    else:
        return tmp.country

csvfile = open(sys.argv[1])
dialect = csv.Sniffer().sniff(csvfile.read(1024))
csvfile.seek(0)
reader = csv.reader(csvfile, dialect=dialect)

if not dialect.escapechar and not dialect.doublequote:
    dialect.doublequote = True

month=None
fp=None
for line in reader:
    date=todate(line[0])
    line[0]=date.isoformat()
    if date.month!=month:
        if fp: fp.close()
        month=date.month
        fname="%s-%s-%s.csv" % (sys.argv[1][:-4],
                                date.year,
                                date.month)
        print >>sys.stderr, "creating", fname
        fp=open(fname, 'w')
        writer=csv.writer(fp, dialect)
        writer.writerow(["time_local","connection","remote_addr","https","http_host",
                         "request","status","request_length","body_bytes_sent","request_time",
                         "http_referer","remote_user","http_user_agent","http_ x_forwarded_for","msec",
                         "request_type", "path", "http_version", "ispage", "isbot",
                         "hostname", "extref","search_query","country"])
    # request_type, path, http_version
    line.extend(explodereq(line[5]))
    # is page?
    line.append(textfilterend(line[16],patterns=['.html','/','.txt']))
    # isbot?
    line.append(textfilter(line[12],patterns=botagents,exclude=True))
    # domain name
    line.append(gethost(line[2]))
    # unquote referer
    tmp=unquote(line[10])
    # simplify referers
    if tmp.startswith('http://www.facebook.com/l.php?u='):
        line[10]='http://www.facebook.com/'
    else:
        line[10]=tmp
    # extref?
    line.append(textfilterstart(line[10], patterns=sys.argv[2:], exclude=False))
    # extract query strings if any
    line.append(get_query(line[10]))
    # append Country
    line.append(get_country(line[2]))
    writer.writerow(line)

if fp: fp.close()

