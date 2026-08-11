# lucio

Render Markdown templates by executing embedded shell or code blocks.


## Overview

`lucio` reads a GitHub-flavored Markdown template,
executes the fenced shell or code blocks that opted in,
and writes a rendered Markdown file:

```bash
$ lucio README.template.md
```

It is strictly template-to-output, never in-place,
and everything that did not opt in passes through byte-for-byte:
tabs, trailing spaces, indented fences, tilde fences, HTML comments,
and code blocks that merely talk about `lucio` are all left alone.

The typical use case is documentation that must not go stale:
the template holds the commands, the rendered file holds
the commands *and* the output they produced when the file was generated.

`lucio` has been developed to render the Markdown files
forming the CLI usage guide for
[`volumito`](https://github.com/pettarin/volumito);
the design strive to achieve flexibility
while keeping the tool extremely light
(just a PyPI package with minimal dependencies)
and the annotations simple for the human user to add.


## Features

- One trigger syntax, no template language: fenced blocks and nothing else
- Byte-for-byte passthrough of everything that is not a trigger block
- Source block, captured stdout, and captured stderr, each shown or hidden per block
- Output merged into the source fence, as a terminal transcript, or kept in a fence of its own
- Hidden setup blocks, for the commands that prepare the stage but must not appear
- Raw Markdown file inclusion
- Expected exit codes, so that a documented failure stays a failure
  and an undocumented one aborts the run
- Syntax errors surface before any block is executed
- AI-generated, Human-reviewed code
- Type-safe implementation with type hints
- Comprehensive unit test coverage (100%)


## Requirements

- Python 3.13 or later
- A package/virtual environment manager tool (e.g., `micromamba`, `conda`, `uv`, etc.)
- `bash`, available on `PATH`


## Installation

**IMPORTANT**: the examples in the documentation use `micromamba`
               to manage virtual environments; feel free to replace it
               with your favorite tool (`conda`, `uv`, etc.).

### From PyPI (Recommended)

`lucio` is published on PyPI as the same-name package
[lucio](https://pypi.org/project/lucio/)
, and this is the recommended way of installing it for most users.

Only the first time: create a virtual environment,
activate it, and install the latest release of `lucio`
available on PyPI with `pip`:

```bash
$ micromamba create -n lucio_env python=3.13
$ micromamba activate lucio_env

(lucio_env) $ pip install lucio
```

### From Source

Clone this repository and install from source
in a virtual environment:

```bash
$ git clone https://github.com/pettarin/lucio
$ cd lucio

$ micromamba create -n lucio_env python=3.13
$ micromamba activate lucio_env

(lucio_env) $ pip install -e .
(lucio_env) $ # or
(lucio_env) $ make install-e-this
```

You should be able to run:

```bash
(lucio_env) $ lucio --version
lucio, version 0.0.3
```


## Usage

```
Usage: lucio [OPTIONS] INPUT [OUTPUT]

  Render the Markdown template INPUT into OUTPUT, executing its lucio blocks.

  Without OUTPUT, an INPUT named NAME.template.md is rendered into NAME.md,
  and any other INPUT is printed on stdout. An OUTPUT of "-" always means
  stdout, and the diagnostics of the tool always go to stderr, so the two
  never mix.

  The template is rendered in memory and written out only once everything
  succeeded, so a failing block leaves OUTPUT untouched.

Options:
  --version              Show the version and exit.
  --color / --no-color   Color the messages of the tool (when the terminal
                         supports it).  [default: color]
  --timeout FLOAT        Per-block execution timeout, in seconds; -1 for no
                         timeout.  [default: 60.0]
  -O, --overwrite-files  Overwrite OUTPUT if it already exists.
  -v, --verbose          Log each executed block and its exit code to stderr.
  -h, --help             Show this message and exit.
```

INPUT is required; OUTPUT is optional, and the two must resolve to different files.
Where the rendered document ends up depends on the two arguments:

| INPUT | OUTPUT | destination |
|---|---|---|
| `NAME.template.md` | *(omitted)* | `NAME.md`, next to INPUT |
| anything else | *(omitted)* | stdout |
| anything | `-` | stdout |
| anything | a path | that path |

So the common case needs one argument only:

```bash
$ lucio README.template.md          # writes README.md
```

The `.template.md` suffix is the only name `lucio` reads anything into; `OUTPUTFILE.md`
is a convention of this documentation, not a rule.

An OUTPUT of `-` prints the document instead of writing it, which keeps `lucio` usable
in a pipeline even for a template-named INPUT:

```bash
$ lucio README.template.md - | less
```

Everything `lucio` has to say goes to stderr, the rendered document being the
only thing ever written to stdout.

An existing OUTPUT is never clobbered by accident, derived names included: `lucio`
refuses to run unless `-O` / `--overwrite-files` is given. The check happens before
the template is parsed, so a refusal costs nothing and executes no block.

Each block is given 60 seconds to run, after which the whole run is aborted; pass
`--timeout` to raise or lower that, or `--timeout -1` to let the blocks take as long
as they need.

### Logging

The messages of the tool go through the standard `logging` machinery, under the
`lucio` logger, and come out on stderr stamped with the UTC time and their level:

```
[2026-08-11T10:14:52.310Z] [DEBU] Input file: "/home/user/lucio/README.template.md"
[2026-08-11T10:14:52.310Z] [DEBU] Output file: "/home/user/lucio/README.md"
[2026-08-11T10:14:52.311Z] [DEBU] Overwrite files: True
[2026-08-11T10:14:52.311Z] [DEBU] Block timeout: 60.0 seconds
[2026-08-11T10:14:52.318Z] [DEBU] README.template.md:12: executing bash lucio block
[2026-08-11T10:14:52.402Z] [DEBU] README.template.md:12: exit code 0
[2026-08-11T10:14:52.404Z] [INFO] Rendered "README.template.md" into "README.md"
```

`INFO` and above are shown by default, which is one line per run saying what was
written; failures are reported as `ERRO`. `-v` lowers the bar to `DEBUG`, which opens
the log with the settings of the run — the resolved paths, whether an existing OUTPUT
may be overwritten, and the timeout each block is given — and then reports every block
as it is executed. The levels are colored when stderr is a terminal, and `--no-color`
turns that off everywhere.

Using `lucio` as a library instead, nothing is printed until you install a handler
of your own on the `lucio` logger.

### Exit codes

| code | meaning |
|---|---|
| `0` | success: OUTPUT was written, or the document was printed on stdout |
| `1` | OUTPUT could not be written, or it exists and `--overwrite-files` was not given |
| `2` | usage error (missing or bad arguments, INPUT and OUTPUT are the same file) |
| `3` | template error: syntax error, or INPUT cannot be read or decoded |
| `4` | execution error: unexpected exit code, timed-out block, `bash` not runnable |

On any error other than `0`, OUTPUT is never opened and stdout stays empty:
a pre-existing OUTPUT is left exactly as it was.


## Template syntax

Two fences, and only these two, are processed:

````
```bash lucio [key=value ...]
```
````

````
```bash include
```
````

The trigger word must be the second token of the info string,
and the language must be `bash`.
Anything else is ordinary Markdown:
```` ```bash ````, ```` ```bash lucioX ````, ```` ```bash run lucio ````,
```` ```lucio ````, and `<!-- include FILE.md -->` all pass through untouched,
as does any trigger fence written inside a longer fence
(that is how the examples in this file survive).

### `bash lucio`

The body of the block is executed by bash, and the block is replaced by
its source fence and/or what the body printed:

````
```bash lucio
echo "hello"
```
````

renders as:

````
```bash
echo "hello"
hello
```
````

Note that the info string is reduced to `bash` in the output,
while the body and the closing fence are copied byte-for-byte.

By default the captured output is merged into the source fence, right after
the commands that produced it, the way a terminal transcript reads.
With `merge=False` it goes into a separate unlabeled fence instead,
one blank line below the source:

````
```bash
echo "hello"
```

```
hello
```
````

Either way, stdout comes first and stderr after it, and if the selected
streams are empty no output is emitted at all.

#### Attributes

| key | values | default | meaning |
|---|---|---|---|
| `command` | `execute` | `execute` | what to do with the block; the only value in this version |
| `exit` | `any`, or an integer between `0` and `255` | `0` | the exit code the block must exit with |
| `merge` | `True`, `False` | `True` | put the captured output inside the source fence, rather than in a fence of its own |
| `show_source` | `True`, `False` | `True` | emit the source block, as a plain ```` ```bash ```` fence |
| `stderr` | `True`, `False` | `True` | include the captured stderr in the output |
| `stdout` | `True`, `False` | `True` | include the captured stdout in the output |

Attributes are unquoted `key=value` tokens, separated by whitespace.
Booleans are spelled the Python way, `True` and `False`, and the case matters:
`true`, `TRUE`, `1`, and `"True"` are all errors, not silent falsehoods.
An unknown key, a repeated key, a malformed token, or an unknown value
is an error too.

`merge` has nothing to do when there is no source fence to merge into
(`show_source=False`) or no output to merge (empty streams, or both
`stdout=False` and `stderr=False`): in those cases it changes nothing.

A block with `show_source=False stdout=False stderr=False` renders to nothing:
it is a hidden setup block. Blank lines around it are collapsed, so it leaves
no trace in the output. Every block runs in the working directory `lucio`
was invoked from, so a hidden block can prepare files for the blocks below it:

````
```bash lucio show_source=False stdout=False stderr=False
rm -f ./configuration.yaml
```
````

Each block is executed in its own bash subprocess, with the body passed
verbatim and nothing injected into it, so shell state (variables, `cd`,
functions) does not carry over from one block to the next; the filesystem,
of course, does.

If a block exits with a code other than the expected one, the whole run is
aborted and OUTPUT is not written. Expected failures must declared with
`exit` to prevent that:

````
```bash lucio exit=1
cat missing_file.txt
```
````

`exit=any` accepts whatever return code the block returns.

A block that exits non-zero and is allowed to says so in the verbose log, naming the
attribute that let it through, so a tolerated failure is never mistaken for an
unnoticed one:

```
[2026-08-11T10:14:52.402Z] [DEBU] README.template.md:12: exit code 1 (permitted by exit=1)
[2026-08-11T10:14:53.118Z] [DEBU] README.template.md:24: exit code 3 (permitted by exit=any)
```

### `bash include`

The body is executed like any other block, but its stdout is pasted raw,
as Markdown, in place of the block: no source fence, no output fence.
Its stderr is discarded, and it must exit with `0`.
Attributes are not allowed.

````
```bash include
cat CONFIGURATION_FILE.md
```
````


## Newlines and whitespace

- CRLF line endings in the template are normalized to LF on read;
  a lone CR is left alone.
- A captured stream is normalized to end with exactly one newline;
  a stream holding nothing but newlines counts as empty.
- The output file ends with exactly one newline
  (an empty rendered document produces an empty file).
- Everything else, whitespace included, is copied byte-for-byte.
- A fence is emitted with as many backticks as needed to wrap the captured
  output, even if it contains fences of its own. A merged fence grows only
  when the output demands it; as long as it does not, the closing line of the
  template is reused byte-for-byte.


## Development

See the
[DEVELOPMENT](https://github.com/pettarin/lucio/blob/main/docs/DEVELOPMENT.md)
document.


## License

This project is licensed under
the GNU General Public License v3.0 or later (GPLv3+).

See the
[LICENSE](https://github.com/pettarin/lucio/blob/main/LICENSE)
file for details.


## Authors

- Alberto Pettarin ([Web](https://www.albertopettarin.it))
