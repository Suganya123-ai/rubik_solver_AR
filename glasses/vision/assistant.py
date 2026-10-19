"""The tutor's assistant: answers spoken questions ("why this move?", "what did I do wrong?", "how many
moves are left?") and writes a short report when the cube is solved, with a large language model.

The vision and the solver decide every move; the model never does. It is given the tutor's real state
(the stage, the move asked for, the moves done, the mistakes, the rest of the plan) and told to answer
only from that, in a sentence or two, and to say so when the facts don't answer the question rather than
guess. Only text is sent: never a camera picture.

Which model (ASSISTANT=azure|ollama|off; by default Azure when it is set up, else a local Ollama model
when one is running, else off):
  - Azure OpenAI: AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_DEPLOYMENT,
    AZURE_OPENAI_API_VERSION, from the environment or ~/.cube_tutor_llm.env (never in git);
  - Ollama (free, offline, on this laptop): OLLAMA_MODEL (default qwen3:8b) at OLLAMA_URL.
"""
import json
import logging
import os
import re
import time
import urllib.error
import urllib.request

log = logging.getLogger('rubik.assistant')
# the laptop: ~/.cube_tutor_llm.env; the glasses app: its private files/llm.env (CUBE_TUTOR_LLM_ENV)
SETTINGS_FILE = os.environ.get('CUBE_TUTOR_LLM_ENV') or os.path.expanduser('~/.cube_tutor_llm.env')
TIMEOUT_S = 20
MAX_TURNS = 4            # earlier questions and answers kept, for follow-ups ("and after that?")

SYSTEM = """You are the voice of a Rubik's cube tutor. The person is holding a real cube in front of a camera \
(a webcam, or AR glasses they are wearing) and the tutor guides them move by move. Your answers are spoken aloud.

Rules:
- Answer in one or two short spoken sentences (at most about 30 words). No lists, no markdown, no emoji.
- Use ONLY the facts given below. Never invent moves, positions, reasons, numbers or tips that are not in them. \
If the facts don't answer the question, say briefly that you can't tell from here and suggest what to do \
(for example: say repeat to hear the step again).
- You never decide or change moves: the solver does. Never contradict the current instruction.
- DIRECTIONS: never say which way to turn a side, or which way an edge moves, unless those exact words are \
in the tutor's current instruction (quote them). For any other move name only the side ("then the blue side"), \
and for the direction tell them to follow the arrow when it comes.
- POSITIONS: say where a side is (on top, on your left...) only as the fact "Where each side is for the person" \
says; never work it out yourself (the camera may face the person: its right is their left).
- Name sides by their colour, as the tutor does ("the green side"). Use move letters (R, U') only if asked.
- About the method: the plan is a near-shortest solution found by a computer (a two-phase search). Its moves do \
not finish recognisable human stages one at a time; each move sets up the following ones. Say that honestly \
when asked why a move is needed.
- If asked about something unrelated to the cube, answer very briefly and steer back to the cube.

How the tutor works (true in every session):
- Scan: the person says scan (or presses S), then holds the cube corner-on so the camera sees three sides at once \
(top, front and right) and holds still until it beeps; then turns the cube to show the other sides, from any \
angle, until all six are in. The camera reads the colours itself.
- Colour check: the six sides are shown on screen; unclear stickers are highlighted and can be tapped to fix. \
Then the person says solve.
- Solving: the tutor gives one move at a time (which side, and which way, with an arrow on the real cube and a \
small 3D cube showing it), then the person holds the cube still so the camera can check it. Right: the next \
move. Wrong: it says how to undo it, then the same plan carries on; after several mistakes it makes a new plan.
- Voice: it says every step; the person can say next (the move is done but the camera missed it), repeat, \
scan, solve, new plan, stop, quiet, speak, help, or ask a question like this one.
- Holding: three sides should face the camera, and fingers should stay off the stickers when holding still."""

REPORT = """Write a short report of this solving session for the person who just solved the cube: two or three \
spoken sentences (at most about 60 words), warm and specific, from the facts only (time, moves, mistakes, help \
used). Mention one thing that went well and, only if the facts show one, one thing to practise. Name sides by \
colour, never move letters. No lists, no markdown."""


def _settings():
    """AZURE_OPENAI_* from the environment, else from ~/.cube_tutor_llm.env."""
    cfg = {k: v for k, v in os.environ.items() if k.startswith(('AZURE_OPENAI_', 'OLLAMA_', 'ASSISTANT'))}
    if os.path.exists(SETTINGS_FILE):
        for line in open(SETTINGS_FILE):
            m = re.match(r'\s*([A-Z_]+)\s*=\s*"?([^"\n]*)"?', line)
            if m and m.group(1) not in cfg:
                cfg[m.group(1)] = m.group(2).strip()
    return cfg


class Azure:
    name = 'azure'

    def __init__(self, cfg):
        self.url = (f"{cfg['AZURE_OPENAI_ENDPOINT'].rstrip('/')}/openai/deployments/{cfg['AZURE_OPENAI_DEPLOYMENT']}"
                    f"/chat/completions?api-version={cfg.get('AZURE_OPENAI_API_VERSION', '2024-12-01-preview')}")
        self.key = cfg['AZURE_OPENAI_API_KEY']
        self.model = cfg['AZURE_OPENAI_DEPLOYMENT']

    def chat(self, messages, max_tokens=160):
        body = json.dumps({'messages': messages, 'max_completion_tokens': max_tokens}).encode()
        req = urllib.request.Request(self.url, body, {'Content-Type': 'application/json', 'api-key': self.key})
        r = json.load(urllib.request.urlopen(req, timeout=TIMEOUT_S))
        self.model = r.get('model', self.model)
        return r['choices'][0]['message']['content'].strip()


class Ollama:
    name = 'ollama'

    def __init__(self, cfg):
        self.url = cfg.get('OLLAMA_URL', 'http://127.0.0.1:11434').rstrip('/')
        self.model = cfg.get('OLLAMA_MODEL', 'qwen3:8b')

    def available(self):
        try:
            urllib.request.urlopen(self.url + '/api/tags', timeout=1)
            return True
        except Exception:
            return False

    def chat(self, messages, max_tokens=160):
        body = json.dumps({'model': self.model, 'messages': messages, 'stream': False, 'think': False,
                           'options': {'num_predict': max_tokens}}).encode()
        req = urllib.request.Request(self.url + '/api/chat', body, {'Content-Type': 'application/json'})
        r = json.load(urllib.request.urlopen(req, timeout=TIMEOUT_S * 3))
        return re.sub(r'<think>.*?</think>', '', r['message']['content'], flags=re.S).strip()


def provider():
    """The model to use, or None (the assistant is off)."""
    cfg = _settings()
    choice = cfg.get('ASSISTANT', '').lower()
    if choice == 'off':
        return None
    if choice in ('', 'azure') and all(cfg.get(k) for k in ('AZURE_OPENAI_API_KEY', 'AZURE_OPENAI_ENDPOINT', 'AZURE_OPENAI_DEPLOYMENT')):
        return Azure(cfg)
    if choice in ('', 'ollama'):
        o = Ollama(cfg)
        if choice == 'ollama' or o.available():
            return o
    return None


def question_messages(question, facts, turns=()):
    """The chat for a question: the rules and the facts, the last few questions and answers, the question."""
    messages = [{'role': 'system', 'content': SYSTEM + '\n\nFacts right now:\n' + facts}]
    for q, a in list(turns)[-MAX_TURNS:]:
        messages += [{'role': 'user', 'content': q}, {'role': 'assistant', 'content': a}]
    messages.append({'role': 'user', 'content': question})
    return messages


def report_messages(facts):
    return [{'role': 'system', 'content': REPORT}, {'role': 'user', 'content': facts}]


class Assistant:
    """One per connected page: keeps the last few questions and answers for follow-ups."""

    def __init__(self):
        self.model = provider()
        self.turns = []
        if self.model:
            log.info('assistant: %s (%s)', self.model.name, self.model.model)

    @property
    def on(self):
        return self.model is not None

    def ask(self, question, facts):
        if not self.model:
            return "Questions need the assistant, and it isn't set up on this computer."
        messages = question_messages(question, facts, self.turns)
        t0 = time.monotonic()
        try:
            answer = self.model.chat(messages, 120)
        except (urllib.error.URLError, TimeoutError, OSError, KeyError, ValueError) as e:
            log.warning('assistant: no answer (%s)', e)
            return "Sorry, I can't answer questions right now. Say repeat to hear the step again."
        log.info('assistant: %.1f s: %r -> %r', time.monotonic() - t0, question, answer)
        self.turns.append((question, answer))
        return answer

    def report(self, facts):
        if not self.model:
            return None
        try:
            return self.model.chat(report_messages(facts), 200)
        except (urllib.error.URLError, TimeoutError, OSError, KeyError, ValueError) as e:
            log.warning('assistant: no report (%s)', e)
            return None
