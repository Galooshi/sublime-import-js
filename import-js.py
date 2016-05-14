from textwrap import dedent
import json
import os
import sublime
import sublime_plugin
import subprocess

import_js_environment = {}


def extract_path():
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


def plugin_loaded():
    global import_js_environment

    import_js_environment = dict(os.environ).copy()
    import_js_environment.update({
        'LC_ALL': 'en_US.UTF-8',
        'LC_CTYPE': 'UTF-8',
        'LANG': 'en_US.UTF-8',
    })

    import_js_environment.update({
        'PATH': extract_path(),
    })

    print('ImportJS loaded with environment:')
    print(import_js_environment)


def no_executable_error(executable):
    return dedent('''
        Couldn't find executable {executable}.

        Make sure you have the `importjs` binary installed (`npm install
        import-js -g`).

        If it is installed but you still get this message, you might have to
        set a custom `executable` in your ImportJS package user settings.
        Example:

        {{
            "executable": "/usr/local/bin/importjs"
        }}

        To see where importjs binary is located, run `which importjs`
        from the command line in your project's root.
        '''.format(executable=executable)).strip()


class ImportJsReplaceCommand(sublime_plugin.TextCommand):
    def run(self, edit, characters):
        self.view.replace(
            edit, sublime.Region(0, self.view.size()), characters)


class ImportJsCommand(sublime_plugin.TextCommand):
    def run(self, edit, **args):
        current_file_contents = self.view.substr(
            sublime.Region(0, self.view.size()))

        project_root = self.view.window().extract_variables()['folder']
        settings = sublime.load_settings('ImportJS.sublime-settings')

        executable = settings.get('executable')
        cmd = args.get('command')
        command = [executable, cmd]

        if(cmd == 'word' or cmd == 'goto'):
            word = self.view.substr(self.view.word(self.view.sel()[0]))
            command.append(word)

        if(cmd == 'add'):
            command.append(json.dumps(args.get('imports')))

        command.append(self.view.file_name())

        print(command)

        try:
            proc = subprocess.Popen(
                command,
                cwd=project_root,
                env=import_js_environment,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
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

        result = proc.communicate(input=current_file_contents.encode('utf-8'))
        stdout = result[0].decode()
        stderr = result[1].decode()

        if(proc.returncode > 0):
            sublime.error_message(
                'Error when executing importjs:\n\n' + stderr)
            return

        if(len(stdout) == 0):
            sublime.error_message(
                'Nothing returned when executing importjs:\n\n' + stderr)
            return

        result = json.loads(stdout)
        if(result.get('messages')):
            sublime.status_message('\n'.join(result.get('messages')))
        if(result.get('unresolvedImports')):
            def handle_resolved_imports(resolved_imports):
                args['command'] = 'add'
                args['imports'] = resolved_imports
                self.run(edit, **args)
            self.ask_to_resolve(result.get('unresolvedImports'),
                                handle_resolved_imports)
            return

        if(cmd == 'goto'):
            self.view.window().open_file(
                self.project_path() + '/' + result.get('goto'))
        else:
            self.view.run_command("import_js_replace",
                                  {"characters": result.get('fileContent')})

    def project_path(self):
        for folder in self.view.window().project_data().get('folders'):
            if(self.view.file_name().startswith(folder.get('path'))):
                return folder.get('path')

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
