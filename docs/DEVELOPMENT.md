# Development

**IMPORTANT**: the examples in the documentation use `micromamba`
               to manage virtual environments; feel free to replace it
               with your favorite tool (`conda`, `uv`, etc.).

## Setup Development Environment

Clone this repository and install from source
in a virtual environment, with development extras:

```bash
$ git clone https://github.com/pettarin/lucio
$ cd lucio

$ micromamba create -n lucio_dev python=3.13
$ micromamba activate lucio_dev

(lucio_dev) $ pip install -e ".[dev]"
(lucio_dev) $ # or
(lucio_dev) $ make install-e-this-dev
```

You should be able to run:

```bash
(lucio_dev) $ lucio --version
lucio, version 0.0.2
```


## Running Tests

```bash
# Run all checks (unit tests, linter, and type checker)
(lucio_dev) $ make test-all
# OR equivalently
(lucio_dev) $ make test

# Run unit tests only
(lucio_dev) $ make test-unit

# Run unit tests with coverage (HTML report in htmlcov/)
(lucio_dev) $ make coverage

# Run linter
(lucio_dev) $ make lint

# Run type checker
(lucio_dev) $ make check-type-hints
```

The unit tests execute real `bash` subprocesses, with plain builtins only
(`cat`, `echo`, `exit`, `printf`, `read`, `sleep`, `true`, `false`)
and no network access.


## Project Structure

```
lucio/
├── docs/
│   ├── CHANGELOG.md              # releases and their changes
│   ├── CODE_OF_CONDUCT.md        # ground rules of the project spaces
│   ├── CONTRIBUTING.md           # how to report issues and contribute code
│   ├── DEVELOPMENT.md            # this file
│   └── SECURITY.md               # how to report a security vulnerability
├── res/
│   └── copyright_header.txt      # header prepended to every source file
├── src/
│   └── lucio/
│       ├── __init__.py           # public API re-exports and version
│       ├── cli.py                # Click-based CLI, and the exit codes of the tool
│       ├── errors.py             # LucioError and its subclasses
│       ├── executor.py           # bash subprocess execution and expected-exit policy
│       ├── model.py              # segments, block options, and execution results
│       ├── parser.py             # template scanner: verbatim text vs trigger fences
│       └── renderer.py           # rendering of the parsed segments into Markdown
├── tests/                        # unit tests
│   ├── test_cli.py
│   ├── test_errors.py
│   ├── test_executor.py
│   ├── test_parser.py
│   └── test_renderer.py
├── LICENSE                       # full text of the license for this project
├── Makefile                      # make commands for the developer
├── MANIFEST.in                   # include/exclude additional files in the PyPI package
├── pyproject.toml                # descriptor for building the PyPI package
└── README.md                     # main README file
```

The rendering pipeline is a one-way street, and each module owns one step of it:
`parser.py` turns the template text into a list of segments, `executor.py` runs
one block body and reports what it printed, and `renderer.py` turns segments and
execution results back into Markdown. The renderer never touches a subprocess:
`cli.py` injects the runner callable it uses, which keeps the rendering rules
testable without bash, and bash testable without templates.


## Branching And Versioning Policy

### Branch `main`

- Branch `main` is protected, and it represents the sources of the latest stable release.
- Only the maintainer is allowed to push there directly,
  usually merging the `devel` branch when preparing a new release.
- Published packages on PyPI are from commit tagged `vX.Y.Z`.

### Branch `devel`

- Branch `devel` is protected, and it accumulates fixes and features for the next release.
- The maintainer is allowed to push there directly,
  usually merging feature or fix branches.
- Other contributors should open pull requests
  (see the [CONTRIBUTING](CONTRIBUTING.md) document)
  against the `devel` branch, which will be reviewed and, if appropriate, merged.

### Other Branches

- Fix branches should be named `fix/gh_#123_short_description`
  where `#123` is the ID of the GitHub issue being fixed.
- Feature branches should be named `feature/gh_#456_short_description`
  where `#456` is the ID of the GitHub issue describing the requested feature.
- In both cases, it is mandatory to have a GitHub issue
  describing the issue being fixed or the new feature being added.
- No need to squash commits on a fix or feature branch,
  just try to have meaningful commit messages if you have more than one commit.
  Usually it is preferable referencing the GitHub issue
  (`Fixes #123 ...` or `Implement #456 ...`) in the commit message.

### Versioning

- This project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).
- Each released version is published on PyPI as package
[lucio](https://pypi.org/project/lucio/)
and the corresponding commit tagged with `vX.Y.Z`,
where `lucio==X.Y.Z` is the released version.


## Contributing

See the
[CONTRIBUTING](CONTRIBUTING.md)
document.

