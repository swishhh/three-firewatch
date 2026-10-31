"""Undo / redo history for the editor (Ctrl+Z / Ctrl+Y)."""
import time

LIMIT = 100
MERGE_SECONDS = 1.5


class UndoStack:
    def __init__(self, on_change=None):
        self.done = []
        self.undone = []
        self.on_change = on_change

    def push(self, label, undo, redo, merge_key=None):
        """Record an action already performed. Consecutive actions with the same `merge_key` (e.g. one
        slider drag) within a moment of each other become one step."""
        now = time.monotonic()
        if merge_key is not None and self.done:
            last = self.done[-1]
            if last['key'] == merge_key and now - last['time'] < MERGE_SECONDS:
                last['redo'], last['time'] = redo, now
                self.undone.clear()
                self._changed()
                return
        self.done.append({'label': label, 'undo': undo, 'redo': redo, 'key': merge_key, 'time': now})
        del self.done[:-LIMIT]
        self.undone.clear()
        self._changed()

    def undo(self):
        if not self.done:
            return None
        action = self.done.pop()
        action['undo']()
        self.undone.append(action)
        self._changed()
        return action['label']

    def redo(self):
        if not self.undone:
            return None
        action = self.undone.pop()
        action['redo']()
        action['key'] = None  # never merge into a redone step
        self.done.append(action)
        self._changed()
        return action['label']

    def clear(self):
        self.done.clear()
        self.undone.clear()
        self._changed()

    def _changed(self):
        if self.on_change is not None:
            self.on_change()
