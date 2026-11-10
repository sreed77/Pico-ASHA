"""Read-only analysis of an Android btsnoop_hci.log: how the phone connects to and streams to ASHA hearing aids."""
import struct, sys, statistics, collections

path = sys.argv[1]
data = open(path, 'rb').read()
assert data[:8] == b'btsnoop\x00', 'not a btsnoop file'
version, datalink = struct.unpack('>II', data[8:16])
print(f"btsnoop version {version}, datalink {datalink} ({'H4' if datalink == 1002 else 'other'})")

TS_EPOCH_OFFSET = 0x00dcddb30f2f8000  # microseconds from year 0 to 1970
recs = []
pos = 16
while pos + 24 <= len(data):
    orig, incl, flags, drops, ts = struct.unpack('>IIIIQ', data[pos:pos + 24])
    pkt = data[pos + 24:pos + 24 + incl]
    pos += 24 + incl
    recs.append((ts - TS_EPOCH_OFFSET, flags, pkt))
print(f"records: {len(recs)}")
t0 = recs[0][0]
def tsec(t): return (t - t0) / 1e6

PHY = {1: '1M', 2: '2M', 3: 'Coded'}
conns = {}          # handle -> dict
events = []         # (time, text)
cid_map = {}        # (handle, cid) -> info
acl_tx = collections.defaultdict(list)   # (handle, cid) -> [(t, sdu_len)]
frag_count = collections.defaultdict(int)
nocp = collections.defaultdict(list)

def u16(b, o): return struct.unpack_from('<H', b, o)[0]

for t, flags, p in recs:
    if not p: continue
    typ = p[0]
    rx = bool(flags & 1)
    ts = tsec(t)
    if typ == 4 and len(p) >= 3:                 # HCI event
        ev = p[1]
        if ev == 0x3E:
            sub = p[3]
            if sub == 0x01 and len(p) >= 21:      # LE Connection Complete
                st, h = p[4], u16(p, 5) & 0xFFF
                iv, lat, to = u16(p, 15), u16(p, 17), u16(p, 19)
                conns[h] = dict(t=ts, iv=iv, lat=lat, to=to, role=p[7], addr=p[9:15][::-1].hex(':'))
                events.append((ts, f"LE connect handle 0x{h:03x} st={st} interval={iv*1.25:.2f}ms latency={lat} timeout={to*10}ms"))
            elif sub == 0x0A and len(p) >= 33:    # Enhanced Connection Complete
                st, h = p[4], u16(p, 5) & 0xFFF
                iv, lat, to = u16(p, 27), u16(p, 29), u16(p, 31)
                conns[h] = dict(t=ts, iv=iv, lat=lat, to=to, role=p[7], addr=p[9:15][::-1].hex(':'))
                events.append((ts, f"LE connect (enh) handle 0x{h:03x} st={st} interval={iv*1.25:.2f}ms latency={lat} timeout={to*10}ms"))
            elif sub == 0x03 and len(p) >= 13:    # Connection Update Complete
                st, h = p[4], u16(p, 5) & 0xFFF
                iv, lat, to = u16(p, 7), u16(p, 9), u16(p, 11)
                events.append((ts, f"conn UPDATE done handle 0x{h:03x} st={st} interval={iv*1.25:.2f}ms latency={lat} timeout={to*10}ms"))
                if h in conns: conns[h]['upd'] = (iv, lat, to)
            elif sub == 0x0C and len(p) >= 9:     # PHY Update Complete
                st, h = p[4], u16(p, 5) & 0xFFF
                events.append((ts, f"PHY update handle 0x{h:03x} st={st} tx={PHY.get(p[7], p[7])} rx={PHY.get(p[8], p[8])}"))
                if h in conns: conns[h]['phy'] = (p[7], p[8])
            elif sub == 0x07 and len(p) >= 14:    # Data length change
                h = u16(p, 4) & 0xFFF
                events.append((ts, f"data length handle 0x{h:03x} tx={u16(p,6)}B/{u16(p,8)}us rx={u16(p,10)}B/{u16(p,12)}us"))
        elif ev == 0x05 and len(p) >= 7:          # Disconnection Complete
            h = u16(p, 4) & 0xFFF
            events.append((ts, f"DISCONNECT handle 0x{h:03x} reason 0x{p[6]:02x}"))
        elif ev == 0x13 and len(p) >= 3:          # Number of Completed Packets
            n = p[3]
            for i in range(n):
                h = u16(p, 4 + 2 * i) & 0xFFF
                c = u16(p, 4 + 2 * n + 2 * i)
                nocp[h].append((ts, c))
    elif typ == 1 and len(p) >= 4:               # HCI command
        op = u16(p, 1)
        if op == 0x2013 and len(p) >= 18:         # LE Connection Update
            h = u16(p, 4) & 0xFFF
            events.append((ts, f"cmd: conn update handle 0x{h:03x} interval {u16(p,6)*1.25:.2f}-{u16(p,8)*1.25:.2f}ms latency {u16(p,10)} timeout {u16(p,12)*10}ms ce {u16(p,14)*0.625:.1f}-{u16(p,16)*0.625:.1f}ms"))
        elif op == 0x2032 and len(p) >= 11:       # LE Set PHY
            h = u16(p, 4) & 0xFFF
            events.append((ts, f"cmd: set PHY handle 0x{h:03x} all={p[6]} tx=0b{p[7]:03b} rx=0b{p[8]:03b}"))
        elif op == 0x2031 and len(p) >= 7:
            events.append((ts, f"cmd: set DEFAULT PHY all={p[4]} tx=0b{p[5]:03b} rx=0b{p[6]:03b}"))
        elif op == 0x200D and len(p) >= 29:       # LE Create Connection
            events.append((ts, f"cmd: LE create connection requested interval {u16(p,17)*1.25:.2f}-{u16(p,19)*1.25:.2f}ms latency {u16(p,21)} timeout {u16(p,23)*10}ms ce {u16(p,25)*0.625:.1f}-{u16(p,27)*0.625:.1f}ms"))
        elif op == 0x2043 and len(p) >= 30:       # LE Extended Create Connection
            nph = bin(p[13]).count('1') if len(p) > 13 else 0
            events.append((ts, f"cmd: LE ext create connection (initiating PHYs mask {p[13]:03b})"))
            off = 14
            for i in range(nph):
                if off + 16 <= len(p):
                    events.append((ts, f"      PHY#{i}: interval {u16(p,off+4)*1.25:.2f}-{u16(p,off+6)*1.25:.2f}ms latency {u16(p,off+8)} timeout {u16(p,off+10)*10}ms ce {u16(p,off+12)*0.625:.1f}-{u16(p,off+14)*0.625:.1f}ms"))
                off += 16
    elif typ == 2 and len(p) >= 5:                # ACL data
        hf = u16(p, 1)
        h = hf & 0xFFF
        pb = (hf >> 12) & 3
        pl = p[5:]
        if pb in (0, 2) and len(pl) >= 4:         # start fragment
            l2len, cid = struct.unpack_from('<HH', pl, 0)
            body = pl[4:]
            if cid == 0x0005 and len(body) >= 4:  # LE signaling
                code, ident, ln = body[0], body[1], u16(body, 2)
                sig = body[4:4 + ln]
                if code == 0x14 and len(sig) >= 10:
                    psm, scid, mtu, mps, cr = struct.unpack_from('<HHHHH', sig, 0)
                    events.append((ts, f"L2CAP CoC REQUEST ({'phone->aid' if not rx else 'aid->phone'}) handle 0x{h:03x} PSM 0x{psm:04x} MTU {mtu} MPS {mps} initial credits {cr}"))
                elif code == 0x15 and len(sig) >= 10:
                    dcid, mtu, mps, cr, res = struct.unpack_from('<HHHHH', sig, 0)
                    events.append((ts, f"L2CAP CoC RESPONSE handle 0x{h:03x} MTU {mtu} MPS {mps} credits {cr} result {res}"))
                    cid_map[(h, dcid)] = 'coc'
                elif code == 0x16 and len(sig) >= 4 and False:
                    pass
            elif cid >= 0x40 and not rx and len(body) >= 2:
                sdu = struct.unpack_from('<H', body, 0)[0]
                acl_tx[(h, cid)].append((ts, sdu, l2len))
        elif pb == 1 and not rx:
            frag_count[h] += 1

print("\n=== Connections seen ===")
for h, c in conns.items():
    print(f"handle 0x{h:03x} addr {c['addr']} at {c['t']:.1f}s: interval {c['iv']*1.25:.2f} ms, latency {c['lat']}, supervision {c['to']*10} ms"
          + (f", later update {c['upd'][0]*1.25:.2f} ms / latency {c['upd'][1]} / {c['upd'][2]*10} ms" if 'upd' in c else "")
          + (f", PHY tx={PHY.get(c['phy'][0])} rx={PHY.get(c['phy'][1])}" if 'phy' in c else ", PHY unchanged (1M default)"))

print("\n=== Link events (first 60) ===")
for ts, txt in sorted(events)[:60]:
    print(f"{ts:9.2f}s  {txt}")
if len(events) > 60: print(f"... {len(events) - 60} more")

print("\n=== Audio stream (phone -> aid, L2CAP CoC data) ===")
for (h, cid), lst in acl_tx.items():
    if len(lst) < 20: continue
    times = [t for t, _, _ in lst]
    gaps = [(b - a) * 1000 for a, b in zip(times, times[1:])]
    sizes = collections.Counter(s for _, s, _ in lst)
    dur = times[-1] - times[0]
    print(f"handle 0x{h:03x} cid 0x{cid:04x}: {len(lst)} SDUs over {dur:.0f}s ({len(lst)/dur:.1f}/s)")
    print(f"   SDU sizes: {dict(sizes.most_common(4))}")
    print(f"   gap between SDUs: median {statistics.median(gaps):.1f} ms, mean {statistics.mean(gaps):.1f} ms, 95th pct {sorted(gaps)[int(len(gaps)*0.95)]:.1f} ms, max {max(gaps):.1f} ms")
    late = sum(1 for g in gaps if g > 30)
    print(f"   gaps longer than 30 ms: {late} ({100*late/len(gaps):.1f}%)")
