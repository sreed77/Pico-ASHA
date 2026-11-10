import struct, sys, collections, subprocess, os, array
src, work, outc, want = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
os.makedirs(work, exist_ok=True)
data = open(src,'rb').read()
pos = 16; recs = []
EPOCH = 0x00dcddb30f2f8000
while pos + 24 <= len(data):
    orig, incl, flags, drops, ts = struct.unpack('>IIIIQ', data[pos:pos+24])
    recs.append(((ts-EPOCH)/1e6, flags, data[pos+24:pos+24+incl])); pos += 24+incl
t0 = recs[0][0]
streams = {0x040: [], 0x042: []}
for t, flags, p in recs:
    if flags & 1 or len(p) < 5 or p[0] != 2: continue
    hf = struct.unpack_from('<H', p, 1)[0]; h = hf & 0xFFF; pb = (hf >> 12) & 3
    if h not in streams or pb not in (0, 2): continue
    l2len, cid = struct.unpack_from('<HH', p, 5)
    if cid < 0x40 or l2len != 163: continue
    body = p[9:9+l2len]
    if struct.unpack_from('<H', body, 0)[0] != 161: continue
    streams[h].append((t-t0, body[2], body[3:163]))
L, R = streams[0x040], streams[0x042]
byseq = collections.defaultdict(list)
for t, s, pl in R: byseq[s].append((t, pl))
pairs = []
for t, s, pl in L:
    c = [(abs(tr-t), tr, plr) for tr, plr in byseq.get(s, []) if abs(tr-t) < 0.2]
    if c: c.sort(); pairs.append((t, s, pl, c[0][2]))
best=(0,0); start=0
for i in range(1, len(pairs)+1):
    if i == len(pairs) or (pairs[i][1]-pairs[i-1][1]) % 256 != 1:
        if i-start > best[1]-best[0]: best=(start,i)
        start=i
run = pairs[best[0]:best[1]]
seg = run[100:100+want]                        # SAME segment as the packet replay build
open(os.path.join(work,'left.g722'),'wb').write(b''.join(x[2] for x in seg))
open(os.path.join(work,'right.g722'),'wb').write(b''.join(x[3] for x in seg))
for side in ('left','right'):
    r = subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','g722',
                        '-i',os.path.join(work,side+'.g722'),'-f','s16le','-ar','16000','-ac','1',
                        os.path.join(work,side+'.pcm')], capture_output=True, text=True)
    if r.returncode != 0: print('ffmpeg failed:', r.stderr); sys.exit(1)
l = array.array('h'); l.frombytes(open(os.path.join(work,'left.pcm'),'rb').read())
r_ = array.array('h'); r_.frombytes(open(os.path.join(work,'right.pcm'),'rb').read())
n = min(len(l), len(r_))
frames = n // 16
n = frames * 16
import math
def rms(a): return math.sqrt(sum(v*v for v in a[:n]) / n)
print(f"decoded {len(l)} / {len(r_)} samples per channel -> using {n} samples ({n/16000:.2f} s, {frames} 1-ms frames)")
print(f"RMS left {rms(l):.0f}, right {rms(r_):.0f}, peak left {max(abs(v) for v in l[:n])}, peak right {max(abs(v) for v in r_[:n])}")
# write C file: interleaved L,R int16, in flash only
with open(outc,'w',newline='\n') as f:
    f.write('/* GENERATED from a phone Bluetooth capture. Private audio content: do not publish or commit. */\n#include <stdint.h>\n#include "pico.h"\n')
    f.write(f'const uint32_t replay_pcm_frames = {frames};\n')
    f.write(f'const int16_t replay_pcm[{n*2}] __in_flash("replay") = {{\n')
    buf=[]
    for i in range(n):
        buf.append(str(l[i])); buf.append(str(r_[i]))
        if len(buf) >= 32: f.write(','.join(buf)+',\n'); buf=[]
    if buf: f.write(','.join(buf)+'\n')
    f.write('};\n')
print('wrote', outc, os.path.getsize(outc), 'bytes of source')

