from pbs import host, ErrorReturnCode_1
ipcache={}

def gethost(ip):
    if ip in ipcache: return ipcache[ip]
    try:
        ipcache[ip]=host(ip).split(' ')[-1][:-2]
        return ipcache[ip]
    except ErrorReturnCode_1:
        ipcache[ip]=''
        return ''

def process(entry):
    entry['hostname']=gethost(entry['remote_addr'])
    return entry
