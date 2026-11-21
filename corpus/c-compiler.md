# C Compiler Basics

A C compiler turns human-readable C source code into machine code the
processor can run. The pipeline has four stages: preprocessing
(expanding `#include` and macros), compiling (translating C into
assembly), assembling (assembly into object files), and linking
(combining object files and libraries into an executable).

GCC is the most common C compiler on Linux. `gcc -O2 -Wall main.c -o
main` compiles with optimisation and warnings enabled. The compiler
performs lexical analysis (tokens), parsing (an abstract syntax tree),
semantic analysis (types and scopes), optimisation, and code
generation — the same layered design as an interpreter, with machine
code as the output instead of execution.

Writing a small compiler for a subset of C is a classic learning
project: a tokenizer, a recursive-descent parser, and a code
generator that emits x86-64 assembly are enough to compile simple
programs with variables, arithmetic, and functions.
