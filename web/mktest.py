s = open('site/index.html').read()
s = s.replace('https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js', 'd3.min.js').replace('https://cdn.jsdelivr.net/npm/topojson-client@3.1.0/dist/topojson-client.min.js', 'topojson-client.min.js')
s = '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><style>:root{color-scheme:light}body{margin:0;font:14px system-ui}[hidden]{display:none!important}</style></head><body>' + s + '</body></html>'
open('test/index.html', 'w').write(s)
