#!/usr/bin/env python3
"""Exclusive logged commands on the physical Zybo console; no remote network."""
import argparse, fcntl, os, re, select, subprocess, sys, termios, time, tty
from pathlib import Path
PORT='/dev/serial/by-id/usb-Digilent_Digilent_Adept_USB_Device_4103510AA655-if01-port0'
p=argparse.ArgumentParser(); p.add_argument('command',nargs='?',default=''); p.add_argument('--timeout',type=int,default=60); p.add_argument('--reboot',action='store_true'); p.add_argument('--menu',action='store_true'); a=p.parse_args()
if subprocess.run(['fuser',PORT],capture_output=True).returncode==0: raise SystemExit('UART already in use')
fd=os.open(PORT,os.O_RDWR|os.O_NOCTTY|os.O_NONBLOCK); fcntl.ioctl(fd,termios.TIOCEXCL)
old=termios.tcgetattr(fd); tty.setraw(fd); cfg=termios.tcgetattr(fd); cfg[2]=termios.CLOCAL|termios.CREAD|termios.CS8; cfg[4]=cfg[5]=termios.B115200; termios.tcsetattr(fd,termios.TCSANOW,cfg)
log=open(Path(__file__).with_name('uart.log'),'ab',buffering=0); log.write(('\nHOST '+time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())+' '+repr(a.command)+'\n').encode()); pending=b''
def send(b): os.write(fd,b)
def expect(pattern,timeout=a.timeout):
    global pending
    deadline=time.monotonic()+timeout
    while True:
        m=re.search(pattern,pending)
        if m:
            pending=pending[m.end():]; return m
        left=deadline-time.monotonic()
        if left<=0 or not select.select([fd],[],[],left)[0]: raise TimeoutError('UART wait: '+repr(pattern))
        b=os.read(fd,65536); log.write(b); sys.stdout.buffer.write(b); sys.stdout.buffer.flush(); pending+=b
try:
    send(b'\r'); m=expect(rb'(zybo login: |(?:^|\n)# )',10)
    if b'login' in m[0]: send(b'root\r'); expect(rb'(?:^|\n)# ',10)
    if a.menu:
        send(b'zybo-profile.sh\r'); expect(rb'Up/Down  Enter  Esc or q')
        send(b'\x1b[B'); expect(rb'Up/Down  Enter  Esc or q')
        send(b'\x1b[A'); expect(rb'Up/Down  Enter  Esc or q')
        send(b'\r'); expect(rb'Up/Down  Enter  Esc or q')
        send(b'\r'); expect(rb'(?:^|\n)# ')
    elif a.command:
        marker='UART_DONE_'+str(time.monotonic_ns())
        command=a.command if a.reboot else a.command+"; printf '\\n"+marker+"_%s\\n' \"$?\""
        if len(command)>1000: raise ValueError('Shell line exceeds safe console bound')
        send(command.encode()+b'\r')
        expect(rb'zybo login: ' if a.reboot else marker.encode()+rb'_\d+\r*\n')
        if not a.reboot: expect(rb'(?:^|\n)# ')
    if not a.reboot:
        send(b'exit\r'); expect(rb'zybo login: ',10)
finally:
    termios.tcsetattr(fd,termios.TCSANOW,old); os.close(fd); log.close()
