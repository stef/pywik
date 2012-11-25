#!/usr/bin/env python

import pymongo, os, sys

basepath=os.path.dirname(os.path.abspath(__file__))

def init_plugins(host):
    filters=[]
    queries=[]
    oldpath=sys.path
    sys.path=[basepath+'/data/'+host+'/plugins',basepath+'/data/plugins', basepath]+sys.path
    for fname in sorted(os.listdir(basepath+'/data/'+host+'/plugins'))+sorted(os.listdir(basepath+'/data/plugins')):
        if fname.endswith('.py'):
            #print >>sys.stderr, '[i] loading plugin', fname[:-3]
            try:
                mod=__import__(fname[:-3], globals(), locals(), ['process', 'queries', 'init'],-1)
                if 'init' in dir(mod):
                    mod.init({'host': host})
                filters.append(mod.process)
                queries.extend(mod.queries())
            except: pass
    sys.path=oldpath
    return (filters, queries)

def handle(item, filters):
    for hndlr in filters:
        item=hndlr(item)
    return item

if __name__ == "__main__":
    filters, queries=init_plugins(sys.argv[1])
    for entry in pymongo.Connection().pywik.__getitem__(sys.argv[1]).find(limit=1000):
        print handle(entry, filters)
