#!/usr/bin/env python
# -*- coding: utf-8 -*-

# todo, enable and handle: $http_HEADER, $cookie_COOKIE in nginx logformat def

import sys, datetime, json
import pymongo
from operator import itemgetter
from plugins import init_plugins

# what i want to see
# good
#    graph of hits/day
#    popular pages
#    referers
#    search queries
#    viewers (see historical visits if any, distinguish by agent?)
#    bots
#    non-404 error requests, hosts
# bad
#    tor visits
#    non-typo 404 pages
#    top non-browser-user-agents (cross-ref with classes of other requests)
#    masquerading crawlers

queries=[ ('pages', {'country': {'$ne': 'UA'},
                     '$or': [{'bad': { '$size': 0 }},{'bad': {'$exists': False}}],
                     '$and': [ { 'tags': 'page' }, { 'tags': { '$nin': ['bot'] } } ]}, ['path']),
          ('searchqueries', {'search_query': {'$ne': ""}},['search_query']),
          ('errors', {'$or': [{'status': {'$lt': 200}},
                              {'status': {'$gt': 400}}],
                      'status': {'$ne': 404}},['status', 'path']),
          ('unknown', {'tags': 'unknown'},['path']),
          ('notfound', {'tags': 'notfound'},['path']),
          ('bots', {'tags': 'bot'},['http_user_agent']),
          ('404s', {'status': 404},['path']),
        ]
spans={'today': 1,
       'yesterday': 2,
       'recently': 3,
       'week': 7,
       'month': 30,
       'quarter': 121,
       }

def spark(data):
    if not data: return ('',0,0)
    blocks = u' ▁▂▃▄▅▆▇█'
    lo = float(min(data))
    hi = float(max(data))
    incr = (hi - lo)/(len(blocks)-1) or 1
    return (''.join([(blocks[int((float(n) - lo)/incr)]
                     if n else
                     ' ')
                    for n in data]),
            int(lo),
            int(hi))

def sparks(host, key, q):
    db=pymongo.Connection().pywik
    return spark([x['count']
                  for x
                  in db.__getitem__(host).group([key],
                                                       q,
                                                       {'count': 0},
                                                       'function(doc, out){ out.count++;}')])

def tostr(x):
    try:
        return str(x).encode('raw_unicode_escape').decode('utf-8')
    except:
        return repr(x)

def displayQ(host, title, q, fields):
    db=pymongo.Connection().pywik
    res=[]
    cur=db.__getitem__(host).find(q, fields)
    res.append('Total %s %s' % (title, cur.count()))

    res.append(u'\n'.join(
        [u"%s\t%s" % (int(x['count']),
                      u' '.join([tostr(x[f]) for f in fields]))
         for x in sorted(db.__getitem__(host).group(fields,
                                                    q,
                                                    {'count': 0},
                                                    'function(doc, out){ out.count++;}'),
                         key=itemgetter('count'),
                         reverse=True)]).encode('utf8'))
    return res

def pywik(site, span=1):
    db=pymongo.Connection().pywik
    now=datetime.datetime.now()
    qspan = now - datetime.timedelta(days=(7 if span<8 else span))
    span = now - datetime.timedelta(days=span)

    res=[]
    reports=queries[:]
    reports.extend(init_plugins(site)[1])
    for title, q, fields in reports:
        #print >>sys.stderr, title, q, fields
        qsparks=dict([x for x in q.items()])
        qsparks["timestamp"]={'$gt': qspan, '$lt': now}

        q["timestamp"]={'$gt': span, '$lt': now}
        res.append(
            {'total': db.__getitem__(site).find(q, fields).count(),
             'fields': fields,
             'title': title,
             'sparks': tod3(db.__getitem__(site).group(fields+['year','month','day'],
                                                       qsparks,
                                                       {'count': 0},
                                                       'function(doc, out){ out.count++;}'),fields),
             'lines': [ (int(x['count']),
                         dict([(f,x[f]) for f in fields]) )
                        for x in sorted(db.__getitem__(site).group(fields,
                                                                   q,
                                                                   {'count': 0},
                                                                   'function(doc, out){ out.count++;}'),
                                        key=itemgetter('count'),
                                        reverse=True ) ] } )
    return res

def ascii():
    now=datetime.datetime.now()
    span=None
    for k, v in spans.items():
        if k in sys.argv:
            span = now - datetime.timedelta(days=v)
            del sys.argv[sys.argv.index(k)]
    if not span:
        span = now - datetime.timedelta(days=1)

    reports=[]
    queries.extend(init_plugins(sys.argv[1])[1])
    for title, q, fields in queries:
        if title in sys.argv:
            reports.append((title, q, fields))
            del sys.argv[sys.argv.index(title)]

    if not reports: reports=queries
    res=[]
    for title, q, fields in reports:
        q["timestamp"]={'$gt': span, '$lt': now}
        gfx, lo, hi = sparks(sys.argv[1], 'day', q)
        res.append((u"%30s %8s %s %s" % (title, lo, gfx, hi)).encode('utf8'))

        res.extend(displayQ(sys.argv[1], title, q, fields))
        res.append('='*80)
    return res

def getentries(site,key,val, span):
    db=pymongo.Connection().pywik
    now=datetime.datetime.now()
    span = now - datetime.timedelta(days=span)
    return db.__getitem__(site).find({key:val,
                                      "timestamp": {'$gt': span,
                                                    '$lt': now}})

def tod3(entries,fields):
    acc={}
    mx = None
    mn = None
    for item in entries:
        date=(int(item['year']),int(item['month']),int(item['day']))
        title=u' '.join([unicode(item[k]) for k in fields])
        tmp={'x': date, 'y': int(item['count']), 'title': title}
        try:
            acc[title].append(tmp)
        except KeyError:
            acc[title]=[tmp]
        if not mx or mx < date:
            mx=date
        if not mn or mn > date:
            mn=date[:3]
    ret = []
    for k, sparse in acc.items():
        res=[]
        i=0
        if k in ['-','']: continue
        cur=datetime.date(*mn)- datetime.timedelta(days=1)
        for item in sorted(sparse, key=itemgetter('x')):
            diff=(datetime.date(*item['x'])-cur).days
            if diff>1: res.extend([{'x': len(res)+j, 'y': 0, 'text': item['title']} for j in xrange(diff-1)])
            res.append({'x': len(res), 'y': item['y'], 'text': item['title']})
            cur=datetime.date(*item['x'])
            i=i+1
        diff=(datetime.date(*mx) - cur).days
        res.extend([{'x': len(res) + j, 'y': 0} for j in xrange(diff)])
        ret.append(res)

    return json.dumps(ret)

if __name__ == "__main__":
    print '\n'.join(ascii())

