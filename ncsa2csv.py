#!/usr/bin/env python
# -*- coding: utf-8 -*-

import fileinput, csv, sys, cStringIO, codecs, apachelog

# missing fields in NCSA format, provided by CSV format
# "connection","https","http_host",
# "request_length","request_time",
# "http_x_forwarded_for","msec",

class UnicodeWriter:
    """
    A CSV writer which will write rows to CSV file "f",
    which is encoded in the given encoding.
    """

    def __init__(self, f, dialect=csv.excel, encoding="utf-8", **kwds):
        # Redirect output to a queue
        self.queue = cStringIO.StringIO()
        self.writer = csv.writer(self.queue, dialect=dialect, **kwds)
        self.stream = f
        self.encoder = codecs.getincrementalencoder(encoding)()

    def writerow(self, row):
        self.writer.writerow([s.encode("utf-8") for s in row])
        # Fetch UTF-8 output from the queue ...
        data = self.queue.getvalue()
        data = data.decode("utf-8")
        # ... and reencode it into the target encoding
        data = self.encoder.encode(data)
        # write to the target stream
        self.stream.write(data)
        # empty queue
        self.queue.truncate(0)

    def writerows(self, rows):
        for row in rows:
            self.writerow(row)

headers = ["time_local","connection","remote_addr","https","http_host",
           "request","status","request_length","body_bytes_sent","request_time",
           "http_referer","remote_user","http_user_agent","http_x_forwarded_for","msec"]

csv.register_dialect('nginx',
                     **{'lineterminator': '\r\n',
                        'skipinitialspace': False,
                        'quoting': 0,
                        'delimiter': ';',
                        'quotechar': '"',
                        'doublequote': False})
writer = UnicodeWriter(sys.stdout, dialect='nginx')

class nginxparser(apachelog.parser):
    def alias(self, name):
        if name=='%>s':
            return 'status'
        if name=='%h':
            return 'remote_addr'
        if name=='%b':
            return "body_bytes_sent",
        if name=='%t':
            return 'time_local'
        if name=='%u':
            return 'remote_user'
        if name=='%r':
            return 'request'
        if name=='%{Referer}i':
            return 'http_referer'
        if name=='%{User-agent}i':
            return 'http_user_agent'
        return name

if __name__ == "__main__":
    p = nginxparser(apachelog.formats['extended'])
    for line in fileinput.input():
        try:
            res = p.parse(line)
        except:
            sys.stderr.write("Unable to parse %s" % line)
            continue
        res['time_local']=res['time_local'][1:-1]
        writer.writerow((str(res.get(k,'')).encode('utf-8') for k in headers))
