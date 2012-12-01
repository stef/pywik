# depends on hostname plugin

from load import basepath

torexits=[]
def init(ctx):
    global torexits
    with open('%s/data/torexits.csv' % basepath,'r') as fp:
        torexits=[x.strip() for x in fp]
    #print '[tor plugin]', len(torexits), 'torexits loaded'

def process(entry):
   if entry['remote_addr'] in torexits:
      entry['tags'].append('tor')
   return entry

def queries():
    return [('tor', {'tags': ['tor', 'page'], },['path', 'hostname', 'http_user_agent']),
            ('tor404', {'tags': ['tor'], 'status': 404 },['path', 'hostname', 'http_user_agent'])]
