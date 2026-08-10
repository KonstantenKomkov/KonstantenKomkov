"""Allowlisted language names from a pinned GitHub Linguist registry."""

LINGUIST_LANGUAGES_COMMIT = "46e68a1dec7765b602ec9601693b10e0763436b1"

ALLOWED_LINGUIST_LANGUAGES = frozenset(
    """
1C Enterprise
2-Dimensional Array
4D
ABAP
ABAP CDS
ABNF
AGS Script
AIDL
AL
ALGOL
AMPL
ANTLR
API Blueprint
APL
ASL
ASN.1
ASP.NET
ATS
ActionScript
Ada
Adblock Filter List
Adobe Font Metrics
Agda
Aiken
Alloy
Alpine Abuild
Altium Designer
AngelScript
Answer Set Programming
Ant Build System
Antlers
ApacheConf
Apex
Apollo Guidance Computer
AppleScript
Arc
AsciiDoc
AspectJ
Assembly
Astro
Asymptote
Augeas
AutoHotkey
AutoIt
Avro IDL
Awk
B (Formal Method)
B4X
BAML
BASIC
BBCode
BIRD2
BQN
Ballerina
Batchfile
Beef
Befunge
Berry
BibTeX
BibTeX Style
Bicep
Bikeshed
Bison
BitBake
Blade
BlitzBasic
BlitzMax
Blueprint
Bluespec
Bluespec BH
Boo
Boogie
Brainfuck
BrighterScript
Brightscript
Browserslist
Bru
BuildStream
C
C#
C++
C-ObjDump
C2hs Haskell
C3
CAP CDS
CIL
CLIPS
CMake
COBOL
CODEOWNERS
COLLADA
CQL
CSON
CSS
CSV
CUE
CWeb
Cabal Config
Caddyfile
Cadence
Cairo
Cairo Zero
CameLIGO
Cangjie
Cap'n Proto
Carbon
CartoCSS
Ceylon
Chapel
Charity
Checksums
ChucK
Circom
Cirru
Clarion
Clarity
Classic ASP
Clean
Click
Clojure
Closure Templates
Cloud Firestore Security Rules
Clue
CoNLL-U
CodeQL
CoffeeScript
ColdFusion
ColdFusion CFC
Common Lisp
Common Workflow Language
Component Pascal
Cooklang
Cool
Cpp-ObjDump
Creole
Crystal
Csound
Csound Document
Csound Score
Cuda
Cue Sheet
Curry
Cycript
Cylc
Cypher
Cython
D
D-ObjDump
D2
DIGITAL Command Language
DM
DNS Zone
DTrace
Dafny
Darcs Patch
Dart
Daslang
DataWeave
Debian Package Control File
DenizenScript
Dhall
Diff
DirectX 3D File
Dockerfile
Dogescript
Dotenv
Dune
Dylan
E
E-mail
EBNF
ECL
ECLiPSe
EJS
EQ
Eagle
Earthly
Easybuild
Ecere Projects
Ecmarkup
Edge
EdgeQL
EditorConfig
Edje Data Collection
Eiffel
Elixir
Elm
Elvish
Elvish Transcript
Emacs Lisp
EmberScript
Erlang
Euphoria
F#
F*
FIGlet Font
FIRRTL
FLUX
Factor
Fancy
Fantom
Faust
Fennel
Filebench WML
Filterscript
FlatBuffers
Flix
Fluent
Formatted
Forth
Fortran
Fortran Free Form
FreeBASIC
FreeMarker
Frege
Futhark
G-code
GAML
GAMS
GAP
GCC Machine Description
GDB
GDScript
GDShader
GEDCOM
GLSL
GN
GSC
Game Maker Language
Gemfile.lock
Gemini
Genero 4gl
Genero per
Genie
Genshi
Gentoo Ebuild
Gentoo Eclass
Gerber Image
Gettext Catalog
Gherkin
Git Attributes
Git Commit
Git Config
Git Revision List
Gleam
Glimmer JS
Glimmer TS
Glyph
Glyph Bitmap Distribution Format
Gno
Gnuplot
Go
Go Checksums
Go Module
Go Template
Go Workspace
Godot Resource
Golo
Gosu
Grace
Gradle
Gradle Kotlin DSL
Grammatical Framework
Graph Modeling Language
GraphQL
Graphviz (DOT)
Groovy
Groovy Server Pages
GtkRC
HAProxy
HCL
HIP
HLSL
HOCON
HTML
HTML+ECR
HTML+EEX
HTML+ERB
HTML+PHP
HTML+Razor
HTTP
HXML
Hack
Haml
Handlebars
Harbour
Hare
Haskell
Haxe
HiveQL
HolyC
Hosts File
Hurl
Hy
HyPhy
IDL
IGOR Pro
IL Assembly
INI
IRC log
ISPC
Idris
Ignore List
ImageJ Macro
Imba
Inform 7
Ink
Inno Setup
Io
Ioke
Isabelle
Isabelle ROOT
J
JAR Manifest
JASS
JCL
JFlex
JSON
JSON with Comments
JSON5
JSONLD
JSONiq
Jac
Jai
Janet
Jasmin
Java
Java Properties
Java Server Pages
Java Template Engine
JavaScript
JavaScript+ERB
Jest Snapshot
JetBrains MPS
Jinja
Jison
Jison Lex
Jolie
Jsonnet
Julia
Julia REPL
Jupyter Notebook
Just
KCL
KDL
KFramework
KRL
Kaitai Struct
KakouneScript
KerboScript
KiCad Layout
KiCad Legacy Layout
KiCad Schematic
Kickstart
Kit
KoLmafia ASH
Koka
Kotlin
Kusto
LFE
LLVM
LOLCODE
LSL
LTspice Symbol
LabVIEW
Lambdapi
Langium
Lark
Lasso
Latte
Lean
Lean 4
Leo
Less
Lex
LigoLANG
LilyPond
Limbo
Linear Programming
Linker Script
Linux Kernel Module
Liquid
Liquidsoap
Literate Agda
Literate CoffeeScript
Literate Haskell
LiveCode Script
LiveScript
Lobster
Logos
Logtalk
LookML
LoomScript
Lua
Luau
M
M3U
M4
M4Sugar
MATLAB
MAXScript
MDX
MLIR
MQL4
MQL5
MTML
MUF
Macaulay2
Makefile
Mako
Markdown
Marko
Mask
Mathematical Programming System
Maven POM
Max
MeTTa
Mercury
Mermaid
Meson
Metal
Microsoft Developer Studio Project
Microsoft Visual Studio Solution
MiniD
MiniScript
MiniYAML
MiniZinc
MiniZinc Data
Mint
Mirah
Modelica
Modula-2
Modula-3
Module Management System
Mojo
Monkey
Monkey C
Moocode
MoonBit
MoonScript
Motoko
Motorola 68K Assembly
Move
Muse
Mustache
Myghty
NASL
NCL
NEON
NL
NMODL
NPM Config
NSIS
NWScript
Nasal
Nearley
Nemerle
NetLinx
NetLinx+ERB
NetLogo
NewLisp
Nextflow
Nginx
Nickel
Nim
Ninja
Nit
Nix
Noir
Nu
NumPy
Nunjucks
Nushell
OASv2-json
OASv2-yaml
OASv3-json
OASv3-yaml
OCaml
OMNeT++ MSG
OMNeT++ NED
Oberon
ObjDump
Object Data Instance Notation
ObjectScript
Objective-C
Objective-C++
Objective-J
Odin
Omgrofl
Opa
Opal
Open Policy Agent
OpenAPI Specification v2
OpenAPI Specification v3
OpenCL
OpenEdge ABL
OpenQASM
OpenRC runscript
OpenSCAD
OpenStep Property List
OpenType Feature File
Option List
Org
OverPy
OverpassQL
Ox
Oxygene
Oz
P4
PDDL
PEG.js
PHP
PLSQL
PLpgSQL
POV-Ray SDL
Pact
Pan
Papyrus
Parrot
Parrot Assembly
Parrot Internal Representation
Pascal
Pawn
Pep8
Perl
Pic
Pickle
PicoLisp
PigLatin
Pike
Pip Requirements
Pkl
PlantUML
Pod
Pod 6
PogoScript
Polar
Pony
Portugol
PostCSS
PostScript
Power Query
PowerBuilder
PowerShell
Praat
Prisma
Pro*C
Processing
Procfile
Proguard
Prolog
Promela
Propeller Spin
Protocol Buffer
Protocol Buffer Text Format
Public Key
Pug
Puppet
Pure Data
PureBasic
PureScript
Pyret
Python
Python console
Python traceback
Q#
QML
QMake
Qt Script
Quake
QuakeC
QuickBASIC
Quint
R
RAML
RAScript
RBS
RDoc
REALbasic
REXX
RMarkdown
RON
ROS Interface
RPC
RPGLE
RPM Spec
RUNOFF
Racket
Ragel
Raku
Rascal
Raw token data
ReScript
Readline Config
Reason
ReasonLIGO
Rebol
Record Jar
Red
Redcode
Redirect Rules
Redscript
Regular Expression
Ren'Py
RenderScript
Rez
Rich Text Format
Ring
Riot
RobotFramework
Robots Exclusion Rules
Roc
Rocq Prover
Roff
Roff Manpage
Rouge
RouterOS Script
Ruby
Rust
SAS
SCSS
SELinux Policy
SMT
SPARQL
SQF
SQL
SQLPL
SRecode Template
SSH Config
STAR
STL
STON
SVG
SWIG
Sage
Sail
Salt
Sass
Scala
Scaml
Scenic
Scheme
Scilab
Self
ShaderLab
Shell
ShellCheck Config
ShellSession
Shen
Sieve
Simple File Verification
Singularity
Slang
Slash
Slice
Slim
Slint
SmPL
Smali
Smalltalk
Smarty
Smithy
Snakemake
Solidity
Soong
SourcePawn
SpiceDB Schema
Spline Font Database
Squirrel
Stan
Standard ML
Starlark
Stata
StringTemplate
Stylus
SubRip Text
SugarSS
SuperCollider
SurrealQL
Survex data
Svelte
Sway
Sweave
Swift
SystemVerilog
TI Program
TL-Verilog
TLA
TMDL
TOML
TSPLIB data
TSQL
TSV
TSX
TXL
Tact
Talon
Tape
Tcl
Tcsh
TeX
Tea
Teal
Terra
Terraform Template
Texinfo
Text
TextGrid
TextMate Properties
Textile
Thrift
Toit
Tolk
Tor Config
Tree-sitter Query
Turing
Turtle
Twig
Type Language
TypeScript
TypeSpec
Typst
Unified Parallel C
Unity3D Asset
Unix Assembly
Uno
UnrealScript
Untyped Plutus Core
UrWeb
V
VBA
VBScript
VCL
VHDL
Vala
Valve Data Format
Velocity Template Language
Vento
Verilog
Verse
Vim Help File
Vim Script
Vim Snippet
Visual Basic .NET
Visual Basic 6.0
Volt
Vue
Vyper
WDL
WGSL
Wavefront Material
Wavefront Object
Web Ontology Language
WebAssembly
WebAssembly Interface Type
WebIDL
WebVTT
Wget Config
Whiley
Wikitext
Win32 Message File
Windows Registry Entries
Witcher Script
Wolfram Language
Wollok
World of Warcraft Addon Data
Wren
X BitMap
X Font Directory Index
X PixMap
X10
XC
XCompose
XML
XML Property List
XPages
XProc
XQuery
XS
XSLT
Xmake
Xojo
Xonsh
Xtend
YAML
YANG
YARA
YASnippet
Yacc
Yul
ZAP
ZIL
Zeek
ZenScript
Zephir
Zig
Zimpl
Zmodel
cURL Config
crontab
desktop
dircolors
eC
edn
fish
hoon
iCalendar
jq
kvlang
mIRC Script
mcfunction
mdsvex
mupad
nanorc
nesC
ooc
pkg-config
q
reStructuredText
sed
templ
ucode
vCard
wisp
xBase
""".strip().splitlines()
)
