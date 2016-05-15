# Running import-js in Sublime Text

1. Install the [ImportJS plugin via Package
   Control](https://packagecontrol.io/packages/ImportJS)

2. Install the import-js npm package

   ```sh
   npm install -g import-js
   ```

3. [Configure import-js](README.md#configuration)

4. Open the root of your project as a folder (Project -> Add Folder to Project…)

5. Import a file!

   Whenever you have undefined variables, open the Command Palette
   (`CTRL+SHIFT+P`/`CMD+SHIFT+P`) and select "ImportJS: fix all imports", or
   "ImportJS: import word under cursor".

It will be helpful to bind `import_js` to easy-to-use bindings, such as:

```json
{ "keys": ["super+alt+i"], "command": "import_js" },
{ "keys": ["super+alt+j"], "command": "import_js", "args": { "word": true } },
{ "keys": ["super+alt+g"], "command": "import_js", "args": { "word": true, "goto": true } },
```

## Troubleshooting

If you get an error message saying something like "Can't find import-js
executable", you may need to specify a path to the `importjs` executable in
configuration. This likely means that you are using a tool like
[nvm](http://nvm.sh) or [nodenv](https://github.com/nodenv/nodenv) to manage
multiple Node versions on your system.

To fix this, you need to make sure that the code that sets up your `PATH` is in
the correct location. This plugin will open a login shell to determine the
proper `PATH`, so the code that sets up your `PATH` needs to be in a file that
is sourced for login shells. Here's a handy table:

Shell          | File
---------------|---------------------------
bash           | ~/.bash_profile
zsh (Mac OS X) | ~/.zprofile
zsh (Linux)    | ~/.zshenv or ~/.zprofile
fish           | ~/.config/fish/config.fish

Alternatively, you can also try editing the ImportJS User Settings from the
Preferences > Package Settings > ImportJS > Settings — User menu and set the
`executable` option to point to the path to the `importjs` executable. Example:

```json
{
  "executable": "/Users/USERNAME/.nvm/versions/node/v4.4.3/bin/importjs"
}
```

Please note that you can't use ~ to refer to the home directory, you need to
specify the full path. To figure out where your `importjs` executable is
located, you can run `which importjs` from your project's directory.
