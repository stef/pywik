#!/usr/bin/env python

if __name__ == "__main__":
    import sys
    sys.path.append('../..')

from load import basepath
from pbs import host, ErrorReturnCode_1
import re
ipcache={}
hostcache={}

def dashes(ip):
    return ip.replace('.', '-')

def hexa(ip):
    return ''.join(["%x" % int(x) for x in ip.split('.')])

def regex(ip):
    return "[0-9A-Za-z]{7,}"

bots={ "DoCoMo/2.0 N905i(c100;TB;W24H16) (compatible; Googlebot-Mobile/2.1; +http://www.google.com/bot.html)": { 'toname': dashes,
                                                                                                                 'type': 'google',
                                                                                                                 'fmt': "crawl-%s\.googlebot\.com"},
       "SAMSUNG-SGH-E250/1.0 Profile/MIDP-2.0 Configuration/CLDC-1.1 UP.Browser/6.2.3.3.c.1.101 (GUI) MMP/2.0 (compatible; Googlebot-Mobile/2.1; +http://www.google.com/bot.html)": { 'toname': dashes,
                                                                                                                 'type': 'google',
                                                                                                                 'fmt': "crawl-%s\.googlebot\.com"},
       "Mozilla/5.0 (iPhone; U; CPU iPhone OS 4_1 like Mac OS X; en-us) AppleWebKit/532.9 (KHTML, like Gecko) Version/4.0.5 Mobile/8B117 Safari/6531.22.7 (compatible; Googlebot-Mobile/2.1; +http://www.google.com/bot.html)":  { 'toname': dashes,
                                                                                                                 'type': 'google',
                                                                                                                 'fmt': "crawl-%s\.googlebot\.com"},
       "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)": { 'toname': dashes,
                                                                                     'type': 'google',
                                                                                     'fmt': "crawl-%s\.googlebot\.com"},
       "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)": { 'toname': dashes,
                                                                                    'type': 'bing',
                                                                                    'fmt': "msnbot-%s\.search\.msn\.com"},
       "Mozilla/5.0 (compatible; YandexBot/3.0; +http://yandex.com/bots)": { 'toname': dashes,
                                                                             'type': 'yandex',
                                                                             'fmt': "spider-%s\.yandex\.com"},
       "Mozilla/5.0 (compatible; YandexImages/3.0; +http://yandex.com/bots)": { 'toname': dashes,
                                                                                'type': 'yandex',
                                                                                'fmt': "img-spider-%s.yandex.com"},
       "Baiduspider+(+http://www.baidu.com/search/spider.htm)": { 'toname': dashes,
                                                                  'type': 'baidu',
                                                                  'fmt': "baiduspider-%s.crawl.baidu.com"},
       "Mozilla/5.0 (compatible; Yahoo! Slurp; http://help.yahoo.com/help/us/ysearch/slurp)": { 'toname': regex,
                                                                                                'type': 'yahoo',
                                                                                                'fmt': "%s\.crawl\.yahoo\.net"},
       "SeznamBot/3.0 (+http://fulltext.sblog.cz/)": { 'toname': dashes,
                                                       'type': 'seznam',
                                                       'fmt': "fulltextrobot-%s.seznam.cz"},
       "Mozilla/5.0 (compatible; Seznam screenshot-generator 2.0; +http://fulltext.sblog.cz/screenshot/)": { 'toname': dashes,
                                                                                                             'type': 'seznam',
                                                                                                             'fmt': "screenshotgenerator-%s.seznam.cz"},
       # fixme: regex is too long for only 3 char regex in discobot
       #"Mozilla/5.0 (compatible; discoverybot/2.0; +http://discoveryengine.com/discoverybot.html)": { 'toname': regex,
       #                                                                                               'type': 'disoveryengine',
       #                                                                                               'fmt': "discobot-%s.discoveryengine.com"},
    }

agents={}
def init(ctx):
    global agents
    fp=open('%s/data/agents.csv' % basepath,'r')
    for line in fp:
        line=' '.join(line.split())
        if not line: continue
        type,text=line.split(',',1)
        agents[text]=type.split()
    fp.close()

def gethost(ip):
    if ip in ipcache: return ipcache[ip]
    try:
        ipcache[ip]=host(ip).split(' ')[-1][:-2]
        return ipcache[ip]
    except ErrorReturnCode_1:
        ipcache[ip]=''
        return ''

def getip(hostname):
    if hostname in hostcache: return hostcache[hostname]
    try:
        res=[tmp.split()[-1] for tmp in host(hostname).split('\n') if tmp]
        hostcache[hostname]=res
        return res
    except ErrorReturnCode_1:
        return ''

def process(entry):
    # isbot?
    # B = Browser
    # C = Link-, bookmark-, server- checking
    # D = Downloading tool
    # P = Proxy server, web filtering
    # R = Robot, crawler, spider
    # S = Spam or bad bot
    entry['agent']=agents.get(entry['http_user_agent'],['?'])
    if not set(entry['agent']).intersection(['S', 'P', 'R', 'C']):
        return entry

    entry['tags'].append('bot')

    if not entry['http_user_agent'] in bots.keys(): return entry

    entry['bot']=bots[entry['http_user_agent']]['type']

    prediction=re.compile((bots[entry['http_user_agent']]['fmt'] %
                           bots[entry['http_user_agent']]['toname'](entry['remote_addr'])))
    hostname=gethost(entry['remote_addr'])
    if not prediction.match(hostname):
        entry['tags'].append('fakebot')
        del entry['tags'][entry['tags'].index('bot')]
        return entry
    if not entry['remote_addr'] in getip(hostname):
        entry['tags'].append('fakebot')
    else:
        entry['tags'].append('validbot')
    return entry

def queries():
    return [('validbots', {'tags': {'$all': ['validbot', 'page']}, },['bot']),
            ('fakebots', {'tags': 'fakebot' },['hostname', 'remote_addr', 'bot', 'path'])]

if __name__ == "__main__":
    init({})

    test={"tags": [],
          "remote_addr": "66.249.66.184",
          "http_user_agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"}
    print
    print process(test)

    test={"tags": [],
          "remote_addr": "64.249.66.184",
          "http_user_agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"}
    print
    print process(test)

    test={"tags": [],
          "remote_addr": "72.30.142.158",
          "http_user_agent": "Mozilla/5.0 (compatible; Yahoo! Slurp; http://help.yahoo.com/help/us/ysearch/slurp)"}
    print
    print process(test)

    test={"tags": [],
          "remote_addr": "71.30.142.158",
          "http_user_agent": "Mozilla/5.0 (compatible; Yahoo! Slurp; http://help.yahoo.com/help/us/ysearch/slurp)"}
    print
    print process(test)

    test={"tags": [],
          "remote_addr": "178.154.174.252",
          "http_user_agent": "Mozilla/5.0 (compatible; YandexBot/3.0; +http://yandex.com/bots)"}
    print
    print process(test)
