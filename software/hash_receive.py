"""Bounded TCP read-ahead into cached buffers while the FPGA consumes DMA.

Only the caller touches the mapped DMA buffer or driver. The receiver owns
two ordinary bytearrays; a buffer is returned only after its DMA-buffer copy.
No payload hashing or software fallback occurs here.
"""
import queue
import socket
import threading


def receive_prefetched(connection, hardware, length):
    if not length:
        return
    free = queue.Queue(maxsize=2)
    ready = queue.Queue(maxsize=2)
    stopped = threading.Event()
    for _ in range(2):
        free.put(bytearray(hardware.buffer_size))

    def put(target, item):
        while not stopped.is_set():
            try:
                target.put(item, timeout=.1)
                return True
            except queue.Full:
                pass
        return False

    def get(source):
        while not stopped.is_set():
            try:
                return source.get(timeout=.1)
            except queue.Empty:
                pass
        return None

    def receive():
        try:
            remaining = length
            while remaining and not stopped.is_set():
                buffer = get(free)
                if buffer is None:
                    return
                count = min(remaining, len(buffer))
                with memoryview(buffer) as view:
                    offset = 0
                    while offset < count:
                        with view[offset:count] as tail:
                            got = connection.recv_into(tail)
                        if not got:
                            raise EOFError('file ended before the declared length')
                        offset += got
                if not put(ready, (buffer, count, None)):
                    return
                remaining -= count
        except Exception as error:
            put(ready, (None, 0, error))

    worker = threading.Thread(target=receive, name='hash-tcp-prefetch', daemon=True)
    worker.start()
    try:
        remaining = length
        while remaining:
            buffer, count, error = get(ready)
            if error is not None:
                raise error
            with memoryview(buffer)[:count] as source:
                hardware.buffer[:count] = source
            # The DMA memory now owns a separate copy; network receive can
            # reuse this cached buffer while the blocking DMA ioctl executes.
            put(free, buffer)
            hardware.transfer(count)
            remaining -= count
    finally:
        stopped.set()
        if worker.is_alive():
            try:
                connection.shutdown(socket.SHUT_RD)
            except OSError:
                pass
        worker.join(2)
        if worker.is_alive():
            raise RuntimeError('TCP receiver failed to stop')
