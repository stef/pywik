#!/usr/bin/env python

# This file is part of pywik.
#
#  pywik is free software: you can redistribute it and/or modify
#  it under the terms of the GNU Affero General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  pywik is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Affero General Public License for more details.
#
#  You should have received a copy of the GNU Affero General Public License
#  along with pywik. If not, see <http://www.gnu.org/licenses/>.
#
# (C) 2012- by s

from flask import Flask, request, render_template, redirect, flash, jsonify
from pywik import pywik, getentries
from common import cfg
from urllib import quote_plus, unquote_plus

menu_items  = (('/today'            , 'today')
              ,('/yesterday'        , 'yesterday')
              ,('/recently'         , 'recently')
              ,('/lastweek'         , 'lastweek')
              ,('/lastmonth'        , 'lastmonth')
              ,('/lastquarter'      , 'lastquarter')
              ,('/lastyear'         , 'lastyear')
              )

app = Flask(__name__)
app.secret_key = cfg.get('app', 'secret_key')

@app.context_processor
def contex():
    global menu_items, cfg, query
    return {'menu'  : menu_items
           ,'cfg'   : cfg
           ,'query' : ''
           ,'path'  : request.path
           }

def parse_query(q):
    return q.get('query')

def totspan(tf):
    if tf=="yesterday": return 2
    if tf=="recently": return 3
    elif tf=="lastweek": return 7
    elif tf=="lastmonth": return 30
    elif tf=="lastquarter": return 121
    elif tf=="lastyear": return 365
    return 1

@app.route('/', methods=['GET'])
def index():
    return redirect('/today')

@app.route('/<string:site>/<string:timeframe>', methods=['GET'])
def stats(site, timeframe):
    if request.args.get('q') and request.args.get('k'):
        return render_template('list.html'
                               ,data = getentries(site,
                                                  request.args.get('k'),
                                                  request.args.get('q'),
                                                  totspan(timeframe))
                               ,key = request.args.get('k')
                               ,val = request.args.get('q')
                               ,timeframe = timeframe
                               ,site = site
                               )

    elif request.args.get('format')=='json':
        return jsonify(items=pywik(site, totspan(timeframe)))
    return render_template('index.html'
                          ,data = pywik(site, totspan(timeframe))
                          ,timeframe = timeframe
                          ,site = site
                          )

@app.template_filter()
def quote(txt):
    if type(txt) in [unicode, str]:
        return quote_plus(txt.encode('utf8'))
    else:
        return txt

if __name__ == "__main__":
    app.run(debug        = cfg.get('server', 'debug')
           ,use_debugger = cfg.get('server', 'debug')
           ,port         = int(cfg.get('server', 'port'))
           )

