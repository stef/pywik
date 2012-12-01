# depends on hostname plugin

from load import basepath
import re

aggregators=[]

def init(ctx):
    global aggregators
    with open('%s/data/%s/rss' % (basepath, ctx['host']),'r') as fp:
        aggregators=[re.compile(x.strip()) for x in fp]

def process(entry):
    for feeder in aggregators:
        if feeder.match(entry['path']):
            entry['tags'].append('rss')
    return entry

def queries():
    return [('rss', {'tags': 'rss' },['hostname', 'http_user_agent'])]
