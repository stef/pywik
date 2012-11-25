from load import basepath, textfilterre, headers
import sys,re

tags={}

def init(ctx):
    fp=open('%s/data/%s/classes' % (basepath, ctx['host']),'r')
    try:
        while True:
            tag=fp.next().strip()
            if not tag: continue
            patterns=[]
            tags[tag]=patterns
            while True:
                field=fp.next().strip()
                if not field: break
                if not field in headers:
                    # skip to the next definition
                    while True:
                        tmp=fp.next()
                        if not tmp.strip(): break
                else:
                    pattern=fp.next()[:-1] # stripping trailing \n
                    if pattern:
                        patterns.append((field,re.compile(pattern)))
    except StopIteration:
        pass
    fp.close()
    return tags

def queries():
    return [(tag, {'$or': [{'bad': { '$size': 0 }},
                           {'bad': {'$exists': False}}],
                   '$and': [ { 'tags': ['page', tag] },
                             { 'tags': { '$nin': ['bot'] } } ]},
             ['path'])
         for tag in tags.keys()]

def process(line):
   inclass=False
   for tag, patterns in tags.items():
       for key, pattern in patterns:
           if textfilterre(line[key], patterns=[pattern]):
               line['tags'].append(tag)
               break
   return line
