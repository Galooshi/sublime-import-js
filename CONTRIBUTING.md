# Contributing to Sublime ImportJS

## General guidelines

We love your input! We want to make contributing to this project as easy and transparent as possible, whether it's:

- Reporting a bug;
- Discussing the current state of the code;
- Submitting a fix;
- Proposing new features;
- Becoming a maintainer.

### We develop with Github
We use github to host code, to track issues and feature requests, as well as accept pull requests.

### Code changes happen through Pull Requests
Pull requests are the best way to propose changes to the codebase. We actively welcome your pull requests:

1. Fork the repo and create your branch from `master`;
2. Write the code and keep it in short, organized commits;
3. Test your code;
4. Make sure your code lints;
5. Issue that pull request!

### Any contributions you make will be under the MIT Software License
In short, when you submit code changes, your submissions are understood to be under the same [MIT License](LICENSE) that covers the project. Feel free to contact the maintainers if that's a concern.

### Report bugs using Github's [issues](https://github.com/Galooshi/sublime-import-js/issues/)
We use GitHub issues to track public bugs. Report a bug by [opening a new issue](https://github.com/Galooshi/sublime-import-js/issues/new); it's that easy!

### Write bug reports with detail, background, and sample code
**Great Bug Reports** tend to have:

- A quick summary and/or background;
- Steps to reproduce;
  - Be specific!;
  - Attach screenshots if relevant;
- What you expected would happen;
- What actually happens;
- Notes (possibly including why you think this might be happening, or stuff you tried that didn't work).

People *love* thorough bug reports. I'm not even kidding.

### Use a consistent coding style

* 4 spaces for indentation;
* Run `pylint` with the provided `.pylintrc` config file.

### License
By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).

### References
This document was adapted from the open-source contribution guidelines [found here](https://gist.github.com/briandk/3d2e8b3ec8daf5a27a62).


## Local development

Here are a few tips to make it simpler to test a local copy of ImportJS in
Sublime:

### Symlink

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
