from load import uunquote, textfilterre, basepath
from urlparse import urlparse, parse_qs
import re, sys

def queries():
    return [ ('extrefs', {'country': {'$ne': 'UA'},
                          'search_query': "",
                          'tags': 'extref',
                          "http_referer": {'$ne': '-'}},['http_referer'])]

ownhosts=None
def init(ctx):
    global ownhosts
    with open('%s/data/%s/ownhosts' % (basepath, ctx['host']),'r') as fp:
        ownhosts=[re.compile("%s://%s/" % (scheme, host.strip())) for host in fp for scheme in ['http','https']]

def process(line):
    # Referer
    # unquote http_referer
    try:
        tmp=uunquote(line['http_referer']).decode('utf8')
    except:
        tmp=uunquote(line['http_referer'])
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
    if line['http_referer'] not in ['', '-'] and not textfilterre(line['http_referer'], patterns=ownhosts):
        line['tags'].append('extref')
    return line
