import json
import sublime
import sublime_plugin
from .import_js_daemon import ImportJsDaemon

DEBUG = True
STATUS_KEY = 'import-js'
STATUS_MESSAGE_WAITING_FOR_RESPONSE = 'Looking for imports...'

def plugin_unloaded():
    ImportJsDaemon.shutdown()

class ImportJsTerminateCommand(sublime_plugin.ApplicationCommand):
    def run(self): # pylint: disable=no-self-use
        ImportJsDaemon.shutdown()

class ImportJsReplaceCommand(sublime_plugin.TextCommand):
    def run(self, edit, characters): # pylint: disable=arguments-differ
        self.view.replace(edit, sublime.Region(0, self.view.size()), characters)


class ImportJsCommand(sublime_plugin.TextCommand):
    def project_root(self):
        return self.view.window().extract_variables()['folder']

    def run(self, edit, **args): # pylint: disable=arguments-differ
        current_file_contents = self.view.substr(sublime.Region(0, self.view.size()))

        command = args.get('command')
        payload = {
            'command': command,
            'pathToFile': self.view.file_name(),
            'fileContent': current_file_contents,
        }

        if (command == 'word' or command == 'goto'):
            payload['commandArg'] = self.view.substr(self.view.word(self.view.sel()[0]))

        if command == 'add':
            payload['commandArg'] = args.get('imports')

        if DEBUG:
            print('Command payload:')
            print(payload)

        if not self.view.get_status(STATUS_KEY):
            self.view.set_status(STATUS_KEY, STATUS_MESSAGE_WAITING_FOR_RESPONSE)

        ImportJsDaemon.execute_command(
            self.project_root(),
            (json.dumps(payload) + '\n').encode('utf-8'),
            lambda response: self.handle_daemon_response(response, edit, command, args))

    def handle_daemon_response(self, result_json, edit, command, command_args):
        if DEBUG:
            print('Command output:')
            print(result_json)

        self.view.erase_status(STATUS_KEY)

        result = json.loads(result_json)

        if result.get('error'):
            sublime.error_message('Error when executing importjs:\n\n' + result.get('error'))
            return

        if result.get('messages'):
            sublime.status_message('\n'.join(result.get('messages')))
        if result.get('unresolvedImports'):
            def handle_resolved_imports(resolved_imports):
                command_args['command'] = 'add'
                command_args['imports'] = resolved_imports
                self.run(edit, **command_args)
            self.view.run_command('import_js_replace', {'characters': result.get('fileContent')})
            self.ask_to_resolve(result.get('unresolvedImports'), handle_resolved_imports)
            return

        if command == 'goto':
            self.view.window().open_file(result.get('goto'))
        else:
            self.view.run_command('import_js_replace', {'characters': result.get('fileContent')})

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
                list(map(lambda imp: imp.get('displayName'), unresolved_imports[word])),
                on_done
            )

        ask_recurse(next(unresolved_iter, None))
