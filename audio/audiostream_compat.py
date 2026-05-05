import threading
from array import array

import pyaudio

MAX_16BITS = 32767
MIN_16BITS = -32768


class OutputStream:
    def __init__(self, channels, rate, buffersize):
        self.channels = channels
        self.rate = rate
        self.buffersize = buffersize
        self.sources = []
        self._source_buffers = {}
        self._lock = threading.Lock()

        self._pa = pyaudio.PyAudio()
        self._stream = self._pa.open(
            format=pyaudio.paInt16,
            channels=channels,
            rate=rate,
            output=True,
            frames_per_buffer=buffersize,
            stream_callback=self._callback,
        )

    def _callback(self, in_data, frame_count, time_info, status):
        needed_bytes = frame_count * 2  # int16 = 2 bytes per sample

        with self._lock:
            if not self.sources:
                return (b'\x00\x00' * frame_count, pyaudio.paContinue)

            for src in self.sources:
                buf = self._source_buffers[id(src)]
                while len(buf) < needed_bytes:
                    raw = src.get_bytes()
                    if raw:
                        buf.extend(raw)
                    else:
                        buf.extend(b'\x00\x00' * frame_count)
                        break

            mixed = [0] * frame_count
            for src in self.sources:
                buf = self._source_buffers[id(src)]
                chunk = array('h', bytes(buf[:needed_bytes]))
                del buf[:needed_bytes]
                for i in range(frame_count):
                    s = mixed[i] + chunk[i]
                    if s > MAX_16BITS:
                        s = MAX_16BITS
                    elif s < MIN_16BITS:
                        s = MIN_16BITS
                    mixed[i] = s

        return (array('h', mixed).tobytes(), pyaudio.paContinue)

    def register_source(self, source):
        with self._lock:
            self.sources.append(source)
            self._source_buffers[id(source)] = bytearray()

    def start(self):
        self._stream.start_stream()


def get_output(channels, rate, buffersize):
    stream = OutputStream(channels, rate, buffersize)
    stream.start()
    return stream


class ThreadSource:
    def __init__(self, output_stream, *args, **kwargs):
        self.output_stream = output_stream

    def start(self):
        self.output_stream.register_source(self)

    def get_bytes(self):
        return b''
