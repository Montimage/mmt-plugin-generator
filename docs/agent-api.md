# mmt-plugin-agent: the skill, headless

`mmt-plugin-agent` runs the [mmt-plugin-generator
skill](../skills/mmt-plugin-generator/SKILL.md) without a coding assistant:
a [LangGraph](https://github.com/langchain-ai/langgraph) agent, built with
[deepagents](https://github.com/langchain-ai/deepagents), reads the skill
and drives `mmt-plugin`'s loop (`validate`, `generate`, `build`, `test`)
from its `--json` envelopes, with any chat model LangChain supports. It has
a command line, `mmt-plugin-agent`, and a Python API, `mmt_plugin_agent`;
the command line calls only the API.

## Install

The agent is the `agent` extra of the `mmt-plugin` distribution, and needs
Python 3.11 or newer (deepagents does). `pip install mmt-plugin` without
the extra still installs only jinja2. On Python 3.10 the extra installs
nothing, and `mmt-plugin-agent` says so (exit 4, `agent.needs-extra`).

From a checkout:

```sh
uv sync --extra agent
uv run mmt-plugin-agent doctor
```

From a built wheel:

```sh
pip install 'mmt_plugin-<version>-py3-none-any.whl[agent]'
```

The agent reads the skill from a skills directory: `--skills DIR` (or
`skills_dir=`), else `MMT_PLUGIN_SKILLS`, else the checkout's `skills/`,
else the agent image's `/opt/mmt-plugin-skills`. An installed wheel has no
checkout: pass `--skills` or set `MMT_PLUGIN_SKILLS`.

`mmt-plugin-agent doctor` lists what a run needs, each check `pass`,
`warn` or `fail` with a hint, and exits 4 when one fails: Python and the
extra, `mmt-plugin` on `PATH`, the SDK prefix and the compiler (through
`mmt-plugin --json doctor`), tshark, capinfos, editcap and mergecap,
libpcap's headers, cyberlab, Docker, the skills directory, `HOME` and the
model. A missing tshark, Docker or cyberlab is a warning: the skill works
around it (no drift check; synthetic captures only, with leave).

## The container

The `agent` stage of the `Dockerfile` is the place to run the agent: it
holds mmt-dpi as a private prefix (`/opt/sdk`, `MMT_BASE`), gcc and clang,
tshark, libpcap's headers, a docker CLI, mmt-plugin with the agent extra
from `uv.lock`, and the skills, root-owned and read-only, in
`/opt/mmt-plugin-skills`. The agent runs as the unprivileged user `agent`.

```sh
make agent-image
make agent-run AGENT_ARGS='new --spec /in/skills/mmt-plugin-generator/evals/cases/spec-telem/spec.md --unattended --allow-synthetic --model anthropic:claude-sonnet-5-5 --json'
```

`agent-run` mounts the current directory read-only at `/in` and
`./agent-work` as the work folder, and passes the model's settings
(`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OLLAMA_HOST`,
`MMT_PLUGIN_AGENT_MODEL`, `MMT_PLUGIN_AGENT_NUM_CTX`) from your environment by name. cyberlab is not
in the image, and the image has no Docker socket: see [The
sandbox](#the-sandbox).

## Models

A model is a `provider:model` string, which LangChain's `init_chat_model`
resolves, or a LangChain chat model object (`model=` in the API). Without
`--model`, `MMT_PLUGIN_AGENT_MODEL` is used. The extra installs three
integrations:

| Provider | `--model` | Settings |
|---|---|---|
| Anthropic | `anthropic:claude-sonnet-5-5` | `ANTHROPIC_API_KEY` |
| vLLM, or any OpenAI-compatible server | `openai:<served model name>` | `OPENAI_BASE_URL` (the server's `/v1` URL), `OPENAI_API_KEY` (any value the server accepts) |
| Ollama | `ollama:<model>`, e.g. `ollama:qwen3-coder` | `OLLAMA_HOST` when it is not `localhost:11434`; `MMT_PLUGIN_AGENT_NUM_CTX`, the context length (`num_ctx`) in tokens, 65536 by default |

The model needs tool calling. Ollama's own context length (2048 or 4096
tokens) is shorter than the agent's system prompt and tools, and Ollama
then drops the start of the conversation, the request with it: the agent
passes `num_ctx` to an `ollama:` model, 65536 tokens unless
`MMT_PLUGIN_AGENT_NUM_CTX` says otherwise (a model object is used as it
is). Keys stay in the environment: the agent's
shell never sees a variable whose name ends in `_API_KEY` or `_TOKEN`, or
holds `SECRET`, `PASSWORD` or `CREDENTIAL`, and `doctor` never prints one.

## Run modes

- `--unattended` (the default): no user answers. Each question the skill
  asks goes to `<work>/questions.md` with the recommended answer and the
  default taken, and the run goes on; it never reads stdin and never uses
  `--force`. A question with no safe default stops the run, `BLOCKED`.
- `--interactive`: each question is printed on stderr and the answer read
  from stdin; the run then resumes where it stopped (the same LangGraph
  thread). `--force` runs only after a yes.

The capture question (the skill's Step 1): when no capture is given
(`--capture FILE`) or found, the skill asks for one, for leave to make a
synthetic one, or for leave to skip the evaluation. `--allow-synthetic`
answers it with a synthetic capture; unattended without it, the evaluation
is skipped and reported as not done (status `incomplete`, exit 0, the
warning `agent.evaluation-not-done`). With `--capture` or `--allow-synthetic`
and an SDK, a green run whose evaluation is not done skipped the
evaluation it had leave for: status `incomplete` with `eval_leave` set,
`ok` false, exit 6 (`agent.evaluation-skipped`). `--no-eval` skips the
evaluation.

A `questions.md` entry:

```text
## Q1: No capture was given or found. Give a capture, allow a synthetic one, or skip?
Recommended: a synthetic capture
Taken: skip the evaluation; it is reported as not done
```

## The command line

```sh
mmt-plugin-agent new --spec FILE | --pcap FILE | --pdl FILE [options]
mmt-plugin-agent update PROJECT --change FILE|TEXT [options]
mmt-plugin-agent doctor [--sdk PREFIX] [--cc CC] [--skills DIR] [--model M]
mmt-plugin-agent eval --model M [--model M ...] --out FILE [--case ID] [--sdk PREFIX]
mmt-plugin-agent --version
```

The options of `new` and `update`: `--sdk PREFIX` (default `MMT_BASE`),
`--cc` (default `CC`, else gcc), `--work DIR` (default
`./plugin-work-<id>` for `new`, `<project>-work` next to the project for
`update`), `--model`, `--unattended` or `--interactive`, `--capture`,
`--allow-synthetic`, `--no-eval`, `--skills`, `--thread-id` and
`--instructions TEXT` (more for the request, such as the label, id and
parent to use). `--json` prints one envelope.

The envelope follows `mmt-plugin`'s
([`docs/design/cli.md`](design/cli.md), sections 5 and 6): `schema_version`
1, `tool`, `command`, `ok`, `exit_code`, `error` (`class`, `code`,
`message`, `hint`), `diagnostics`, `context` and `result`. Its JSON Schemas
are in `src/mmt_plugin_agent/schemas/v1/`: `envelope.json`, and
`result.json` for `new` and `update`. Codes are `agent.*`.

| Exit | Class | When |
|---|---|---|
| 0 | success | Done, or green with the evaluation not done (`incomplete`) and no `--capture` or `--allow-synthetic`. |
| 1 | internal | The model's provider failed (a bad key, a rate limit, an endpoint down) or an I/O error (`agent.unexpected`, its message without secrets), a bug, or the run returned no result. |
| 2 | usage | Bad arguments, no model (`agent.no-model`), a model string without a provider (`agent.bad-model`). |
| 3 | model | An input that is not there (`agent.bad-input`). |
| 4 | sdk | The environment: no Python 3.11 or extra (`agent.needs-extra`), no skills (`agent.skills-not-found`), an SDK prefix under `/opt/mmt` (`agent.system-sdk`: extract the package into a private prefix), `doctor` with a failed check (`agent.doctor-failed`). |
| 6 | test | Not green (`agent.not-green`), the evaluation failed (`agent.eval-failed`), green with the evaluation not done although `--capture` or `--allow-synthetic` gave leave for it (`agent.evaluation-skipped`), `BLOCKED` (`agent.blocked`), the skills were changed (`agent.skills-modified`, even when the run then failed), an eval case failed (`agent.eval-cases-failed`). |
| 130 | interrupted | Ctrl-C. |

## The Python API

```python
from mmt_plugin_agent import PluginAgent
```

`PluginAgent(model=None, *, sdk=None, cc=None, work_dir=None,
mode="unattended", capture=None, allow_synthetic=False, no_eval=False,
skills_dir=None, extra_skills=(), tools=(), on_question=None,
checkpointer=None, timeout=900)` takes what the command line takes; its
methods are:

- `new(spec=|pcap=|pdl=, instructions=None, thread_id=None)` and
  `update(project, change=, ...)` return an `AgentResult`; `anew` and
  `aupdate` are their async forms.
- `stream(...)` (and `astream`) takes the arguments of `new`, or
  `project=` and `change=`, and yields `AgentEvent`s: `step` (a tool call of
  the model), `command` (a shell command that ran or was refused),
  `envelope` (its mmt-plugin envelope), `loop` (a loop run that ended),
  `question` (a run waiting for an answer) and `done`, whose `result` is the
  `AgentResult`. Every loop command gives a `step`, a `command` and an
  `envelope` event.
- `resume(thread_id, answer)` (and `stream_resume`) answers the question
  a `waiting` run stopped at, in the same `PluginAgent`; `release(thread_id)`
  forgets a `waiting` run that will not be resumed (it removes the run's
  skills snapshot). A run that ends, fails, is interrupted or whose events
  are no longer read is released on its own.
- `doctor()` returns the `DoctorReport` of `mmt-plugin-agent doctor`.

`AgentResult` has `status` (`done`, `incomplete`, `eval_failed`,
`not_green`, `blocked`, `failed`, `waiting`), `ok`, `thread_id`, `work`,
`project`, `loop` (the last loop run: its commands' exit codes, the test
summary, `green(with_sdk)`; read from the envelopes the skill saves in
`<work>/runs/run-<n>/` during this run, else from the shell commands, each
with mmt-plugin's exit code from its envelope), `loop_runs`, `evaluation` (`pass`, `fail`,
`not_done`, `skipped`, from `manifest.json`), `drift` (the open drifts),
`unchecked`, `report_path`, `questions_path`, `question`,
`skills_modified`, `commands`, `message` (the model's last reply) and
`eval_leave` (`capture`, `synthetic` or `None`: the leave the run had for
the evaluation; `skipped_with_leave` is an `incomplete` run that had it,
and is not `ok`); `to_json()` is the command line's `result`.

This example runs in CI with a scripted model
(`tests/unit/agent/test_docs_example.py`):

<!-- agent-api:run -->
```python
from mmt_plugin_agent import PluginAgent

agent = PluginAgent(
    "anthropic:claude-sonnet-5-5",
    work_dir="telem-work",
    allow_synthetic=True,
)
result = agent.new(spec="skills/mmt-plugin-generator/evals/cases/spec-telem/spec.md")
print(result.status, result.work.name, result.loop_runs)
for item in result.unchecked:
    print("not checked:", item)
```

Questions in your own code: `on_question` gets each `Question` (`kind`
`capture`, `force` or `other`, `text`, `recommended`) and returns the
answer, in either mode:

```python
from mmt_plugin_agent import PluginAgent, Question


def answer(question: Question) -> str:
    if question.kind == "capture":
        return "allow a synthetic capture"
    return question.recommended


agent = PluginAgent("ollama:qwen3-coder", on_question=answer)
for event in agent.stream(spec="spec.md"):
    print(event.kind, event.message)
```

Without `on_question`, an interactive run stops with status `waiting` and
`result.question`; `agent.resume(result.thread_id, "my answer")` goes on.

As a subgraph: `build_graph(model, work_dir=..., ...)` returns the compiled
graph, whose state has `messages`; `request_text(spec=...)` writes the user
message of a request. Give it a checkpointer for interactive questions. It
reads the skills from a read-only copy, but only `PluginAgent` checks after
a run that the skills were not changed.

```python
from langgraph.graph import END, START, MessagesState, StateGraph

from mmt_plugin_agent import build_graph, request_text

parent = StateGraph(MessagesState)
parent.add_node("plugin", build_graph("anthropic:claude-sonnet-5-5", work_dir="work"))
parent.add_edge(START, "plugin")
parent.add_edge("plugin", END)
app = parent.compile()
app.invoke({"messages": [{"role": "user", "content": request_text(spec="spec.md")}]})
```

## Model evals

`mmt-plugin-agent eval` has each `--model` draft every case of
`skills/mmt-plugin-generator/evals/cases/` (or those `--case` names),
unattended and without the capture evaluation, then judges it with the
checks of `evals/run_evals.py`: each envelope of the agent's loop (from
the command's output, else from the file it saved in the work folder's
`runs/` while it ran) against the skill's contract, each fix at what the failed run reported, no packet
test deleted or rewritten, the final loop, run again, green, and an
update's label, id, profile, parents and packet tests kept. Unlike the
scripted evals, the loop need not stop where the case's script does. It
writes a table per model and case to `--out` (Markdown) and the same with
`.json`; it exits 6 when a case fails. Without `--sdk` it uses `MMT_BASE`,
as a run does. A model that puts its work folder or project elsewhere
than the brief says fails the case with that one problem.

```sh
mmt-plugin-agent eval --model anthropic:claude-sonnet-5-5 --model ollama:qwen3-coder --sdk "$MMT_BASE" --out results.md
```

## The sandbox

The agent's shell has no isolation of its own: a command it runs can do
whatever the user running `mmt-plugin-agent` can. Its guards are defence
in depth:

- The file tools write only in the work folder, an update's project and
  the temporary directory, never in the skills (links followed). What
  deepagents takes out of the context (large tool results, summarized
  history) goes to `<work>/.agent/`.
- The shell refuses `sudo`, `--system`, any path under `/opt/mmt`, and
  `--force` unattended (interactive: only after a yes). A refused command
  is not run.
- The skills the model reads are a read-only copy (files 0444, directories
  0555, in `~/.cache/mmt-plugin-agent/`). At the end of every run the
  source skills directory is compared with its digest at the start; a
  change, by any route, is restored and the run fails with
  `agent.skills-modified`.
- The shell's environment is an allowlist (`PATH`, `HOME`, `MMT_*`,
  `UV_*`, `XDG_*`, proxies, `DOCKER_*`, ...) without secrets.

The container is the sandbox: run the agent in the `agent` image, where it
is not root and the skills are root-owned and read-only. The image has no
Docker socket. Mounting the host's (`-v /var/run/docker.sock:...`) lets
cyberlab record real captures, but gives the agent root on the host. Use
it only when you trust the model and the inputs, or give it a separate
Docker daemon (Docker-in-Docker). Without Docker, captures are synthetic,
and only with leave (`--allow-synthetic`).
