# lucio

Render Markdown templates by executing embedded shell or code blocks.


## Overview

`lucio` reads a GitHub-flavored Markdown template,
executes the fenced shell or code blocks
that are annotated for its consumption,
and writes a rendered Markdown file:

```bash
lucio README.template.md README.md
```

`lucio` is strictly template-to-output, never edits in-place,
and fences that are not explicitly marked for `lucio`
pass through byte-for-byte: tabs, trailing spaces, indented fences,
tilde fences, HTML comments, are all left intact.

The typical use case is automating the update of documentation
for command line tools:
the template holds the commands, the rendered file holds
the commands and the output they produce.
Indeed `lucio` has been developed to render the Markdown files
forming the CLI usage guide for
[`volumito`](https://github.com/pettarin/volumito).

The design of `lucio` aims at achieving flexibility
while keeping the tool extremely light
(it is published as the sdist PyPI package
[lucio](https://pypi.org/project/lucio/)
requiring only minimal dependencies)
and the annotations reasonably short and simple
for the human user to manually author and maintain.


## Features

- Simple trigger syntax based on annotations on fenced blocks
- Byte-for-byte passthrough of everything that is not a trigger block
- Block source, captured stdout, and captured stderr, each shown or hidden per block
- Stdout/stderr contents can be merged or kept separate from the source block
- Support fo "hidden" setup blocks to run commands
  but that must be omitted from the rendered document
- File inclusion by path relative to the template, raw or fenced in any language
- Check on exit codes, allowing for documenting expected failing behavior
  while still catching unexpected errors via tool failure
- Syntax errors surface before any block is executed
- AI-generated, Human-reviewed and Human-tested code
- Type-safe implementation with type hints
- Comprehensive unit test coverage (100%)


## Requirements

- Python 3.13 or later
- A package/virtual environment manager tool (e.g., `micromamba`, `conda`, `uv`, etc.)
- To execute shell blocks: `bash`/`sh`/`zsh` available on `PATH`


## Installation

**IMPORTANT**: the examples in the documentation use `micromamba`
               to manage virtual environments; feel free to replace it
               with your favorite tool (`conda`, `uv`, etc.).

### From PyPI (Recommended)

`lucio` is published on PyPI as the same-name package
[lucio](https://pypi.org/project/lucio/),
and this is the recommended way of installing it for most users.

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

```bash lucio
lucio --version
```

(dropping the `(lucio_env) $` prefix in the examples from now on).

## Usage

**IMPORTANT**: `lucio` might execute dangerous/irreversible commands.
               **Never execute the tool over untrusted input files.**

```bash lucio
lucio --help
```

INPUT is required; OUTPUT is optional, and the two must resolve to different files.
Where the rendered document ends up depends on the two arguments:

| INPUT              | OUTPUT      | Destination              |
|--------------------|-------------|--------------------------|
| `NAME.template.md` | *(omitted)* | `NAME.md`, next to INPUT |
| `NAME.tmd`         | *(omitted)* | `NAME.md`, next to INPUT |
| anything else      | *(omitted)* | stdout                   |
| anything           | `-`         | stdout                   |
| anything           | a path      | that path                |

Examples:

```bash
lucio README.template.md          # writes README.md
lucio README.tmd                  # writes README.md
lucio README.mark /tmp/OUT.mark   # writes /tmp/OUT.mark
lucio README.tmd -                # writes to stdout
```

An OUTPUT of `-` prints the document instead of writing it,
which keeps `lucio` usable in a pipeline even for a template-named INPUT:

```bash
lucio README.template.md - | less
```

`-P` / `--pager` does the same without the pipe, sending the document to your
`PAGER` when stdout is a terminal
(but it is ignored when issued with redirection to file):

```bash
lucio README.template.md - -P
```

An existing OUTPUT is never overwritten by accident, including when its path is derived:
`lucio` refuses to overwrite files unless the `-O` / `--overwrite-files` option is specified.
The check happens before the template is parsed, so a refusal costs nothing and executes no block.

### Do-not-edit Comment

By default, the rendered document opens with a comment naming the template it came from,
so that whoever finds the generated file knows what to edit instead:

```
<!-- This file README.md has been rendered by CLI tool 'lucio'. Do not edit this file, but rather its template README.template.md . -->
```

This behavior can be prevented by issuing the `-E` / `--omit-do-not-edit-comment` option.

### Logging

Logs and messages from `lucio` are printed to stderr,
to avoid mixing them with the rendered document written to stdout.

The messages of the tool go through the Python standard `logging` machinery,
under the logger named `lucio`, and come out on stderr stamped with the UTC time and their level:

```
[2026-08-11T10:14:52.310Z] [DEBU] Input file: "/home/user/lucio/README.template.md"
[2026-08-11T10:14:52.310Z] [DEBU] Output file: "/home/user/lucio/README.md"
[2026-08-11T10:14:52.310Z] [DEBU] Check language: False
[2026-08-11T10:14:52.310Z] [DEBU] Omit do-not-edit comment: False
[2026-08-11T10:14:52.311Z] [DEBU] Overwrite files: True
[2026-08-11T10:14:52.311Z] [DEBU] Pager: False
[2026-08-11T10:14:52.311Z] [DEBU] Remove do-not-edit comment on include: False
[2026-08-11T10:14:52.311Z] [DEBU] Block timeout: 60.0 seconds
[2026-08-11T10:14:52.311Z] [DEBU] Total timeout: 300.0 seconds
[2026-08-11T10:14:52.312Z] [INFO] Rendering "README.template.md" into "README.md"...
[2026-08-11T10:14:52.318Z] [DEBU] README.template.md:12: executing bash block
[2026-08-11T10:14:52.402Z] [DEBU] README.template.md:12: exit code 0
[2026-08-11T10:14:52.404Z] [DEBU] README.template.md:24: including "PART.md"
[2026-08-11T10:14:52.406Z] [INFO] Rendering "README.template.md" into "README.md"... done
```

Messages at log level `INFO` and above are shown by default.
Use option `-v` / `--verbose` to show `DEBUG` messages.

The messages are colored according to their level when stderr is a terminal,
while option `-D` / `--do-not-color` turns coloration off.

### Timeouts

Two timeouts bound a run: each block is given 60 seconds, and the run as a whole is given 300 seconds.
Pass `-b` / `--block-timeout` and `-t` / `--total-timeout` to raise or lower either,
or the special value `-1` to disable it.

### Exit Codes

| Code | Meaning                                                                         |
|------|---------------------------------------------------------------------------------|
| `0`  | success: OUTPUT was written, or the document was printed on stdout              |
| `1`  | OUTPUT could not be written, or it exists and `--overwrite-files` was not given |
| `2`  | usage error (missing or bad arguments, INPUT and OUTPUT are the same file)      |
| `3`  | template error: syntax error, or INPUT cannot be read or decoded                |
| `4`  | execution error: unexpected exit code, timed-out block, `bash` not runnable     |

On any error other than `0`, OUTPUT is never opened and stdout stays empty:
a pre-existing OUTPUT is left exactly as it was.

### Newlines And Whitespace

- CRLF line endings in the template are normalized to LF on read;
  a lone CR is left alone.
- A captured stream is normalized to end with exactly one newline;
  a stream holding nothing but newlines counts as empty.
- The output file ends with exactly one newline.
- The do-not-edit comment and the blank line below it are the only bytes `lucio`
  adds of its own; issuing `-E` / `--omit-do-not-edit-comment` removes them.
- Everything else, whitespace included, is copied byte-for-byte.
- A fence is emitted with as many backticks as needed to wrap the captured
  output, even if it contains fences of its own. A merged fence grows only
  when the output demands it; as long as it does not, the closing line of the
  template is reused byte-for-byte.


## Template Syntax

Only fences whose info string has the trigger word `lucio`
as its second token are processed:

````
```LANGUAGE lucio [key=value ...]
```
````

A `command=execute` block, which is the default, is run by Bash,
so its language must be `bash`;
a `command=include` block may carry any language,
which is used to fence the file it reads.
The language is copied into the output and never interpreted,
and it is not checked unless `-L` / `--check-language` is given,
which validates it against the language names and aliases known to
[highlight.js](https://github.com/highlightjs/highlight.js/blob/main/SUPPORTED_LANGUAGES.md).

Anything else is ordinary Markdown:
```` ```bash ````, ```` ```bash lucioX ````, ```` ```bash run lucio ````,
```` ```lucio ````, ```` ```bash include ````, and `<!-- include FILE.md -->`
all pass through untouched, as does any trigger fence written inside a longer
fence (that is how the examples in this file survive).

### Trigger Blocks (`LANGUAGE lucio`)

The body of the block is executed by Bash, and the block is replaced by
its source fence and/or what the body printed:

````
```bash lucio command=execute
echo "Hello World"
```
````

renders as:

````
```bash
echo "Hello World"
Hello World
```
````

Note that the info string is reduced to `bash` in the output,
while the body and the closing fence are copied byte-for-byte.

By default the captured output is merged into the source fence,
right after the commands that produced it, the way a terminal transcript reads.
With `merge=false` it goes into a separate unlabeled fence instead,
one blank line below the source:

````
```bash lucio command=execute merge=false
echo "Hello World"
```
````

renders as two fenced blocks:

````
```bash
echo "Hello World"
```

```
Hello World
```
````

Either way, stdout comes first and stderr after it,
and if the selected streams are empty no output is emitted at all.
You can use stream redirection (e.g., `2>&1`) in the source block
to interleave the stdout/stderr contents.

#### Attributes

| Key           | Values                           | Default    | Applies To | Meaning                                                                            |
|---------------|----------------------------------|------------|------------|------------------------------------------------------------------------------------|
| `command`     | `execute`, `include`             | `include`  |            | what the block does                                                                |
| `exit`        | `any`, or int in `[0, 255]`      | `0`        | `execute`  | the exit code the block must exit with (if not, `lucio` run fails)                 |
| `merge`       | `true`, `false`                  | `true`     | `execute`  | put the captured output inside the source fence, rather than in a fence of its own |
| `path`        | a file path                      | N/A        | `include`  | the file `command=include` reads                                                   |
| `show_source` | `true`, `false`                  | `true`     | `execute`  | emit the source block, as a plain ```` ```bash ```` fence                          |
| `stderr`      | `true`, `false`                  | `true`     | `execute`  | include the captured stderr in the output                                          |
| `stdout`      | `true`, `false`                  | `true`     | `execute`  | include the captured stdout in the output                                          |
| `style`       | `fence`, `language`, `literal`   | `language` | `include`  | how the included file is wrapped                                                   |

Attributes are `key=value` tokens, separated by whitespace.
A value may be wrapped in double quotes, and must be if it contains spaces,
as in `path="/path/with spaces/FILE.md"`; the quotes come off before the value
is checked, so `stdout="true"` means exactly `stdout=true`.
Booleans are written `true` and `false`, lowercase like every other value;
attempting to use for instance `True`, `TRUE`, or `1` will produce an error.
Specifying unknown keys, keys not supported by the given `command`,
repeating a key, mispelled tokens or values will error out as well.

`merge` does nothing if `show_source=false` or there is no output to merge
(e.g., empty stdout/stderr contents, or `stdout=false` and `stderr=false`).

A block with `show_source=false stdout=false stderr=false` renders to nothing:
it is a hidden block that can be used to run "setup" commands
(e.g., creating or removing files, etc.) before other trigger blocks are executed.

Blank lines around hidden blocks are collapsed, so they leave no trace in the output.
Every block runs in the working directory `lucio` was invoked from,
so a hidden block can prepare files for the blocks below it:

````
```bash lucio command=execute show_source=false stdout=false stderr=false
rm -f ./configuration.yaml
echo "answer: 42" > ./myotherfile.yaml
```
````

As anticipated above, there are two types of trigger blocks,
depending on the `command` attribute: `command=include` blocks (default),
and `command=execute` blocks, described in the next subsections.

#### Blocks With `command=include`

````
```LANGUAGE lucio [command=include] path=/path/to/file/to/be/included [style=language]
```
````

The file named by `path` is read and put in place of the block:
no Bash execution is involved, and the block takes no attribute
other than `path` and `style`, nor body.
Timeouts do not apply, since no processing happens.

A relative `path` is resolved against **the directory of the template**,
so a template and the files it includes travel together and can be rendered from anywhere.
Note that this differs from the `command=execute` blocks, which run in the working
directory `lucio` was invoked from.

An absolute `path` is taken as it is. A leading `~` and any `$VARIABLE` or
`${VARIABLE}` are expanded first, so a template can name a file outside its own tree
without hard-coding a machine; naming a variable that is not set aborts the run,
rather than silently reading from the wrong place.

The `style` attribute says how the file is wrapped:

| Value      | Result                                                                |
|------------|------------------------------------------------------------------------|
| `fence`    | the file inside a fence with no language                              |
| `language` | the file inside a fence carrying the language of the trigger (default) |
| `literal`  | the file pasted raw, as Markdown                                      |

So, if `configuration.yaml` contains `answer: 42`, the block:

````
```yaml lucio command=include path=configuration.yaml
```
````

renders as:

````
```yaml
answer: 42
```
````

while `style=fence` emits the same fence without the `yaml` label,
and `style=literal` pastes `answer: 42` alone.
The language is still the first token of the info string
even when `style=literal` makes no use of it.
The emitted fence grows as needed to clear any backtick run in the file,
and it always sits at column 0.
An empty file contributes nothing, whatever the style.

The file is never interpreted: a trigger fence inside it is text,
not something `lucio` renders in turn.
A file that cannot be read aborts the run, like any other failing block.

Including a file that `lucio` generated might paste its do-not-edit comment along with it,
in the middle of the main document and even possibly naming the wrong template.
Option `-R` / `--remove-do-not-edit-comment-on-include` drops that opening comment
and the blank line below it, from every file included in the run:

````
```markdown lucio command=include path=PART.md style=literal
```
````

```
PART.md, itself rendered by lucio:      included with -R:

<!-- This file PART.md has ... -->      ## Part

## Part                                 Text.

Text.
```

Only the first line is considered, and only when it is a comment `lucio` itself
would have written: licence headers, linter directives, another generator's
banners, etc. are left unchanged.

Note that `-R` is about the file being read,
while `-E` is about the file being written;
a run of `lucio` can use either, both or neither.


#### Blocks With `command=execute`

**IMPORTANT**: currently only `LANGUAGE=bash` blocks support `command=execute`.

````
```bash lucio [command=execute] [exit=0] [show_source=true] [stdout=true] [stderr=true] [merge=true]
# write any Bash command(s) to be executed as the block body
echo "Hello World"
touch /tmp/myfile
```
````

Each block is executed in its own Bash subprocess,
with the body passed verbatim and nothing injected into it,
so shell state (variables, `cd`, functions) does not carry over from one block to the next;
the filesystem, of course, does.

If a block exits with a code other than the expected one, the whole run is aborted
and OUTPUT is not written.
Expected failures must declared with `exit` to prevent that:

````
```bash lucio exit=1
cat missing_file.txt
```
````

Specify `exit=any` to accept whatever return code the block returns.

The verbose log will show something similar to the following:

```
[2026-08-11T10:14:52.402Z] [DEBU] README.template.md:12: exit code 1 (permitted by exit=1)
[2026-08-11T10:14:53.118Z] [DEBU] README.template.md:24: exit code 3 (permitted by exit=any)
```



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
