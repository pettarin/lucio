"""The language names a fence may carry, as known to highlight.js.

Only ``--check-language`` consults this: a language is otherwise copied into the emitted
fence and never interpreted. The list is a snapshot of the SUPPORTED_LANGUAGES.md
document of highlight.js, and drifts as upstream adds languages.

:copyright: Copyright (C) 2026 Alberto Pettarin
:license: GNU General Public License v3.0 (see the LICENSE file for details)
"""

# Generated values: run "make update-languages" to refresh them from highlight.js
LANGUAGES = frozenset(
    {
        "1c", "4d", "abap", "abc", "abnf", "accesslog", "actionscript", "ada", "adoc", "aiken",
        "ak", "alan", "angelscript", "apache", "apacheconf", "apex", "applescript", "arcade",
        "arduino", "arm", "armasm", "as", "asc", "asciidoc", "aspectj", "atom", "autohotkey",
        "autoit", "avrasm", "awk", "axapta", "bal", "ballerina", "bash", "basic", "bat",
        "batch", "bbcode", "bf", "bicep", "bind", "blade", "bnf", "bqn", "brainfuck", "c",
        "c++", "c3", "cal", "candid", "capnp", "capnproto", "cc", "cedar", "cedarschema",
        "chaos", "chapel", "chpl", "cisco", "clj", "clojure", "cls", "cmake", "cmake.in", "cmd",
        "cobol", "codeowners", "coffee", "coffeescript", "console", "coq", "cos", "cpc", "cpp",
        "cr", "craftcms", "crm", "crmsh", "crystal", "cs", "csharp", "cshtml", "cson", "csp",
        "css", "cts", "curl", "cxx", "cypher", "d", "dafny", "dart", "dax", "desktop", "dfm",
        "did", "diff", "dj", "django", "djot", "dns", "docker", "dockerfile", "dos", "dpr",
        "dsconfig", "dst", "dts", "dust", "dylan", "ebnf", "elixir", "elm", "erl", "erlang",
        "esql", "excel", "extempore", "f90", "f95", "fix", "flix", "fortran", "freedesktop",
        "fs", "fsharp", "fsi", "fsscript", "fsx", "func", "gams", "gauss", "gawk", "gcode",
        "gdscript", "gemspec", "gf", "gherkin", "gleam", "glimmer", "glsl", "gml", "gms", "gn",
        "gni", "go", "godot", "golang", "golo", "gololang", "gql", "gradle", "graph", "graphql",
        "groovy", "gsql", "gss", "gyp", "h", "h++", "haml", "handlebars", "haskell", "haxe",
        "hbs", "hcl", "hh", "hlsl", "hpp", "hs", "html", "html.handlebars", "html.hbs",
        "htmlbars", "http", "https", "hx", "hxx", "hy", "hylang", "i", "i7", "iced", "iecst",
        "igor", "igorpro", "inform7", "ini", "ino", "instances", "iol", "ipf", "iptables",
        "irb", "irpf90", "jaiva", "java", "javascript", "jinja", "jiv", "jl", "jolie", "js",
        "json", "json5", "jsonata", "jsonc", "jsp", "jsx", "julia", "julia-repl", "jva", "k",
        "kaos", "kdb", "kotlin", "kt", "ktm", "kts", "ktx", "l4", "lasso", "lassoscript",
        "ldif", "leaf", "lean", "legal", "less", "liq", "liquid", "lisp", "livecodeserver",
        "livescript", "llvm", "ln", "lookml", "lotusscript", "ls", "lss", "lua", "luau", "m",
        "macaulay2", "magik", "mak", "make", "makefile", "markdown", "mathematica", "matlab",
        "mawk", "maxima", "mbt", "md", "mel", "mercury", "metapost", "mint", "mips", "mipsasm",
        "mirc", "mirth", "mizar", "mk", "mkb", "mkd", "mkdown", "ml", "mlir", "mlw", "mm",
        "mma", "mo", "mojolicious", "monkey", "moon", "moonbit", "moonscript", "motoko", "mrc",
        "mts", "n1ql", "nawk", "nc", "never", "nginx", "nginxconf", "nim", "nimrod", "nix",
        "nsis", "oak", "obj-c", "obj-c++", "objc", "objective-c++", "objectivec", "ocaml",
        "ocl", "odin", "ol", "openscad", "osascript", "oxygene", "p21", "p6", "papyrus",
        "parser3", "pas", "pascal", "patch", "pcmk", "perl", "perl6", "pf", "pf.conf", "pgsql",
        "phix", "php", "pine", "pinescript", "pkl", "pl", "plaintext", "plist", "pluto", "pm",
        "pm6", "po", "pod6", "podspec", "pony", "postgres", "postgresql", "poweron",
        "powershell", "pp", "pq", "prg", "prisma", "processing", "profile", "prolog",
        "properties", "proto", "protobuf", "ps", "ps1", "psc", "puppet", "pwsh", "py", "pycon",
        "python", "python-repl", "qml", "qsharp", "r", "raku", "rakudoc", "rakumod",
        "rakuquoting", "rakuregexe", "rascript", "razor", "razor-cshtml", "rb", "re",
        "reasonml", "rebol", "red", "red-system", "redbol", "res", "rescript", "rf", "rib",
        "risc", "riscript", "riscv", "riscvasm", "robot", "rpm", "rpm-spec", "rpm-specfile",
        "rs", "rsl", "rss", "ruby", "ruleslanguage", "rust", "rvt", "rvt-script", "sap-abap",
        "sas", "sc", "scad", "scala", "scheme", "sci", "scilab", "scl", "scss", "sfz", "sh",
        "shell", "shexc", "smali", "smalltalk", "sml", "sol", "solidity", "spec", "specfile",
        "spl", "sql", "st", "stan", "standard-cobol", "stanfuncs", "stata", "step", "stl",
        "stp", "structured-text", "styl", "stylus", "subunit", "supercollider", "svelte", "svg",
        "swift", "systemd", "tao", "tap", "tcl", "terraform", "tex", "text", "tf", "thor",
        "thrift", "tk", "toit", "toml", "tp", "ts", "tsql", "tsx", "ttcn", "ttcn3", "ttcnpp",
        "twig", "txt", "typescript", "u", "unicorn-rails-log", "unison", "v", "vala", "vb",
        "vba", "vbnet", "vbs", "vbscript", "verilog", "veryl", "vhdl", "vim", "voltscript",
        "vss", "wgsl", "whyml", "wl", "x++", "x86asm", "x86asmatt", "xhtml", "xjb", "xl", "xls",
        "xlsx", "xml", "xojo", "xpath", "xq", "xqm", "xquery", "xs", "xsd", "xsharp", "xsl",
        "xtlang", "xtm", "yaml", "yml", "zenscript", "zep", "zephir", "zig", "zone", "zs", "zsh"
    }
)
"""Every alias of the table, lowercased; a written language is matched case-insensitively."""
