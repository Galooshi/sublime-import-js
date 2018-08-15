Here are a few tips to make it simpler to test a local copy of ImportJS in
Sublime:

## Symlink

Make a symlink inside your Sublime packages folder to the local copy of
sublime-import-js. Every time you change the `import-js.py` file the plugin will
reload.

```sh
cd ~/Library/Application Support/Sublime Text 3/Packages
ln -s ~/sublime-import-js sublime-import-js
```

## Code of conduct

This project adheres to the [Contributor Covenant Code of Conduct][code-of-conduct]. By
participating, you are expected to honor this code.

[code-of-conduct]: CODE_OF_CONDUCT.md
