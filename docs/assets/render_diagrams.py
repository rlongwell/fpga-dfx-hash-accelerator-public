#!/usr/bin/env python3
"""Regenerate README SVGs using the standard library and retained DFX results."""
from pathlib import Path
from html import escape
import json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

def start(width, height, title, desc):
    return [f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">
<title id="title">{escape(title)}</title><desc id="desc">{escape(desc)}</desc>
<defs>
  <linearGradient id="bg" x2="1" y2="1"><stop stop-color="#101b31"/><stop offset="1" stop-color="#101827"/></linearGradient>
  <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10Z" fill="#70d9e9"/></marker>
  <marker id="purple" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L10 5L0 10Z" fill="#c0a2ff"/></marker>
</defs>
<rect width="{width}" height="{height}" rx="20" fill="url(#bg)"/>
<g font-family="DejaVu Sans,Arial,sans-serif">''']

def text(s, x, y, value, size=16, fill="#dbe6f5", weight=400, anchor="start"):
    s.append(f'<text x="{x}" y="{y}" fill="{fill}" font-size="{size}" font-weight="{weight}" text-anchor="{anchor}">{escape(str(value))}</text>')

def rect(s,x,y,w,h,fill="#1b2c44",stroke="#405670",rx=12,extra=""):
    s.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" {extra}/>')

def line(s,path,color="#70d9e9",dashed=False):
    dash='stroke-dasharray="7 6"' if dashed else ''
    marker="purple" if color=="#c0a2ff" else "arrow"
    s.append(f'<path d="{path}" fill="none" stroke="{color}" stroke-width="2" {dash} marker-end="url(#{marker})"/>')

def save(s,name):
    (HERE/name).write_text('\n'.join(s)+"\n</g></svg>\n")

s=start(1280,720,"FPGA DFX hash accelerator architecture","A host sends files to the Zynq processing system. Linux buffers chunks in DDR; AXI DMA feeds a static framing and isolation shell, which connects to one loaded hash engine. PCAP replaces the engine between files. The digest is captured in static registers.")
text(s,40,48,"FPGA DFX HASH ACCELERATOR",14,"#70d9e9",700)
text(s,40,91,"Three algorithms. One reconfigurable region.",31,"#f4f8ff",700)
text(s,40,122,"Zybo Z7-20  /  Zynq-7020  /  64-bit AXI Stream  /  100 MHz PL clock",16,"#aabbd1")
# Boundaries and column labels.
for x,w,label,sub,col in [(40,190,"HOST","File source","#6d8dae"),(265,290,"PROCESSING SYSTEM","Static ARM + peripherals","#70d9e9"),(595,300,"STATIC LOGIC","DMA + control + isolation","#70d9e9"),(935,305,"RECONFIGURABLE","u_hash partition","#c0a2ff")]:
    rect(s,x,157,w,427,"#142238",col,14, 'stroke-dasharray="7 5"' if x==935 else '')
    text(s,x+18,188,label,14,col,700)
    text(s,x+18,212,sub,14,"#aabbd1")
rect(s,58,267,154,112)
text(s,135,302,"File client",20,"#f4f8ff",700,"middle")
text(s,135,331,"Python + TCP",15,anchor="middle")
text(s,135,355,"Digest verification",13,"#aabbd1",anchor="middle")
rect(s,285,256,250,68)
text(s,410,284,"PS Ethernet",19,"#f4f8ff",700,"middle")
text(s,410,308,"MIO → onboard PHY",14,"#aabbd1",anchor="middle")
rect(s,285,359,250,68)
text(s,410,387,"Linux service + driver",19,"#f4f8ff",700,"middle")
text(s,410,411,"Bounded 1 MiB DMA buffer",14,"#aabbd1",anchor="middle")
rect(s,285,474,250,68)
text(s,410,503,"DDR memory",19,"#f4f8ff",700,"middle")
text(s,410,527,"Chunked file transfer",14,"#aabbd1",anchor="middle")
line(s,"M212 290H285");text(s,244,248,"TCP",13,"#70d9e9",anchor="middle")
line(s,"M410 324V359");line(s,"M410 427V474")
rect(s,615,256,260,68)
text(s,745,284,"AXI Lite registers",19,"#f4f8ff",700,"middle")
text(s,745,308,"Length / status / digest latch",14,"#aabbd1",anchor="middle")
rect(s,615,359,260,84)
text(s,745,387,"Static hash shell",19,"#f4f8ff",700,"middle")
text(s,745,412,"File framing + backpressure",14,"#aabbd1",anchor="middle")
text(s,745,432,"Isolation + partition reset",14,"#aabbd1",anchor="middle")
rect(s,615,474,260,68)
text(s,745,503,"AXI DMA · MM2S",19,"#f4f8ff",700,"middle")
text(s,745,527,"DDR → AXI Stream",14,"#aabbd1",anchor="middle")
line(s,"M535 508H615");text(s,575,493,"HP0",12,"#70d9e9",anchor="middle")
line(s,"M745 474V443");line(s,"M745 324V359")
line(s,"M535 392H575V290H615");text(s,575,367,"GP0",12,"#70d9e9",anchor="middle")
# A single loaded RM with alternatives.
rect(s,955,256,265,251,"#23263f","#8c78b6")
text(s,1087,287,"ONE LOADED ENGINE",13,"#c0a2ff",700,"middle")
for y,alg,detail in [(308,"SHA3-256","Keccak-f[1600]"),(370,"SHA-256","64-round compression"),(432,"BLAKE2s-256","10-round compression")]:
    rect(s,975,y,225,52,"#2a304b","#4b4f70",8)
    text(s,1087,y+22,alg,18,"#f4f8ff",700,"middle")
    text(s,1087,y+42,detail,12,"#b9c4d9",anchor="middle")
line(s,"M875 397H955");text(s,915,382,"64-bit",12,"#70d9e9",anchor="middle")
line(s,"M1087 507V558H905V430H875")
line(s,"M850 359V324")
text(s,1087,545,"256-bit digest + status",13,"#70d9e9",anchor="middle")
# Reconfiguration is an independent control path.
line(s,"M310 427H278V615H1087V584","#c0a2ff",True)
rect(s,378,597,475,36,"#101827","#101827",0)
text(s,615,620,"PCAP · compatible partial image · between files",15,"#c0a2ff",500,"middle")
text(s,40,672,"ENGINEERING FOCUS",12,"#70d9e9",700)
text(s,235,672,"Length-aware streaming   /   Fail-closed isolation   /   Reused static routing",16,"#dbe6f5")
text(s,40,698,"TCP input path · the GUI and local ARM API use the same DMA, shell and hash partition.",13,"#8fa4bf")
save(s,"architecture.svg")

report=json.loads((ROOT/'results/dfx_summary.json').read_text())
s=start(1280,532,"Routed resource usage for three compatible DFX configurations","Stacked bars show static and reconfigurable partition LUT counts from retained Vivado 2024.2 routed reports. SHA3 uses 7193 total LUTs, SHA-256 3953, and BLAKE2s 6338. All meet 100 MHz setup timing. These are implementation results, not board measurements.")
text(s,40,48,"IMPLEMENTATION EVIDENCE",14,"#70d9e9",700)
text(s,40,88,"Static infrastructure, reused across every engine.",29,"#f4f8ff",700)
text(s,40,119,"Vivado 2024.2  /  xc7z020clg400-1  /  Full-system routed results  /  100 MHz",16,"#aabbd1")
rect(s,40,144,15,15,"#486780","#486780",3);text(s,64,157,"Static logic",14)
rect(s,181,144,15,15,"#70d9e9","#70d9e9",3);text(s,205,157,"Reconfigurable engine",14)
text(s,1000,187,"TOTAL LUTs",12,"#aabbd1",700,"middle")
text(s,1163,187,"SETUP SLACK",12,"#aabbd1",700,"middle")
for n,(key,label) in enumerate([('sha3','SHA3-256'),('sha256','SHA-256'),('blake2s','BLAKE2s-256')]):
    y=225+n*86
    row=report['configurations'][key]
    text(s,40,y+20,label,20,"#f4f8ff",700)
    scale=700/8000
    a=row['static']['luts']*scale;b=row['rp']['luts']*scale
    rect(s,225,y,700,34,"#1a2940","#1a2940",4)
    rect(s,225,y,a,34,"#486780","#486780",0)
    rect(s,225+a,y,b,34,"#70d9e9","#70d9e9",0)
    text(s,225+a/2,y+23,f"{row['static']['luts']:,}",14,"#ffffff",700,"middle")
    text(s,225+a+b/2,y+23,f"{row['rp']['luts']:,}",14,"#112437",700,"middle")
    text(s,1000,y+24,f"{row['total']['luts']:,}",25,"#f4f8ff",700,"middle")
    text(s,1163,y+24,f"+{row['timing']['wns_ns']:.3f} ns",22,"#99e6be",700,"middle")
for value in (0,2000,4000,6000,8000):
    text(s,225+value*700/8000,451,f'{value:,}',12,"#8fa4bf",anchor="middle")
text(s,575,474,"Routed LUT count",13,"#aabbd1",anchor="middle")
text(s,40,510,"Routed implementation · results/dfx_summary.json · all three configurations passed timing and static compatibility checks.",13,"#8fa4bf")
save(s,"implementation.svg")
print('Generated docs/assets/architecture.svg and implementation.svg')
