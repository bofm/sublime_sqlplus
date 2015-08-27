import sys
import subprocess
import queue
import os
import signal
import threading
import weakref
import types
from functools import wraps
from collections import namedtuple, deque


class CommandLineWrapper:
    """Wraps a command line application. Redirects stdin, stdout and stderr
       through pipes. Reads stdout and stderr asynchronously.

    >>> c = CommandLineWrapper('cmd', encoding='cp866')
    >>> c.stop()
    >>> c.communicate('echo Hello World!')
    Traceback (most recent call last):
        ...
    RuntimeError: The process is not running.
    >>> c.start()
    >>> out = c.communicate('echo Hello World!')
    >>> assert 'Hello World!' in out
    >>> out = c.communicate('AaaazzzZ')
    >>> assert c._STDERR_PREFIX in out
    >>> c.stop()
    >>> c.stop()
    Traceback (most recent call last):
        ...
    RuntimeError: The process is not running.
    >>> c.start()
    >>> c.start()
    Traceback (most recent call last):
        ...
    RuntimeError: Already started.
    >>> c.stop()

    Context manager
    >>> cc = None
    >>> with CommandLineWrapper('cmd', encoding='cp866') as c:
    ...     cc = c
    ...     assert 'AAAAAA' in c.communicate('echo AAAAAA')
    >>> assert not cc.is_running

    """

    _CHANNELS = namedtuple('CHANNELS', 'stdout stderr')(1, 2)
    _STDERR_PREFIX = 'STDERROR=> '

    def __init__(self, *process_args, workdir=None, encoding='utf-8', start=True, startupinfo=None):
        if startupinfo is None and sys.platform == 'win32':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        self._startupinfo = startupinfo
        self._process = None
        self._workdir = workdir
        self._encoding = encoding
        self._process_args = process_args
        self._q = queue.Queue()
        self._handlers = weakref.WeakValueDictionary()
        if start:
            self.start()

    def start(self):
        if self.is_running:
            raise RuntimeError('Already started.')
        self._process = subprocess.Popen(self._process_args,
                                         stdin=subprocess.PIPE,
                                         stdout=subprocess.PIPE,
                                         stderr=subprocess.PIPE,
                                         cwd=self._workdir,
                                         startupinfo=self._startupinfo,
                                         bufsize=0)
        self._handle_output(self._CHANNELS.stdout, self._process.stdout)
        self._handle_output(self._CHANNELS.stderr, self._process.stderr)

    def stop(self):
        self._raise_if_not_running()
        self._process.terminate()
        self._process.wait()
        self._process = None

    def kill(self):
        if sys.platform == 'win32':
            import _winapi
            handle = _winapi.OpenProcess(1, False, self._process.pid)
            _winapi.TerminateProcess(handle, -1)
            _winapi.CloseHandle(handle)
        else:
            os.kill(self.process.pid, signal.SIGKILL)

    def _create_handler(self, channel, buffer):
        encoding = self._encoding
        buffer = weakref.proxy(buffer)
        self = weakref.proxy(self)

        def handler():
            with open(buffer.fileno(), 'rb', closefd=False) as output:
                try:
                    while (self.is_running and not self._q.full()):
                        buf = output.read1(8192)
                        if buf:
                            try:
                                text = str(buf, encoding)
                                text = text.replace('\r', '')  # Windows
                            except UnicodeDecodeError:
                                print('\nWrong encoding: %s\n' % encoding)
                                raise
                            item = (channel, text)
                            self._q.put(item)
                except ReferenceError:
                    return
        return handler

    def _handle_output(self, channel, buffer):
        if channel in self._handlers:
            raise RuntimeError('Channel %s is already handled.' % channel)
        handler = self._create_handler(channel, buffer)
        started_handler = self._run_handler(handler)
        if not started_handler:
            raise RuntimeError('_run_handler() must return an object')
        self._handlers[channel] = started_handler

    def _run_handler(self, handler):
        threaded_handler = threading.Thread(target=handler, daemon=True)
        threaded_handler.start()
        return threaded_handler

    def item_to_text(self, item):
        channel, text = item
        if channel == self._CHANNELS.stderr:
            text = self._STDERR_PREFIX + text.replace('\n', '\n' + self._STDERR_PREFIX)
        return text

    def _gen_output(self, timeout=0.1):
        try:
            while self.is_running:
                item = self._q.get(timeout=timeout)
                yield self.item_to_text(item)
        except queue.Empty:
            raise StopIteration

    def get_output(self, timeout=0.1):
        self._raise_if_not_running()
        return ''.join(item for item in self._gen_output(timeout))

    def run_command(self, command):
        self._raise_if_not_running()
        self._process.stdin.write(bytes(str(command) + '\n', self._encoding))

    def communicate(self, input=None):
        if input:
            self.run_command(input)
        return self.get_output()

    def _raise_if_not_running(self):
        if not self.is_running:
            raise RuntimeError('The process is not running.')

    @property
    def is_running(self):
        if self._process is None:
            return False
        return self._process.poll() is None

    def __enter__(self):
        if not self.is_running:
            self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.is_running:
            self.stop()

    def __del__(self):
        try:
            self.stop()
        except:
            pass


class History:
    """
    >>> h = History()

    >>> class Foo:
    ...     @staticmethod
    ...     @h
    ...     def spam(x):
    ...         print(x)

    >>> a = Foo()
    >>> a.spam('one')
    one
    >>> a.spam('two')
    two
    >>> h.add('three')
    >>> print(list(h.items))
    ['one', 'two', 'three']
    >>> h.get_prev()
    'three'
    >>> h.get_next()
    'three'
    >>> h.get_prev()
    'two'
    >>> h.get_next()
    'three'
    >>> h.get_prev()
    'two'
    >>> h.get_prev()
    'one'
    >>> h.get_prev()
    'one'
    >>> h.get_next()
    'two'
    >>> h.get_next()
    'three'
    >>> h.get_next()
    'three'
    >>> h.add('three')
    >>> print(list(h.items))
    ['one', 'two', 'three']
    """

    def __init__(self, maxlen=999):
        self.items = deque(maxlen=maxlen)
        self._index = 0

    def add(self, item):
        if not item:
            return
        if not self.items or self.items[-1] != item:
            self.items.append(item)
            self._index = len(self.items)

    def get_prev(self):
        if not self.items:
            return None
        self.index -= 1
        return self.items[self.index]

    def get_next(self):
        if not self.items:
            return None
        self.index += 1
        if self.index >= len(self.items):
            return self.items[-1]
        return self.items[self.index]

    @property
    def index(self):
        return self._index

    @index.setter
    def index(self, val):
        if 0 <= val < len(self.items):
            self._index = val

    def __call__(self, fn):
        @wraps(fn)
        def wrapper(a):
            self.add(a)
            return fn(a)
        return wrapper
