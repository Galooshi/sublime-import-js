from textwrap import dedent
import json
import os
import subprocess
import threading
import queue
import sublime # pylint: disable=import-error
import sublime_plugin # pylint: disable=import-error

DEBUG = True
IMPORT_JS_ENVIRONMENT = {}
DAEMON = None
DAEMON_QUEUE = None
DAEMON_THREAD = None
EXECUTABLE = 'importjsd'
DAEMON_POLL_INTERVAL = 10


def extract_path():
    if 'SHELL' in os.environ:
        # We have to delimit the PATH output with markers because
        # text might be output during shell startup.
        out = subprocess.Popen(
            [os.environ['SHELL'], '-l', '-c', 'echo "__SUBL_PATH__${PATH}__SUBL_PATH__"'],
            env=os.environ,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        ).communicate()[0].decode()
        path = out.split('__SUBL_PATH__', 2)

        if len(path) > 1:
            return path[1]

        return ''
    else:
        return os.environ['PATH']

def plugin_loaded():
    global IMPORT_JS_ENVIRONMENT

    IMPORT_JS_ENVIRONMENT = dict(os.environ).copy()
    IMPORT_JS_ENVIRONMENT.update({
        'LC_ALL': 'en_US.UTF-8',
        'LC_CTYPE': 'UTF-8',
        'LANG': 'en_US.UTF-8',
    })

    path_env_variable = extract_path()

    settings = sublime.load_settings('ImportJS.sublime-settings')
    setting_paths = settings.get('paths')
    if setting_paths:
        path_env_variable = ':'.join(setting_paths) + ':' + path_env_variable

    IMPORT_JS_ENVIRONMENT.update({
        'PATH': path_env_variable,
    })

    if DEBUG:
        print('ImportJS loaded with environment:')
        print(IMPORT_JS_ENVIRONMENT)

def terminate_daemon():
    global DAEMON
    if DAEMON is None:
        return

    if DEBUG:
        print('Stopping ImportJS daemon process')

    DAEMON.terminate()
    DAEMON = None

def plugin_unloaded():
    terminate_daemon()

def no_executable_error(executable):
    return dedent('''
        Couldn't find executable {executable}.

        Make sure you have the `{executable}` binary installed (`npm install
        import-js -g`).

        If it is installed but you still get this message, and you are using
        something like nvm or nodenv, you probably need to configure your PATH
        correctly. Make sure that the code that sets up your PATH for these
        tools is located in .bash_profile, .zprofile, or the equivalent file
        for your shell.

        Alternatively, you might have to set the `paths` option in your
        ImportJS package user settings. Example:

        {{
            "paths": ["/Users/USERNAME/.nvm/versions/node/v4.4.3/bin"]
        }}

        To see where the {executable} binary is located, run `which {executable}`
        from the command line in your project's root.
        '''.format(executable=executable)).strip()

def enqueue_output(stdout, target):
    for line in iter(stdout.readline, b''):
        target.put(line.decode('utf-8'))
    stdout.close()

class ImportJsReplaceCommand(sublime_plugin.TextCommand):
    def run(self, edit, characters):
        self.view.replace(edit, sublime.Region(0, self.view.size()), characters)


class ImportJsCommand(sublime_plugin.TextCommand):
    waiting_for_daemon_response = False

    def project_root(self):
        return self.view.window().extract_variables()['folder']

    def get_daemon(self):
        global DAEMON
        global DAEMON_QUEUE
        global DAEMON_THREAD
        if DAEMON is not None:
            return DAEMON, DAEMON_QUEUE

        is_windows = os.name == 'nt'

        try:
            DAEMON = subprocess.Popen(
                [EXECUTABLE, 'start', '--parent-pid', str(os.getppid())],
                cwd=self.project_root(),
                env=IMPORT_JS_ENVIRONMENT,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=is_windows
            )
            DAEMON_QUEUE = queue.Queue()
            DAEMON_THREAD = threading.Thread(
                target=enqueue_output,
                args=(DAEMON.stdout, DAEMON_QUEUE)
            )
            DAEMON_THREAD.daemon = True
            DAEMON_THREAD.start()
            # The daemon process will print one line at startup of the command,
            # something like "Daemon active. Logs will go to [...]". We need to
            # ignore this line so that we can expect json output when running
            # commands.
            self.wait_for_daemon_response()

            return DAEMON, DAEMON_QUEUE
        except FileNotFoundError as exception:
            if str(exception).find(EXECUTABLE) > -1:
                # If the executable is in the error message, then we believe
                # that the executable cannot be found and show a more helpful
                # message.
                sublime.error_message(no_executable_error(EXECUTABLE))
            else:
                # Something other than the executable cannot be found, so we
                # pass through the original message.
                sublime.error_message(exception.strerror)
            raise exception

    def run(self, edit, **args):
        if self.waiting_for_daemon_response:
            return

        current_file_contents = self.view.substr(
            sublime.Region(0, self.view.size()))

        command = args.get('command')
        payload = {
            'command': command,
            'pathToFile': self.view.file_name(),
            'fileContent': current_file_contents,
        }

        if(command == 'word' or command == 'goto'):
            payload['commandArg'] = self.view.substr(
                self.view.word(self.view.sel()[0]))

        if command == 'add':
            payload['commandArg'] = args.get('imports')


        if DEBUG:
            print('Command payload:')
            print(payload)
        self.write_daemon_command(payload)
        self.wait_for_daemon_response(
            lambda response: self.handle_daemon_response(response, edit, command, args))

    def write_daemon_command(self, payload):
        daemon_process, _ = self.get_daemon()
        daemon_process.stdin.write((json.dumps(payload) + '\n').encode('utf-8'))
        try:
            daemon_process.stdin.flush()
        except (BrokenPipeError, IOError):
            if DEBUG:
                print('Something went wrong with the process, restarting...')
            terminate_daemon()
            self.write_daemon_command(payload)

    def handle_daemon_response(self, result_json, edit, command, command_args):
        if DEBUG:
            print('Command response:')
            print(result_json)
        result = json.loads(result_json)

        if result.get('error'):
            sublime.error_message(
                'Error when executing importjs:\n\n' + result.get('error'))
            return

        if result.get('messages'):
            sublime.status_message('\n'.join(result.get('messages')))
        if result.get('unresolvedImports'):
            def handle_resolved_imports(resolved_imports):
                command_args['command'] = 'add'
                command_args['imports'] = resolved_imports
                self.run(edit, **command_args)
            self.view.run_command('import_js_replace',
                                  {'characters': result.get('fileContent')})
            self.ask_to_resolve(result.get('unresolvedImports'),
                                handle_resolved_imports)
            return

        if command == 'goto':
            self.view.window().open_file(result.get('goto'))
        else:
            self.view.run_command('import_js_replace',
                                  {'characters': result.get('fileContent')})

    def wait_for_daemon_response(self, callback=None):
        self.waiting_for_daemon_response = True
        sublime.set_timeout_async(lambda: self.read_daemon_response(callback), DAEMON_POLL_INTERVAL)

    def read_daemon_response(self, callback):
        _, daemon_queue = self.get_daemon()
        try:
            response = daemon_queue.get_nowait()
            self.waiting_for_daemon_response = False
            if callback is not None:
                callback(response)
        except queue.Empty:
            self.wait_for_daemon_response(callback)

    def ask_to_resolve(self, unresolved_imports, on_resolve):
        resolved = {}
        unresolved_iter = iter(unresolved_imports)

        def ask_recurse(word):
            if not word:
                on_resolve(resolved)
                return

            def on_done(i):
                if i > -1:
                    resolved[word] = unresolved_imports[word][i]['data']
                ask_recurse(next(unresolved_iter, None))

            self.view.show_popup_menu(
                list(map(lambda imp: imp.get('displayName'),
                         unresolved_imports[word])),
                on_done
            )

        ask_recurse(next(unresolved_iter, None))
