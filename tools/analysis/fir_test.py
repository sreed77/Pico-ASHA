import re, math, sys
src = open(sys.argv[1]).read()
body = src[src.index('asha_fir_coefficients[ASHA_FIR_NUM_TAPS] = {'):]
body = body[body.index('{')+1: body.index('};')]
h = [int(x) for x in re.findall(r'-?\d+', body)]
N = 253; assert len(h) == N, len(h)
print("taps", len(h), "sum", sum(h), "symmetric", all(h[i]==h[N-1-i] for i in range(N)))
def sat(v): return max(-32768, min(32767, v))
class Dec:
    def __init__(s): s.state = [0]*(N+48-1)
    def block(s, x48):
        st = s.state
        for i in range(48): st[N-1+i] = x48[i]
        out = []
        half = (N-1)//2
        for o in range(16):
            sm = st[o*3:]
            even = sm[half]*h[half]; odd = 0
            for c in range(0, half, 2):
                even += (sm[c] + sm[N-1-c]) * h[c]
                odd  += (sm[c+1] + sm[N-2-c]) * h[c+1]
            out.append(sat((even+odd) >> 15))
        for i in range(N-1): st[i] = st[48+i]
        return out
def run(sig):
    d = Dec(); out = []
    for b in range(len(sig)//48): out += d.block(sig[b*48:(b+1)*48])
    return out
def ref(sig):
    # direct-form reference: y[m] = sum_k h[k]*x[3m+(N-1)-k] with zero history, same as the block code
    x = [0]*(N-1) + sig
    return [sat(sum(h[k]*x[3*m + (N-1) - k] for k in range(N)) >> 15) for m in range(len(sig)//3)]
# 1) block implementation vs direct convolution
import random
random.seed(1)
sig = [int(8000*math.sin(2*math.pi*1000*i/48000) + 6000*math.sin(2*math.pi*3300*i/48000) + random.randint(-2000,2000)) for i in range(48*60)]
a, r = run(sig), ref(sig)
print("block code equals direct convolution:", a == r, "(max diff", max(abs(p-q) for p,q in zip(a,r)), ")")
# 2) 1 kHz sine, check output is a clean sine delayed by 42 samples
amp = 20000
sig = [int(amp*math.sin(2*math.pi*1000*i/48000)) for i in range(48*80)]
o = run(sig)
ideal = [amp*math.sin(2*math.pi*1000*(3*m - 126)/48000) for m in range(len(o))]
err = [o[m]-ideal[m] for m in range(60, len(o))]   # skip start-up
print("1 kHz sine: max error vs ideal %.1f (of %d), rms error %.2f" % (max(abs(e) for e in err), amp, math.sqrt(sum(e*e for e in err)/len(err))))
# 3) full-scale square-ish / clipping stress, check for wraparound: output must stay within +-32767 and track sign
sig = [32767 if (i//24)%2==0 else -32768 for i in range(48*80)]
o = run(sig)
print("full-scale square: output min %d max %d (saturated samples: %d)" % (min(o), max(o), sum(1 for v in o if v in (32767,-32768))))
# 4) DC gain
o = run([10000]*(48*20))
print("DC 10000 in -> %d out (settled)" % o[-1])
# 5) frequency response at a few points
for f in (500, 3000, 6000, 6800, 7000, 7280, 7800, 9000, 12000):
    amp=10000; sig=[amp*math.sin(2*math.pi*f*i/48000) for i in range(48*60)]
    o=run([int(v) for v in sig]); pk=max(abs(v) for v in o[60:]); print("  %5d Hz: gain %.2f dB" % (f, 20*math.log10(pk/amp)))
