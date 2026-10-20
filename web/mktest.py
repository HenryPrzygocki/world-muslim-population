"""Mirror the GitHub Pages build into web/test for local testing (d3 served locally: the sandbox has no CDN access)."""
import glob, os, shutil
WEB = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(WEB); T = f'{WEB}/test'
os.makedirs(T, exist_ok=True)
for f in glob.glob(f'{T}/*.json') + glob.glob(f'{T}/*.csv'): os.remove(f)
for f in glob.glob(f'{ROOT}/*.json') + glob.glob(f'{ROOT}/*.csv'): shutil.copy(f, T)
s = open(f'{ROOT}/index.html').read().replace('https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js', 'd3.min.js')
open(f'{T}/index.html', 'w').write(s)
print('test copy ready')
