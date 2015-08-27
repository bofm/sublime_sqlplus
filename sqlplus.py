import os
import sublime
import sublime_plugin
from time import time
from .sttools import *
from .command_line_wrapper import CommandLineWrapper, History


settings = Settings('SQLPlus.sublime-settings')

sqlplus_instances = {}  # { view_id: sqlplus_instance }
history = History()


class CommandHistory(sublime_plugin.TextCommand):
    def run(self, edit):
        command = self.get_command()
        if command:
            replace_selected(self.view, command)


class HistoryPrevCommand(CommandHistory):
    get_command = history.get_prev


class HistoryNextCommand(CommandHistory):
    get_command = history.get_next


class Cleanup(sublime_plugin.EventListener):
    def on_pre_close(self, view):
        sqlplus = sqlplus_instances.pop(view.id(), None)
        if sqlplus is not None:
            try:
                sqlplus.stop()
            except RuntimeError:
                pass


class Sqlplus(CommandLineWrapper):

    def __init__(self, *args, **kwargs):
        self.position = 0
        global settings
        silent = settings.silent and '-S' or ''
        sqlplus_path = settings.path
        workdir = settings.workdir
        if not os.path.isdir(workdir):
            raise ValueError('SQLPlus workdir "%s" does not exist.' % workdir)
        super().__init__(sqlplus_path, silent, '/nolog', start=False, workdir=workdir)


@async
def handle_output(sqlplus, view):
    try:
        text = sqlplus.get_output(timeout=0.1).strip('\n')
        if text:
            text = check_set_connstr(view, text)
            text = '\n%s\n' % text
            insert_at(view, sqlplus.position, text)
            sqlplus.position += len(text)
        handle_output(sqlplus, view)
    except RuntimeError as e:
        msg = 'SQL*Plus process terminated.'
        print(msg)
        sublime.status_message(msg)
        insert_at(view, sqlplus.position, '\n%s\n\n' % msg)
        view.erase_status('sqlplus_connstr')


def check_set_connstr(view, text):
    connstr = settings.connection_string
    if not connstr:
        return text
    connstr_l, _, connstr_r = connstr.rpartition('|')
    if not connstr_l:
        return text
    if connstr_l in text and connstr_r in text:
        text1, _, connstr = text.rpartition(connstr_l)
        connstr, _, text2 = connstr.rpartition(connstr_r)
        view.set_status('sqlplus_connstr', connstr)
        return text1 + text2
    return text


class RunInSqlplusCommand(sublime_plugin.TextCommand):

    def parse(self):
        """Returns current selection or, if nothing is selected, the line where
        the cursor is."""

        regions = self.view.sel()
        if len(regions) > 1:
            sublime.status_message('Too many regions (%i).' % len(regions))
        region = regions[0]
        if region.size() == 0:
            region = self.view.expand_by_class(
                region,
                sublime.CLASS_LINE_START | sublime.CLASS_LINE_END)
        self.sqlplus_instance.position = region.end()
        return self.view.substr(region)

    def run(self, edit):
        global settings
        syntax = settings.auto_set_syntax
        if syntax:
            if self.view.settings().get('syntax') != syntax:
                self.view.set_syntax_file(settings.auto_set_syntax)
        sqlplus = self.sqlplus_instance
        command = self.parse()
        if not sqlplus.is_running:
            sqlplus.start()
            handle_output(sqlplus, self.view)
        sqlplus.run_command(command)
        history.add(command.strip('\n'))

    @property
    def sqlplus_instance(self):
        global sqlplus_instances
        sqlplus = sqlplus_instances.get(self.view.id(), None)
        if sqlplus is None:
            sqlplus = Sqlplus()
            sqlplus_instances[self.view.id()] = sqlplus
        return sqlplus


class Completions(sublime_plugin.EventListener):

    _BUILD_FREQ = 30.0  # seconds
    _last_build_time = None
    _is_building = False
    _completions = []

    def can_build(self):
        return (not self._is_building
                and (self._last_build_time is None
                     or time() - self._last_build_time > self._BUILD_FREQ) )

    @async
    def build_completions(self):
        if not self.can_build():
            return
        self._build()

    def _build(self):
        try:
            print('Sqlplus: Building completions...')
            self._is_building = True
            self._completions = list(self.gen_items(settings.workdir))
        finally:
            self._last_build_time = time()
            self._is_building = False
            print('Sqlplus: Finished building completions.')

    def gen_items(self, root):
        for dirpath, dirs, files in os.walk(root, followlinks=True):
            files = [f for f in files if not f[0] == '.']
            dirs[:] = [d for d in dirs if not d[0] == '.']
            reldir = os.path.relpath(dirpath, root)
            if reldir == '.':
                reldir = ''
            else:
                yield ('%s\t%s' % (reldir, '(dir)'), reldir)
            for x in dirs:
                d = os.path.join(reldir, x)
                yield ('%s\t%s' % (d, '(dir)'), d)
            for file in files:
                f = os.path.join(reldir, file)
                if f.lower().endswith('.sql'):
                    f2, *_ = f.rpartition('.')
                fullpath = os.path.join(dirpath, file)
                yield (f, f2)

    def get_usage(self, filename):
        if not filename.lower().endswith('.sql'):
            return ''
        try:
            with open(filename, 'r', encoding='utf-8', errors='replace') as f:
                for line in f:
                    if 'usage:' in line.lower():
                        _, _, usage = line.partition(':')
                        return usage.strip()
            return ''
        except OSError:
            return ''

    def on_query_completions(self, view, prefix, locations):
        """
        Returns a list of tuples for auto-completion
        [ (<string_to_insert>, <string_to_show_in_the_dropdown>), ... ]
        """
        global sqlplus_instances
        if view.id() not in sqlplus_instances:
            return
        self.build_completions()
        return (self._completions, sublime.INHIBIT_EXPLICIT_COMPLETIONS)
