"""Exclusive, bounded UART console operations for the local desktop demo."""
import fcntl
import hashlib
import os
from pathlib import Path
import re
import secrets
import select
import shlex
import subprocess
import termios
import time
import tty

PORT = '/dev/serial/by-id/usb-Digilent_Digilent_Adept_USB_Device_4103510AA655-if01-port0'
LOGIN = rb'(?:^|\n)\r*zybo login: '
PROMPT = rb'(?:^|\n)\r*# '


class Cancelled(Exception):
    pass


class Console:
    def __init__(self, log):
        self.log, self.fd, self.pending, self.original = log, None, bytearray(), None

    def __enter__(self):
        if not Path(PORT).is_char_device():
            raise RuntimeError('Zybo USB UART is disconnected. Check power and the J12 cable.')
        if subprocess.run(['fuser', PORT], capture_output=True).returncode == 0:
            raise RuntimeError('UART is in use. Close your serial terminal before connecting.')
        self.fd = os.open(PORT, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        try:
            fcntl.ioctl(self.fd, termios.TIOCEXCL)
            self.original = termios.tcgetattr(self.fd)
            tty.setraw(self.fd)
            config = termios.tcgetattr(self.fd)
            config[2] = termios.CLOCAL | termios.CREAD | termios.CS8
            config[4] = config[5] = termios.B115200
            termios.tcsetattr(self.fd, termios.TCSANOW, config)
            self.send(b'\r')
            self.expect(LOGIN, 6)
            self.send(b'root\r')
            self.expect(PROMPT, 6)
            return self
        except Exception:
            self.close()
            raise

    def close(self):
        if self.fd is not None:
            try:
                if self.original is not None:
                    termios.tcsetattr(self.fd, termios.TCSANOW, self.original)
            finally:
                os.close(self.fd)
                self.fd = None

    def __exit__(self, *_):
        try:
            self.send(b'\r')
            self.expect(PROMPT, 12)
            self.send(b'exit\r')
            self.expect(LOGIN, 6)
        finally:
            self.close()

    def send(self, data):
        view = memoryview(data)
        while view:
            if not select.select([], [self.fd], [], 8)[1]:
                raise TimeoutError('The UART stopped accepting data.')
            try:
                view = view[os.write(self.fd, view):]
            except BlockingIOError:
                continue

    def expect(self, pattern, timeout):
        regex = re.compile(pattern)
        deadline = time.monotonic() + timeout
        while True:
            match = regex.search(self.pending)
            if match:
                before = bytes(self.pending[:match.start()])
                matched = bytes(self.pending[match.start():match.end()])
                del self.pending[:match.end()]
                return before, matched
            left = deadline - time.monotonic()
            if left <= 0 or not select.select([self.fd], [], [], left)[0]:
                raise TimeoutError('Board response timed out. Reconnect after the console returns to login.')
            data = os.read(self.fd, 4096)
            if not data:
                raise OSError('USB UART disconnected.')
            self.log.write(data)
            self.log.flush()
            self.pending.extend(data)
            if len(self.pending) > 256 * 1024:
                raise RuntimeError('Unexpectedly large board response.')

    def command(self, command, timeout=30):
        token = 'DEMO_CMD_' + secrets.token_hex(8)
        wire = command + "; printf '\\n" + token + "_%s\\n' \"$?\""
        if len(wire.encode()) > 950:
            raise ValueError('Console command exceeds the safe line length.')
        self.send(wire.encode() + b'\r')
        before, marker = self.expect(rb'(?m)^' + token.encode() + rb'_\d+\r*\n', timeout)
        self.expect(PROMPT, 6)
        status = int(marker.strip().rsplit(b'_', 1)[1])
        if status:
            raise RuntimeError('Board command failed: ' + before.decode(errors='replace')[-1200:])
        return before.decode(errors='replace')

    def upload(self, source, destination, progress=lambda *_: None, cancelled=lambda: False):
        """Checksum-verified raw transfer; never overwrites an existing file.

        Same console protocol as the user's zybo-file-transfer helper: raw
        bounded head, restore terminal, SHA-256, publish only a verified file.
        """
        source = Path(source)
        size = source.stat().st_size
        with source.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        token = 'DEMO_UP_' + secrets.token_hex(8)
        command = (
            f'd={shlex.quote(destination)}; u={token}; '
            'if [ -e "$d" ] || [ -L "$d" ]; then echo "${u}_EXISTS"; '
            'elif s=$(stty -g) && t=$(mktemp /tmp/zybo-demo-upload-XXXXXX); then '
            'stty raw -echo min 0 time 80; printf \'\\n%s_READY\\n\' "$u"; '
            f'head -c {size} > "$t"; stty "$s"; h=$(sha256sum "$t"); '
            f'if [ "${{h%% *}}" = {digest} ] && mv -nT "$t" "$d" && [ ! -e "$t" ]; '
            'then echo "${u}_DONE"; else rm -f "$t"; echo "${u}_FAILED"; fi; '
            'else echo "${u}_FAILED"; fi'
        )
        self.send(command.encode() + b'\r')
        pattern = rb'(?m)^' + token.encode() + rb'_(?:READY|DONE|EXISTS|FAILED)\r*\n'
        _, marker = self.expect(pattern, 8)
        if b'_READY' not in marker:
            self.expect(PROMPT, 6)
            raise RuntimeError('Board temporary upload destination is unavailable.')
        interrupted = False
        with source.open('rb') as stream:
            sent = 0
            while sent < size:
                if cancelled():
                    interrupted = True
                    break
                block = stream.read(min(1024, size - sent))
                if not block:
                    raise EOFError('Local payload changed during transfer.')
                self.send(block)
                termios.tcdrain(self.fd)
                sent += len(block)
                progress(sent, size)
        _, marker = self.expect(pattern, 20)
        self.expect(PROMPT, 6)
        if interrupted:
            raise Cancelled('Transfer cancelled; the temporary receiver has stopped.')
        if b'_DONE' not in marker:
            raise RuntimeError('The UART transfer failed its SHA-256 check.')
        return digest

    def agent(self, path, arguments, event):
        self.send(('python3 -u ' + shlex.quote(path) + ' ' + arguments).encode() + b'\r')
        done, error = False, None
        while not done:
            _, line = self.expect(rb'(?m)^@ZYBO_DEMO [^\n]*\n', 120)
            import json
            message = json.loads(line[len(b'@ZYBO_DEMO '):].strip())
            event(message)
            if message['event'] in ('done', 'error'):
                done = True
                if message['event'] == 'error':
                    error = message['message']
        self.expect(PROMPT, 8)
        if error:
            raise RuntimeError(error)
