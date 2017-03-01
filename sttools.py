from threading import Thread
from functools import wraps, partial
from concurrent.futures import ThreadPoolExecutor

import sublime
import sublime_plugin


class _Singleton(type):

    def __init__(self, *args, **kwargs):
        self.__instance = None
        super().__init__(*args, **kwargs)

    def __call__(self, *args, **kwargs):
        if self.__instance is None:
            self.__instance = super().__call__(*args, **kwargs)
        return self.__instance


class Settings(metaclass=_Singleton):

    def __init__(self, filename):
        self.filename = filename

    def __call__(self, name):
        return sublime.load_settings(self.filename).get(name)

    def __getattr__(self, name):
        return self.__call__(name)


def get_selected_region(view):
    regions = view.sel()
    if len(regions) > 1:
        raise LookupError(
            "Too many selection regions (%i). Must be 1." % len(regions))
    region = regions[0]
    return region


def insert_at(view, position, string):
    view.run_command('zz_insert', {
        'position': position,
        'string': str(string)
    })


def insert(view, string):
    """Inserts at the end of selection"""
    region = get_selected_region(view)
    insert_at(view, region.end(), string)


def replace_selected(view, string):
    region = get_selected_region(view)
    replace(view, region.begin(), region.end(), string)
    view.sel().clear()
    view.sel().add(sublime.Region(region.begin(), region.begin() + len(string)))


def replace(view, start, end, string):
    view.run_command('zz_replace', {
        'start': start,
        'end': end,
        'string': str(string)
    })


def move_cursor(view, position):
    view.sel().clear()
    view.sel().add(sublime.Region(position, position))


def after_insert(view, start, end=None):
    # !!!!!!!!!!!!!!!  use view.show() !!!!!!!!!!!!!!!!
    if end is None:
        end = start
    # Clear the selection and put the cursor on the end of the region
    if any(s.begin() <= end for s in view.sel()):
        # Only if the cursor is before insertion
        move_cursor(view, end)

    # Move the viewport to the end of the inserted text
    screen_height = view.viewport_extent()[1]
    new_view_end = view.text_to_layout(end)[1]  # Y coordinate only
    new_view_start = new_view_end - screen_height + 50
    if not new_view_start < view.viewport_position()[1] < new_view_end:
        # Only if inserted text is not already visible
        view.set_viewport_position((0, new_view_start))


class ZzReplaceCommand(sublime_plugin.TextCommand):

    def run(self, edit, start, end, string):
        self.view.replace(edit, sublime.Region(start, end), string)


class ZzInsertCommand(sublime_plugin.TextCommand):

    def run(self, edit, position, string):
        self.view.insert(edit, position, string)
        after_insert(self.view, position + len(string))


class Activity:

    def __init__(self, view, id, message):
        self.id = id
        self.view = view
        self.message = message
        self._finished = False

    def __enter__(self):
        self.animate_activity()

    def __exit__(self, type, value, traceback):
        self._finished = True
        self.view.erase_status(self.id)
        self.view = None

    def animate_activity(self, i=0, x=1):
        if self._finished:
            return
        # This animates a little activity indicator in the status area
        before = i % 8
        after = (7) - before
        if not after:
            x = -1
        if not before:
            x = 1
        i += x
        self.view.set_status(self.id, '%s [%s=%s]' % (
            self.message, ' ' * before, ' ' * after))
        sublime.set_timeout(lambda: self.animate_activity(i, x), 100)


def async(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        sublime.set_timeout_async(partial(fn, *args, **kwargs))
    return wrapper


def threaded(fn, start=True):
    @wraps(fn)
    def run(*args, **kwargs):
        t = Thread(target=fn, args=args, kwargs=kwargs, daemon=True)
        if start:
            t.start()
        return t
    return run


executor = None


def thread_pool(fn):
    @wraps(fn)
    def run(*args, **kwargs):
        global executor
        if executor is None:
            executor = ThreadPoolExecutor(max_workers=8)
        future = executor.submit(fn, *args, **kwargs)
        return future
    return run


class classproperty(property):
    """https://docs.python.org/3.3/howto/descriptor.html?highlight=descriptor#properties"""

    def __get__(self, obj, cls):
        return self.fget(cls)


def expand_region_empty_line(region, view):
    if region.size() != 0:
        return region
    region = view.expand_by_class(region, sublime.CLASS_EMPTY_LINE)
    assert isinstance(region, sublime.Region)
    return region
