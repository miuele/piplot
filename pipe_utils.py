import os
import selectors
from collections import deque

def nonblocking_opener(file, flags):
    return os.open(file, flags | os.O_NONBLOCK)

class SelectorReader:
    def __init__(self, selector=selectors.DefaultSelector()):
        self._selector = selector

    def register(self, file):
        self._selector.register(file, selectors.EVENT_READ)

    def unregister(self, file):
        self._selector.unregister(file)

    def __len__(self):
        return len(self._selector.get_map())

    def select(self, timeout=None):
        for key, events in self._selector.select():
            if events & selectors.EVENT_READ != 0:
                yield key.fileobj

    def close(self):
        self._selector.close()

class LineBuffer:

    def __init__(self, text=None, *, linesep='\n'):
        self._lines = deque()
        self._stash = []
        self._linesep = linesep
        if text is not None:
            self.write(text)

    def write(self, s):
        lines = s.split(self._linesep)
        self._stash.append(lines[0])
        if len(lines) > 1:
            self._lines.append(''.join(self._stash))
            self._lines.extend(lines[1:-1])
            self._stash = [lines[-1]]

    def readline(self):
        if len(self._lines) == 0:
            return None

        return self._lines.popleft()

    def lines(self):
        while line := self.readline():
            yield line

    def num_lines(self):
        return len(self._lines)

    @property
    def leftover(self):
        self._stash = [''.join(self._stash)]
        return self._stash[0]

