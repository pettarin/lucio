# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [0.0.3] - 2026-08-11

### Added

- Derive OUTPUT from an INPUT named `NAME.template.md`, rendering it into `NAME.md`
- Print the rendered document on stdout when OUTPUT is omitted, or when it is `-`
- `-O` / `--overwrite-files` option, required to overwrite an existing OUTPUT
- `--color` / `--no-color` option

### Changed

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

