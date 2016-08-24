from textwrap import dedent
import json
import os
import sublime
import sublime_plugin
import subprocess

import_js_environment = {}
daemons = {}


def extract_path():
    if 'SHELL' in os.environ:
        # We have to delimit the PATH output with markers because
        # text might be output during shell startup.
        out = subprocess.Popen(
            [os.environ['SHELL'], '-l', '-c',
                'echo "__SUBL_PATH__${PATH}__SUBL_PATH__"'],
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
    global import_js_environment

    import_js_environment = dict(os.environ).copy()
    import_js_environment.update({
        'LC_ALL': 'en_US.UTF-8',
        'LC_CTYPE': 'UTF-8',
        'LANG': 'en_US.UTF-8',
    })

    path_env_variable = extract_path()

    settings = sublime.load_settings('ImportJS.sublime-settings')
    setting_paths = settings.get('paths')
    if setting_paths:
        path_env_variable = ':'.join(setting_paths) + ':' + path_env_variable

    import_js_environment.update({
        'PATH': path_env_variable,
    })

    print('ImportJS loaded with environment:')
    print(import_js_environment)

def plugin_unloaded():
    global daemons
    for cwd, daemon in daemons.items():
        print('Stopping ImportJS daemon process for cwd ' + cwd)
        daemon.terminate()

def no_executable_error(executable):
    return dedent('''
        Couldn't find executable {executable}.

        Make sure you have the `importjsd` binary installed (`npm install
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

        To see where the importjsd binary is located, run `which importjsd`
        from the command line in your project's root.
        '''.format(executable=executable)).strip()


class ImportJsReplaceCommand(sublime_plugin.TextCommand):
    def run(self, edit, characters):
        self.view.replace(
            edit, sublime.Region(0, self.view.size()), characters)


class ImportJsCommand(sublime_plugin.TextCommand):
    def project_root(self):
        return self.view.window().extract_variables()['folder']

    def start_or_get_daemon(self, cwd):
        global daemons
        if (cwd in daemons):
            return daemons[cwd]

        is_windows = os.name == 'nt'
        executable = 'importjsd'

        try:
            daemon = subprocess.Popen(
                [executable, 'start', '--parent-pid', str(os.getppid())],
                cwd=cwd,
                env=import_js_environment,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=is_windows
            )
            # The daemon process will print one line at startup of the command,
            # something like "DAEMON active. Logs will go to [...]". We need to
            # ignore this line so that we can expect json output when running
            # commands.
            daemon.stdout.readline()

            daemons[cwd] = daemon

            return daemon
        except FileNotFoundError as e:
            if(e.strerror.find(executable) > -1):
                # If the executable is in the error message, then we believe
                # that the executable cannot be found and show a more helpful
                # message.
                sublime.error_message(no_executable_error(executable))
            else:
                # Something other than the executable cannot be found, so we
                # pass through the original message.
                sublime.error_message(e.strerror)
            raise e

    def run(self, edit, **args):
        current_file_contents = self.view.substr(
            sublime.Region(0, self.view.size()))

        cmd = args.get('command')
        payload = {
            "command": cmd,
            "pathToFile": self.view.file_name(),
            "fileContent": current_file_contents,
        }

        if(cmd == 'word' or cmd == 'goto'):
            payload["commandArg"] = self.view.substr(
                    self.view.word(self.view.sel()[0]))

        if(cmd == 'add'):
            payload["commandArg"] = args.get('imports');


        print(payload)
        process = self.start_or_get_daemon(self.project_root())
        process.stdin.write((json.dumps(payload) + '\n').encode('utf-8'))
        process.stdin.flush()
        resultJson = process.stdout.readline().decode('utf-8')
        print(resultJson)

        result = json.loads(resultJson)

        if(result.get('error')):
            sublime.error_message(
                'Error when executing importjs:\n\n' + result.get('error'))
            return

        if(result.get('messages')):
            sublime.status_message('\n'.join(result.get('messages')))
        if(result.get('unresolvedImports')):
            def handle_resolved_imports(resolved_imports):
                args['command'] = 'add'
                args['imports'] = resolved_imports
                self.run(edit, **args)
            self.view.run_command("import_js_replace",
                                  {"characters": result.get('fileContent')})
            self.ask_to_resolve(result.get('unresolvedImports'),
                                handle_resolved_imports)
            return

        if(cmd == 'goto'):
            self.view.window().open_file(
                self.project_root() + '/' + result.get('goto'))
        else:
            self.view.run_command("import_js_replace",
                                  {"characters": result.get('fileContent')})

    def ask_to_resolve(self, unresolved_imports, on_resolve):
        resolved = {}
        unresolved_iter = iter(unresolved_imports)

        def ask_recurse(word):
            if (not(word)):
                on_resolve(resolved)
                return

            def on_done(i):
                if(i > -1):
                    resolved[word] = unresolved_imports[word][i]['importPath']
                ask_recurse(next(unresolved_iter, None))

            self.view.show_popup_menu(
                list(map(lambda imp: imp.get('displayName'),
                         unresolved_imports[word])),
                on_done
            )

        ask_recurse(next(unresolved_iter, None))
