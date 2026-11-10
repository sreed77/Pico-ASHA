import struct, sys, collections
data = open(sys.argv[1],'rb').read()
pos = 16; recs = []
EPOCH = 0x00dcddb30f2f8000
while pos + 24 <= len(data):
    orig, incl, flags, drops, ts = struct.unpack('>IIIIQ', data[pos:pos+24])
    recs.append(((ts-EPOCH)/1e6, flags, data[pos+24:pos+24+incl])); pos += 24+incl
t0 = recs[0][0]
conn_hdl = {0x040:'aid1',0x042:'aid2'}
print("ATT writes / notifications on the two aid links (time s, dir, handle, opcode, value):")
n=0
for t, flags, p in recs:
    if len(p) < 9 or p[0] != 2: continue
    hf = struct.unpack_from('<H', p, 1)[0]; h = hf & 0xFFF; pb = (hf>>12)&3
    if h not in conn_hdl or pb not in (0,2): continue
    l2len, cid = struct.unpack_from('<HH', p, 5)
    if cid != 4: continue
    att = p[9:9+l2len]
    op = att[0]
    d = 'phone->aid' if not (flags & 1) else 'aid->phone'
    if op in (0x12, 0x52, 0x1B, 0x1D) and len(att) >= 3:
        hd = struct.unpack_from('<H', att, 1)[0]
        print(f"{t-t0:8.2f}s {conn_hdl[h]} {d} op=0x{op:02x} attr=0x{hd:04x} value={att[3:].hex()}")
        n+=1
    if n > 70: break
