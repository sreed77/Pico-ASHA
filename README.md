# Fork notes (sreed77/Pico-ASHA, branch `experiment/conn-params`)

**Start here.** This fork is a working record of an investigation into audio
stutter when streaming PC audio to two Cochlear Nucleus 8 (CP1110) processors
with a Pico 2 W on Windows 11. The upstream project is
[shermp/Pico-ASHA](https://github.com/shermp/Pico-ASHA). The original README
follows after this section.

## Where things are

| Branch | What it holds |
|---|---|
| `experiment/conn-params` (this one) | Everything: release button, link experiments, statistics, the diagnostic build modes, analysis scripts, the troubleshooter and the docs page. |
| `feature/release-button-led` | A physical "release" button and LED patterns (earlier work, separate). |
| `contrib/acp-conn-param-status` | Clean change for upstream: send ACP status `03 02 10` after connecting, like Android. |
| `contrib/link-diagnostics` | Clean change for upstream: `PICO_ASHA_LINK_STATS`, `PICO_ASHA_CONN_LATENCY`, `PICO_ASHA_SUPERVISION_TIMEOUT`, `PICO_ASHA_REQUEST_2M_PHY`, all off or unchanged by default. |
| `contrib/troubleshooting-docs` | Clean change for upstream: `website/docs/troubleshooting.md` and `tools/Pico-ASHA-Troubleshoot.ps1`. |

`main` tracks upstream. The `contrib/*` branches start from upstream's
`main` (c5fd3e5) so they can become pull requests. They do not carry this
README.

Details of the findings are in `website/docs/troubleshooting.md`.

## Where the work stands

* Setup: Windows 11, Pico 2 W, two Cochlear Nucleus 8 (CP1110, firmware
  11.0.11.1), an Android phone used as the reference.
* Result: with the ACP `03 02 10` write, a 4 s supervision timeout and a 2M PHY
  request, a 4 minute run had 3 bad ear-seconds out of 480 (0.6%), no USB
  underruns, no clock drift, peak level 79%. Before that, audio went choppy
  after a few minutes. Not isolated: which of those three changes matters.
* Still open: a slight degradation about every 30 s that the link and USB
  statistics do not show. The user judged it "95% there" and stopped chasing it.
* Ruled out: radio link and encoder (replaying recorded phone packets and
  recorded phone audio through the Pico encoder were clean), the 48 kHz to
  16 kHz decimation filter (verified offline), USB feed, clipping.
* Windows stores the Pico playback format as 48 kHz. Offering only 16 kHz
  breaks stream start ("audio renderer error"). Do not use the 16 kHz-only mode
  on a PC that already knows the device.

## Build options added in this branch

| CMake option | Default | Purpose |
|---|---|---|
| `PICO_ASHA_LINK_STATS` | OFF | Per-second link and USB statistics as `ShortLog` lines. |
| `PICO_ASHA_CONN_LATENCY` | 10 | Latency requested when connecting. |
| `PICO_ASHA_SUPERVISION_TIMEOUT` | 100 | Supervision timeout in 10 ms units (400 = 4 s). |
| `PICO_ASHA_REQUEST_2M_PHY` | OFF | Ask the controller for the 2M PHY. |
| `PICO_ASHA_TEST_TONE` | OFF | Ignore USB audio, stream a 1 kHz tone. |
| `PICO_ASHA_REPLAY` | OFF | Replay recorded G.722 packets from `replay-data/replay_sdus.c`. |
| `PICO_ASHA_REPLAY_PCM` | OFF | Encode recorded PCM from `replay-data/replay_pcm.c` with the Pico encoder. |
| `PICO_ASHA_USB_16K_ONLY` | OFF | Advertise only 16 kHz on USB. See the warning above. |
| `PICO_ASHA_PCM_ATTEN_SHIFT` | 0 | Lower incoming USB audio by 6 dB per step. |

The ACP `03 02 10` write is always on in this branch (no option).

The replay modes need `replay-data/*.c` files built from a private Android
capture. Those files are **not** in the repository and must never be
committed. `tools/analysis/` has the scripts that make them (see below). The
replay data must go in flash (`__in_flash("replay")`) because the build uses
`PICO_COPY_TO_RAM=1` and RAM is only 512 KB.

## Statistics line format

Sent once a second while streaming, only with `PICO_ASHA_LINK_STATS`:
`L n50 g22 c4 t3` (packets, longest gap ms, lowest credits, main-loop stall ms),
`L a50 k45` (over-the-air acks, longest ack gap ms),
`usb u0 f4-4 d0 r48 p42` (underruns, buffer fill, lateness ms, rate kHz, peak %),
and `link`, `upd`, `phy`, `setphy`, `dle` lines on connection events.
Text must fit the 32 byte `ShortLog`, and the compiler format-truncation
check is an error, so use `uint8`/`uint16` values or `% 100U`.

## Experiment builds (what each letter was)

The test builds were named `vA` to `vO`. Rebuild one by passing the options.

| Build | Options |
|---|---|
| v0 | baseline plus logging |
| vA | latency 0 |
| vB | latency 0, timeout 400 |
| vC | latency 0, timeout 400, 2M PHY |
| vD | 2M PHY only |
| vE | 2M PHY plus statistics |
| vF | 2M PHY, timeout 400, main-loop stall detection |
| vG | adds USB statistics |
| vH / vI / vJ | test tone / tone with ack statistics / tone with the `03 02 10` write |
| vK | live PC audio, `03 02 10` write, 2M PHY, timeout 400, rate and peak readout |
| vL | replay of recorded packets (private data) |
| vM | recorded PCM through the Pico encoder (private data) |
| vN | live audio, 16 kHz only (fails on Windows, see above) |
| vO | as vK with the input lowered by 6 dB |

The best result so far is vK.

## How to build (Windows)

The toolchain is a local folder, not in the repository: `pico-sdk` 2.2.0,
the Arm GNU toolchain, picotool and pioasm. With those paths set:

```powershell
$t = '<toolchain folder>'
$env:PICO_SDK_PATH = "$t\pico-sdk"; $env:PICO_TOOLCHAIN_PATH = "$t\arm-gnu"
$env:picotool_DIR = "$t\picotool\picotool"; $env:pioasm_DIR = "$t\sdk-tools\pioasm"
$env:PATH = "$t\arm-gnu\bin;$env:PATH"
cmake -G Ninja -B build -DPICO_BOARD=pico2_w -DCMAKE_BUILD_TYPE=Release "-Dpioasm_DIR=$t\sdk-tools\pioasm" -DPICO_ASHA_LINK_STATS=ON -DPICO_ASHA_REQUEST_2M_PHY=ON -DPICO_ASHA_SUPERVISION_TIMEOUT=400
cmake --build build
```

Pass each option as a separate argument. Flash by holding BOOTSEL and copying
`build\pico_asha.uf2` to the drive.

## Tools

* `tools/Pico-ASHA-Troubleshoot.ps1`: read-only Windows troubleshooter. Needs a
  firmware built with `PICO_ASHA_LINK_STATS=ON`. Close the GUI and any control
  app tab first (one program per serial port). It finds bad seconds by itself
  and writes a report and CSV. `-SelfTest` checks the parser.
* `tools/analysis/` (Python 3, standard library only, run with `python -I`):
  * `btsnoop_analyze.py <btsnoop_hci.log>`: how a phone connects and streams
    (connection settings, PHY, L2CAP, packet gaps).
  * `att_writes.py`: GATT writes the phone sends (ACP, volume).
  * `nocp_phone2.py`: acknowledgement timing in a capture.
  * `extract_sdus.py`, `make_pcm.py`: pull the audio packets out of a capture
    and decode them (needs ffmpeg) to make the `replay-data` files.
  * `fir_test.py`: checks the 48 kHz to 16 kHz filter against a reference.

## Upstream

Open upstream work seen on 2026-11-10: #68 (continuous streaming mode, touches
the same files), #61, #50, #30. Related issues: #54 (occasional tiny cutouts),
#48, #47. The plan is to propose `contrib/acp-conn-param-status` as a pull
request and offer the diagnostics and docs in an issue first. Draft texts are
kept outside the repository. Cochlear Nucleus 8 is already listed as Working
in the status table below.

## Private data

Never commit: Bluetooth captures, Android bug reports, `replay-data/`, replay
firmware builds, troubleshooter reports (they contain device addresses) or
anything with the user's phone details.

---

# Pico ASHA

Pico ASHA is an attempt to implement Android's Audio Streaming for Hearing Aids (ASHA) protocol on a Raspberry Pi Pico W microcontroller.

Visit the [website](https://shermp.github.io/Pico-ASHA) for documentation.

## Status

**This project is in Beta.** Currently, it is possible to discover and stream audio to several hearing aid models, see the device status table below for details.

### Device Status

| Device | Status |
| --- | --- |
| Audio Service R S 7.6 | Working |
| Cochlear Baha 6 Max | Working |
| Cochlear Nucleus 7 | Working |
| Cochlear Nucleus 8 | Working |
| MED-EL SONNET 3 | Working |
| Oticon More 2 | Working |
| Philips HearLink 9030 | Working |
| Philips HearLink 9050 | Working |
| Signia 5AX | Working |
| Signia Pure Charge&Go T 7AX | Working |
| Sonic Radiant SE 60 | Working |
| Starkey Arc AI | Can Pair, but not open L2CAP CoC Connection |
| Widex Moment 220 | Working |

**It should be safe, but I cannot guarantee it will not mess up your hearing aids!**

## Licence

Unless otherwise noted in the file, the source code in this repository is licenced under the BSD 3-clause licence, however any binaries must be provided on a more restrictive licence, see below.

Pico-ASHA uses [BTstack by BlueKitchen](https://github.com/bluekitchen/btstack), which in general has a non-commercial free licence available. Raspberry Pi have provided a [commercial licence](https://github.com/raspberrypi/pico-sdk/blob/master/src/rp2_common/pico_btstack/LICENSE.RP) if using BTstack on official Raspberry Pi Pico W or WH. If Pico-ASHA is implemented on any other device, then the terms of the original BlueKitchen BTstack licence MUST be adhered to.
