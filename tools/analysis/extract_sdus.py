import struct, sys, collections
src, outdir, want = sys.argv[1], sys.argv[2], int(sys.argv[3])
data = open(src,'rb').read()
pos = 16; recs = []
EPOCH = 0x00dcddb30f2f8000
while pos + 24 <= len(data):
    orig, incl, flags, drops, ts = struct.unpack('>IIIIQ', data[pos:pos+24])
    recs.append(((ts-EPOCH)/1e6, flags, data[pos+24:pos+24+incl])); pos += 24+incl
t0 = recs[0][0]
streams = {0x040: [], 0x042: []}   # left, right
for t, flags, p in recs:
    if flags & 1 or len(p) < 5 or p[0] != 2: continue          # only host -> controller ACL
    hf = struct.unpack_from('<H', p, 1)[0]; h = hf & 0xFFF; pb = (hf >> 12) & 3
    if h not in streams or pb not in (0, 2): continue
    l2len, cid = struct.unpack_from('<HH', p, 5)
    if cid < 0x40 or l2len != 163: continue
    body = p[9:9+l2len]
    sdu_len = struct.unpack_from('<H', body, 0)[0]
    if sdu_len != 161: continue
    seq = body[2]; payload = body[3:3+160]
    if len(payload) != 160: continue
    streams[h].append((t-t0, seq, payload))
for h, l in streams.items(): print(f"handle 0x{h:03x}: {len(l)} SDUs, first at {l[0][0]:.1f}s, last at {l[-1][0]:.1f}s")
def unwrap(lst):
    out = {}; absid = 0; prev = None
    for t, seq, pl in lst:
        if prev is not None:
            step = (seq - prev) % 256
            if step != 1: absid += 1000   # break marker: discontinuity (sequence jump)
            else: absid += 1
        out[absid] = (t, seq, pl); prev = seq
    return out
# Pair the two aids by (sequence number, time proximity)
L, R = streams[0x040], streams[0x042]
byseq = collections.defaultdict(list)
for t, s, pl in R: byseq[s].append((t, pl))
pairs = []
for t, s, pl in L:
    cands = [(abs(tr - t), tr, plr) for tr, plr in byseq.get(s, []) if abs(tr - t) < 0.2]
    if cands:
        cands.sort(); pairs.append((t, s, pl, cands[0][2]))
print("paired SDUs:", len(pairs))
# find the longest run of consecutive sequence numbers
best = (0, 0); start = 0
for i in range(1, len(pairs) + 1):
    if i == len(pairs) or (pairs[i][1] - pairs[i-1][1]) % 256 != 1:
        if i - start > best[1] - best[0]: best = (start, i)
        start = i
run = pairs[best[0]:best[1]]
print(f"longest gapless run: {len(run)} pairs from {run[0][0]:.1f}s to {run[-1][0]:.1f}s")
skip = 100 if len(run) > want + 200 else 0   # skip the first 2 seconds of the run
seg = run[skip:skip+want]
print(f"using {len(seg)} pairs ({len(seg)*0.02:.1f} s) starting at {seg[0][0]:.1f}s of the capture")
import os
os.makedirs(outdir, exist_ok=True)
n = len(seg)
def arr(name, idx):
    b = b''.join(x[idx] for x in seg)
    rows = []
    for i in range(0, len(b), 32):
        rows.append(','.join(str(v) for v in b[i:i+32]))
    return f"const uint8_t {name}[{len(b)}] = {{\n" + ',\n'.join(rows) + "\n};\n"
with open(os.path.join(outdir, 'replay_sdus.c'), 'w', newline='\n') as f:
    f.write("/* GENERATED from a phone Bluetooth capture. Private audio content: do not publish or commit. */\n#include <stdint.h>\n")
    f.write(f"const uint32_t replay_count = {n};\n")
    f.write(arr('replay_l', 2) if False else arr('replay_l', 2))
    f.write(arr('replay_r', 3))
print("wrote", os.path.join(outdir, 'replay_sdus.c'))
