import struct, sys, statistics, collections
data = open(sys.argv[1],'rb').read()
pos = 16; recs = []
EPOCH = 0x00dcddb30f2f8000
while pos + 24 <= len(data):
    orig, incl, flags, drops, ts = struct.unpack('>IIIIQ', data[pos:pos+24])
    recs.append(((ts-EPOCH)/1e6, data[pos+24:pos+24+incl])); pos += 24+incl
t0 = recs[0][0]
ev = collections.defaultdict(list)
odd = 0
for t, p in recs:
    if len(p) >= 4 and p[0] == 4 and p[1] == 0x13:
        n = p[3]
        if len(p) != 4 + 4*n: odd += 1; continue
        for i in range(n):
            h = struct.unpack_from('<H', p, 4+2*i)[0] & 0xFFF
            c = struct.unpack_from('<H', p, 4+2*n+2*i)[0]
            ev[h].append((t-t0, c))
print("malformed events skipped:", odd)
for h, lst in sorted(ev.items()):
    if len(lst) < 100: continue
    times=[t for t,_ in lst]; cnt=[c for _,c in lst]
    # keep only the steady streaming window: longest run where consecutive gaps < 1 s
    gaps=[(b-a)*1000 for a,b in zip(times,times[1:])]
    sg=[g for g in gaps if g < 1000]
    dur = times[-1]-times[0]
    s=sorted(sg)
    print(f"handle 0x{h:03x}: {len(lst)} events, total acked {sum(cnt)}, count/event mean {statistics.mean(cnt):.2f} max {max(cnt)}")
    print(f"   gaps (<1s only): median {statistics.median(sg):.1f} ms, 90th {s[int(len(s)*.9)]:.1f}, 99th {s[int(len(s)*.99)]:.1f}, max {max(sg):.1f}; >=40ms {sum(1 for g in sg if g>=40)} of {len(sg)} ({100*sum(1 for g in sg if g>=40)/len(sg):.1f}%); >=60ms {sum(1 for g in sg if g>=60)}")
