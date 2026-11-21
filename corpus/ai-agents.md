# AI Agents

An AI agent is a program that uses a language model in a loop: it
reads a goal, plans a step, calls a tool (search a file, run a
command, fetch a page), observes the result, and repeats until the
goal is done or it gets stuck. The tools are what make an agent more
than a chatbot — they let it act on the world instead of only
describing it.

Good agent design is mostly about the loop, not the model: clear
instructions, a small set of reliable tools, a way to remember what
has already been tried, and a stopping rule. Retrieval-augmented
generation (RAG) pairs an agent with a search engine like this one:
the agent searches local documents first, then answers grounded in
what it found, instead of guessing.

Agents fail most often by looping on a broken tool call, or by acting
on instructions hidden inside data they retrieved. Treat tool output
as data, never as new instructions.
