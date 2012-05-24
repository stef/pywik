# -*- coding: utf-8 -*-
# <nbformat>2</nbformat>

# <codecell>

from pandas import *
import datetime
from functools import partial

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

now=datetime.datetime.now(GMT1())
lastweek = now - datetime.timedelta(days=7)
lastmonth = now - datetime.timedelta(days=30)

raw = read_csv("logs/ctrlc-access.csv", 
               sep=';', 
               names=["time_local","connection","remote_addr","https","http_host","request","status","request_length","body_bytes_sent","request_time","http_referer","remote_user","http_user_agent","http_ x_forwarded_for","msec"],
               converters={'time_local': todate,},
               encoding='utf8')

# <codecell>

# only keep fresh stuff
fresh = raw[raw.time_local>lastmonth]

# filter out all non successful page loads
ok_status = fresh[fresh.status == 200]

pages = ok_status[ok_status.ispage == True]
humans = pages[pages['isbot']==False]
humans

# <codecell>

byip = humans.groupby('remote_addr')
ipcount = byip.apply(len)
ipcount.sort()
ipcount[-10:]


def today(ix, df=None):
    return df.ix[ix]['time_local'].day

def todayseries(df):
    bydays=partial(today,df=df)
    byday = df.groupby(bydays)
    return byday.apply(len)

#todayseries(raw[raw.status == 200]).plot(label="ok")
#todayseries(raw[raw.status != 200]).plot(label="no")
#todayseries(raw[raw.status == 404]).plot(label="404")
todayseries(humans).plot()
todayseries(pages).plot()

# <codecell>

agents = humans.groupby('http_user_agent')
agentcount = agents.apply(len)
agentcount.sort()
agentcount

# <codecell>


# <codecell>
externals=humans[humans.extref == True]
refs = externals.groupby('http_referer').apply(len)
refs.sort()
refs

# <codecell>

reqs = humans.groupby('path').apply(len)
reqs.sort()
reqs

# <codecell>

byuser = humans.groupby(['remote_addr', 'http_user_agent'])
tmp = byuser.apply(len)
tmp.sort()

for key in tmp.index[-10:]:
    print key[0]
    print key[1]
    print concat([byuser.get_group(key)['time_local'], byuser.get_group(key)['path'], byuser.get_group(key)['http_referer']], axis=1).to_string()

# <codecell>
