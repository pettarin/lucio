# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [0.0.5] - 2026-08-11

### Changed

- Spell the boolean attribute values `true` and `false`, lowercase like every other
  value; `True` and `False` are now errors, as their lowercase forms used to be
- Report the do-not-edit setting as its option states it, `Omit do-not-edit comment: False`,
  rather than as the negation it used to log


## [0.0.4] - 2026-08-11

### Added

- `command=include` with a `path` attribute, reading the file directly, with a relative
  path resolved against the directory of the template
- `-R` / `--remove-do-not-edit-comment-on-include` option, stripping the do-not-edit
  comment, and the blank line below it, from an included file that `lucio` generated

### Removed

- The `bash include` trigger, superseded by `command=include`; such a fence is now
  ordinary Markdown, and its `cat FILE.md` body is no longer needed


## [0.0.3] - 2026-08-11

### Added

- Derive OUTPUT from an INPUT named `NAME.template.md` or `NAME.tmd`, rendering it
  into `NAME.md`
- Print the rendered document on stdout when OUTPUT is omitted, or when it is `-`
- `-O` / `--overwrite-files` option, required to overwrite an existing OUTPUT
- `-D` / `--do-not-color` option
- `-P` / `--pager` option, printing the document through a pager when on a terminal
- `-V` as short form of `--version`
- `-t` / `--total-timeout` option, bounding the whole run, 300 seconds by default
- Open the rendered document with a comment naming the template it came from,
  omitted by the `-E` / `--omit-do-not-edit-comment` option
- Log the settings of the run at `DEBUG` level, before the first block is executed:
  the resolved input and output paths, the overwrite flag, and the block timeout

### Changed

- Report a run as a pair of `INFO` lines, `Rendering "IN" into "OUT"...` before the work
  and the same with `done` after it, in place of the single line once it was over
- Rename `--timeout` to `-b` / `--block-timeout`, default it to 60 seconds, and accept
  `-1` for no timeout at all
- Name the attribute that permitted a non-zero exit code in the verbose log,
  as `exit code 1 (permitted by exit=1)`
- Log the messages of the tool through the `lucio` logger, as
  `[UTC timestamp] [LEVEL] message` on stderr, colored when the terminal supports it;
  one `INFO` line per run reports what was rendered, and `--verbose` adds the `DEBUG` ones


## [0.0.2] - 2026-08-11

### Changed

- Rewrite the development document to describe lucio: setup, project structure, and modules
- Describe the tool as executing "shell or code blocks", in view of a future generalization


## [0.0.1] - 2026-08-11

### Added

- Initial release

