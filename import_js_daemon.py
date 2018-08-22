from textwrap import dedent
import os
import queue
import subprocess
import threading
import sublime

DEBUG = True
IMPORT_JS_ENVIRONMENT = {}
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

class ImportJsDaemon:
    DEBUG = True
    DAEMON_INSTANCE = None
    DAEMON_PROCESS = None
    DAEMON_QUEUE = None

    @staticmethod
    def execute_command(cwd, payload, callback):
        daemon = ImportJsDaemon.get_daemon(cwd)
        try:
            return daemon.execute_queued_command(payload, callback)
        except (BrokenPipeError, IOError):
            if DEBUG:
                print('Something went wrong with the process, restarting...')
            ImportJsDaemon.shutdown()
            ImportJsDaemon.execute_command(cwd, payload, callback)

    @staticmethod
    def get_daemon(cwd):
        if ImportJsDaemon.DAEMON_INSTANCE is not None:
            return ImportJsDaemon.DAEMON_INSTANCE

        daemon = ImportJsDaemon(cwd)

        if DEBUG:
            print('Started ImportJS daemon')

        ImportJsDaemon.DAEMON_INSTANCE = daemon
        return daemon

    @staticmethod
    def shutdown():
        if ImportJsDaemon.DAEMON_INSTANCE is None:
            return

        if DEBUG:
            print('Stopping ImportJS daemon')

        ImportJsDaemon.DAEMON_INSTANCE.shutdown_process()
        ImportJsDaemon.DAEMON_INSTANCE = None

    def __init__(self, cwd):
        self._cwd = cwd
        self._command_queue = queue.Queue()
        self._read_polling_started = False
        self._instantiate_daemon()

    def shutdown_process(self):
        self._process.terminate()

    def execute_queued_command(self, payload=None, callback=None):
        if payload is not None:
            self._write_command(payload)

        # Put the command into a queue and start polling.
        self._command_queue.put(callback)

        if DEBUG:
            print('Received ImportJS daemon command;', 'queue size:', self._command_queue.qsize())

        self._start_read_interval()


    def _instantiate_daemon(self):
        is_windows = os.name == 'nt'

        try:
            self._process = subprocess.Popen(
                [EXECUTABLE, 'start', '--parent-pid', str(os.getppid())],
                cwd=self._cwd,
                env=IMPORT_JS_ENVIRONMENT,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=is_windows
            )
            self._read_queue = queue.Queue()
            self._read_thread = threading.Thread(
                target=enqueue_output,
                args=(self._process.stdout, self._read_queue)
            )
            self._read_thread.daemon = True
            self._read_thread.start()
            # Run an empty command, to consume the first line of the daemon output, which
            # shows the log path.
            self.execute_queued_command()
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

    def _write_command(self, command):
        self._process.stdin.write(command)
        self._process.stdin.flush()

        if DEBUG:
            print('Wrote ImportJS daemon command')

    def _start_read_interval(self):
        # Don't start multiple polling intervals.
        if self._read_polling_started:
            return

        self._read_polling_started = True
        self._read_output()

    def _read_output(self):
        # If we ran out of commands waiting, stop polling.
        if self._command_queue.empty():
            self._read_polling_started = False
            return

        try:
            # If there is no line to read yet, this call will throw an exception.
            response = self._read_queue.get_nowait()

            # If we can a response, get the first waiting command and finish it.
            callback = self._command_queue.get_nowait()
            if callback is not None:
                callback(response)

            if DEBUG:
                print('Returned ImportJS daemon command output')
        except queue.Empty:
            pass

        # Keep polling. If the waiting commands queue is empty, it will be handled
        # at the start of the call.
        sublime.set_timeout_async(self._read_output, DAEMON_POLL_INTERVAL)
