#!/usr/bin/env python3
"""lean-team metrics, learning status, and quiet Claude Code hooks (stdlib only)."""

import argparse
import datetime as dt
import io
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys


VERSION = "2.2.0"
MAX_TRANSCRIPT = 50 * 1024 * 1024
KINDS = ("build", "fix", "review", "research", "content", "media", "plan", "ops")
CAUSES = ("brief-ambiguous", "design-not-decided", "ownership-too-narrow",
          "brief-contradictory", "scope-grew-in-review", "executor-weak",
          "executor-blocked", "env-tooling", "flaky-test", "lead-error",
          "user-correction")
AUTO = ("remind", "keywords", "off")
KEYWORDS = ("lean-team", "lean team", "эконом", "токен", "дешёв", "дешев",
            "save tokens", "fewer tokens", "cheap", "token budget")
ID_PATTERN = r"(?:C-\d{4}-\d{2}-\d{2}-[a-z0-9]+|C\d+)"
ID_RE = re.compile(r"(?<![\w-])" + ID_PATTERN + r"(?![\w-])")
HEADING_RE = re.compile(
    r"^## (" + ID_PATTERN + r") · (mechanical|large|small) · "
    r"(candidate|trial|rule|proposed-to-core|retired) · "
    r"(core|personal|project:\S+|adapter:\S+|recipe:\S+)\s*$")
EVIDENCE_RE = re.compile(r"^- (\d{4}-\d{2}-\d{2}) (\S+) v([\d.]+): (.*)$")
FIELDS = ("calls", "input", "write_5m", "write_1h", "read", "output", "effective")


class ValidationError(Exception):
    def __init__(self, problems):
        self.problems = problems if isinstance(problems, list) else [problems]
        super().__init__("; ".join(self.problems))


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValidationError(message + "; use --help for valid arguments")


def read_text(path):
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return ""


def read_object(path):
    try:
        value = json.loads(read_text(path))
        return value if isinstance(value, dict) else {}
    except (ValueError, OSError):
        return {}


def json_lines(path):
    try:
        with path.open(encoding="utf-8", errors="replace") as stream:
            for line in stream:
                try:
                    value = json.loads(line)
                except ValueError:
                    continue
                if isinstance(value, dict):
                    yield value
    except FileNotFoundError:
        return


def data_dir():
    return Path(os.environ.get("LEAN_TEAM_HOME") or Path.home() / ".claude/lean-team")


def projects_dir():
    explicit = os.environ.get("LEAN_TEAM_PROJECTS_DIR")
    config = os.environ.get("CLAUDE_CONFIG_DIR")
    return Path(explicit) if explicit else Path(config or Path.home() / ".claude") / "projects"


def project_dir(args, hook=None):
    explicit = (getattr(args, "project_dir", None) or os.environ.get("CLAUDE_PROJECT_DIR")
                or (hook or {}).get("cwd"))
    if explicit:
        return Path(explicit).resolve()
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"], capture_output=True,
            encoding="utf-8", errors="replace", timeout=0.2 if hook is not None else 2)
        if result.returncode == 0 and result.stdout.strip():
            return Path(result.stdout.strip()).resolve()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return Path.cwd()


def session_id(args, hook=None):
    # Hook payloads identify the actual event, even if an inherited env is stale.
    return (getattr(args, "session", None) or (hook or {}).get("session_id")
            or os.environ.get("CLAUDE_CODE_SESSION_ID"))


def valid_session(session):
    return (isinstance(session, str) and bool(session) and session not in (".", "..")
            and re.fullmatch(r"[\w.-]+", session) is not None)


def config_value():
    value = read_object(data_dir() / "config.json").get("auto")
    return value if value in AUTO else "remind"


def write_object(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False) + "\n", encoding="utf-8")


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError("timestamp must be an ISO 8601 string")
    parsed = dt.datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def last_until(session):
    result = None
    for row in json_lines(data_dir() / "metrics.jsonl"):
        if row.get("v") == 1 and row.get("session") == session:
            result = row.get("until")
    return result


def find_transcript(session):
    root = projects_dir()
    choices = []
    if root.is_dir():
        for folder in root.iterdir():
            if folder.is_dir():
                path = folder / (session + ".jsonl")
                if path.is_file():
                    choices.append(path)
    if not choices:
        raise FileNotFoundError(
            "transcript for session {} not found under {}".format(session, root.as_posix()))
    return max(choices, key=lambda path: (path.stat().st_mtime_ns, path.as_posix()))


def empty_totals():
    return dict.fromkeys(FIELDS, 0)


def number(value):
    return value if isinstance(value, (int, float)) and math.isfinite(value) else 0


def effective(totals):
    return round(totals["input"] + 1.25 * totals["write_5m"] + 2 * totals["write_1h"]
                 + 0.1 * totals["read"] + 5 * totals["output"])


def measure(session, since=None):
    """Deduplicate calls across the main transcript and its subagent files."""
    main = find_transcript(session)
    lower = timestamp(since) if since else None
    groups = {}
    for name in ("lead", "subagents"):
        groups[name] = dict(empty_totals(), images=0, models={})
    calls = {}
    until, latest = since, lower
    paths = [(main, False)]
    paths.extend((path, True) for path in sorted(
        (main.parent / session / "subagents").glob("*.jsonl")))
    for path, subagent in paths:
        for row in json_lines(path):
            group = "subagents" if subagent or row.get("isSidechain") is True else "lead"
            try:
                when = timestamp(row.get("timestamp"))
            except (ValueError, TypeError, OverflowError):
                when = None
            inside = when is not None and (lower is None or when > lower)
            if inside and group == "lead" and (latest is None or when > latest):
                until, latest = row["timestamp"], when
            message = row.get("message")
            if not isinstance(message, dict):
                continue
            if row.get("type") == "assistant" and isinstance(message.get("usage"), dict):
                ident = message.get("id")
                key = ("id", str(ident)) if ident else ("line", len(calls))
                # Retain last copies even outside the window, and synthetic copies.
                calls[key] = (group, message, inside)
            if inside and row.get("type") == "user":
                content = message.get("content", [])
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "tool_result":
                            items = block.get("content")
                            if isinstance(items, list):
                                groups[group]["images"] += sum(
                                    isinstance(item, dict) and item.get("type") == "image"
                                    for item in items)
    for group, message, inside in calls.values():
        if not inside or message.get("model") == "<synthetic>":
            continue
        model = message.get("model") or "unknown"
        if not isinstance(model, str):
            model = "unknown"
        totals = groups[group]["models"].setdefault(model, empty_totals())
        usage = message["usage"]
        creation = usage.get("cache_creation")
        totals["calls"] += 1
        for field, key in (("input", "input_tokens"), ("read", "cache_read_input_tokens"),
                           ("output", "output_tokens")):
            totals[field] += number(usage.get(key))
        if isinstance(creation, dict):
            totals["write_5m"] += number(creation.get("ephemeral_5m_input_tokens"))
            totals["write_1h"] += number(creation.get("ephemeral_1h_input_tokens"))
        else:
            totals["write_5m"] += number(usage.get("cache_creation_input_tokens"))
    for group in groups.values():
        for model in group["models"].values():
            model["effective"] = effective(model)
            for field in FIELDS[:-1]:
                group[field] += model[field]
        group["effective"] = effective(group)
    groups["external"] = {}
    return groups, until


def compact(value):
    if abs(value) >= 1000000:
        return "{:.2f}M".format(value / 1000000)
    if abs(value) >= 1000:
        return "{:.1f}k".format(value / 1000)
    return str(value)


def token_line(label, totals):
    return ("{} calls={} in={} write={} read={} out={} effective={}".format(
        label, totals["calls"], compact(totals["input"]),
        compact(totals["write_5m"] + totals["write_1h"]), compact(totals["read"]),
        compact(totals["output"]), compact(totals["effective"])))


def tokens_command(args):
    session = session_id(args)
    if not valid_session(session):
        raise ValidationError("missing or invalid session; pass --session ID or set CLAUDE_CODE_SESSION_ID")
    since = last_until(session) if args.since_last_log else args.since
    if since:
        try:
            timestamp(since)
        except (ValueError, TypeError, OverflowError):
            raise ValidationError("invalid --since timestamp; use ISO 8601, e.g. 2026-10-25T00:00:00Z")
    tokens, until = measure(session, since)
    if args.json:
        print(json.dumps(dict(tokens, until=until), ensure_ascii=False))
        return
    print("Session {} window {} -> {}".format(session[:8], since or "beginning", until or "empty"))
    lines = [token_line(group + " " + model, totals)
             for group in ("lead", "subagents")
             for model, totals in sorted(tokens[group]["models"].items())]
    # Preserve every model while bounding output even for unusually many models.
    for line in lines[:6]:
        print(line)
    if len(lines) > 6:
        print(" | ".join(lines[6:]))
    total = {key: tokens["lead"][key] + tokens["subagents"][key] for key in FIELDS}
    total["effective"] = effective(total)
    print(token_line("total", total))
    print("images lead={} subagents={}".format(tokens["lead"]["images"], tokens["subagents"]["images"]))


def metric_count():
    path = data_dir() / "metrics.jsonl"
    try:
        with path.open(encoding="utf-8", errors="replace") as stream:
            return sum(bool(line.strip()) for line in stream)
    except FileNotFoundError:
        return 0


def iterations():
    count = metric_count()
    offset = read_object(data_dir() / "state.json").get("consolidated_at_line", 0)
    if not isinstance(offset, int) or offset < 0:
        offset = 0
    return max(0, count - offset)


def candidate_data():
    candidates, unformatted, current = [], 0, None
    for line in read_text(data_dir() / "candidates.md").splitlines():
        if re.match(r"^#{1,6}\s", line):
            current = None
        match = HEADING_RE.fullmatch(line)
        if match:
            ident, kind, status, scope = match.groups()
            current = dict(id=ident, type=kind, status=status, scope=scope,
                           action="", yes=0, total=0, worse=False, applied=0)
            candidates.append(current)
        elif line.startswith("## C"):
            unformatted += 1
        elif current is not None:
            if line.startswith("Action:") and not current.get("_action_seen"):
                current["action"] = line[len("Action:"):].strip()
                current["_action_seen"] = True
            evidence = EVIDENCE_RE.fullmatch(line)
            if evidence:
                effect = re.search(r"\beffect=(yes|no)\b", evidence[4])
                if effect:
                    current["total"] += 1
                    current["yes"] += effect[1] == "yes"
                    current["worse"] |= bool(re.search(r"\bquality=worse\b", evidence[4]))
    applied = {}
    for row in json_lines(data_dir() / "metrics.jsonl"):
        rules = row.get("rules_applied")
        if row.get("v") == 1 and isinstance(rules, list):
            for ident in set(item for item in rules if isinstance(item, str)):
                applied[ident] = applied.get(ident, 0) + 1
    for candidate in candidates:
        candidate.pop("_action_seen", None)
        candidate["applied"] = applied.get(candidate["id"], 0)
        active = candidate["status"] in ("candidate", "trial")
        yes, total = candidate["yes"], candidate["total"]
        threshold = (yes >= 1 if candidate["type"] == "mechanical" else
                     yes >= 2 if candidate["type"] == "large" else total >= 3 and yes >= 2)
        candidate["ready"] = active and not candidate["worse"] and threshold
        candidate["retire"] = active and total >= 5 and yes == 0
        candidate["check"] = active and candidate["worse"]
    return candidates, unformatted


def line_count(path):
    return len(read_text(path).splitlines())


def status_data(args, hook=None):
    directory = project_dir(args, hook)
    project = getattr(args, "project", None) or directory.name
    candidates, unformatted = candidate_data()
    count = iterations()
    open_candidates = [candidate for candidate in candidates
                       if candidate["status"] in ("candidate", "trial")
                       and candidate["scope"] in ("core", "personal", "project:" + project)]
    caps = {}
    for name, path, cap in (("personal", data_dir() / "local.md", 60),
                            ("project", directory / ".claude/lean-team.md", 40)):
        lines = line_count(path)
        caps[name] = dict(lines=lines, cap=cap, over=lines > cap)
    return dict(project=project, iterations_since_consolidation=count, due=count >= 5,
                strict=len(candidates), unformatted=unformatted, open=len(open_candidates),
                candidates=candidates, ready=[c["id"] for c in candidates if c["ready"]],
                retire=[c["id"] for c in candidates if c["retire"]],
                check=[c["id"] for c in candidates if c["check"]], caps=caps)


def status_lines(status):
    lines = ["lean-team {} — {}".format(VERSION, status["project"]),
             "{} iterations since consolidation{}".format(
                 status["iterations_since_consolidation"], " — consolidate now" if status["due"] else ""),
             "candidates: strict={} unformatted={} open={}".format(
                 status["strict"], status["unformatted"], status["open"])]
    for category in ("ready", "retire", "check"):
        matches = [c for c in status["candidates"] if c[category]]
        items = ["{} ({}, {}/{})".format(c["id"], c["type"], c["yes"], c["total"])
                 for c in matches[:5]]
        if len(matches) > 5:
            items.append("+{}".format(len(matches) - 5))
        lines.append(category + ": " + (", ".join(items) or "none"))
    lines.append("caps: " + "; ".join("{} {}/{}{}".format(
        name, cap["lines"], cap["cap"], " OVER" if cap["over"] else "")
        for name, cap in status["caps"].items()))
    return lines


def status_command(args):
    status = status_data(args)
    if args.json:
        print(json.dumps(status, ensure_ascii=False))
    elif args.open:
        candidates = [c for c in status["candidates"]
                      if c["status"] in ("candidate", "trial")
                      and c["scope"] in ("core", "personal", "project:" + status["project"])]
        for c in candidates[:20]:
            print("{} · {} · {} · {}/{} · {}".format(
                c["id"], c["type"], c["status"], c["yes"], c["total"], c["action"][:90]))
    else:
        print("\n".join(status_lines(status)))


def comma_list(value):
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def parse_pairs(value, external, problems):
    result = {}
    option = "--external" if external else "--limits"
    for item in comma_list(value):
        try:
            key, raw = item.rsplit("=", 1)
            key, raw = key.strip(), raw.strip()
            if external:
                if not re.fullmatch(r"[^\s:=,]+:[^\s=,]+", key):
                    raise ValueError()
                parsed = int(raw)
                if parsed < 0:
                    raise ValueError()
            else:
                if key not in ("week", "5h"):
                    raise ValueError()
                parsed = float(raw)
                if not math.isfinite(parsed):
                    raise ValueError()
                if parsed.is_integer():
                    parsed = int(parsed)
            result[key] = parsed
        except (ValueError, OverflowError):
            example = "executor:model=216000 (nonnegative integer)" if external else "week=+3,5h=+12 (finite percentage points)"
            problems.append("invalid {} item {!r}; use {}".format(option, item, example))
    return result


def validate_log(args):
    problems = []
    for name in ("task", "kind", "success"):
        if not getattr(args, name):
            problems.append("missing --{}; supply --{} VALUE".format(name, name))
    for name, choices in (("kind", KINDS), ("success", ("yes", "partial", "no"))):
        value = getattr(args, name)
        if value and value not in choices:
            problems.append("invalid --{}; choose {}".format(name, "|".join(choices)))
    for name, cap in (("task", 80), ("note", 160)):
        if len(getattr(args, name) or "") > cap:
            problems.append("--{} is too long; shorten to {} characters".format(name, cap))
    for name in ("review_rounds", "user_corrections"):
        try:
            value = int(getattr(args, name))
            if value < 0:
                raise ValueError()
            setattr(args, name, value)
        except (ValueError, TypeError):
            problems.append("invalid --{}; use an integer >= 0".format(name.replace("_", "-")))
    session = session_id(args)
    if not valid_session(session):
        problems.append("missing or invalid session; pass --session ID or set CLAUDE_CODE_SESSION_ID")
    candidate_ids = set()
    for line in read_text(data_dir() / "candidates.md").splitlines():
        match = re.match(r"^##\s+(\S+)", line)
        if match and re.fullmatch(ID_PATTERN, match[1].rstrip(":")):
            candidate_ids.add(match[1].rstrip(":"))
    directory = project_dir(args)
    known = candidate_ids | set(ID_RE.findall(read_text(data_dir() / "local.md")))
    known.update(ID_RE.findall(read_text(directory / ".claude/lean-team.md")))
    rules, new, causes = map(comma_list, (args.rules, args.new, args.causes))
    for ident in rules:
        if ident not in known:
            problems.append("unknown rule {}; add its id to candidates.md, local.md or the project layer".format(ident))
    for ident in new:
        if ident not in candidate_ids:
            problems.append("unknown new candidate {}; write its heading in candidates.md first".format(ident))
    for cause in causes:
        if cause not in CAUSES:
            problems.append("unknown cause {}; choose {}".format(cause, ", ".join(CAUSES)))
    external = parse_pairs(args.external, True, problems)
    limits = parse_pairs(args.limits, False, problems)
    if problems:
        raise ValidationError(problems)
    return session, directory, rules, new, causes, external, limits


def log_command(args):
    session, directory, rules, new, causes, external, limits = validate_log(args)
    since = last_until(session)
    try:
        tokens, until = measure(session, since)
        tokens["external"] = external
    except FileNotFoundError as error:
        tokens, until = None, since
        print("warning: {}; pass --session ID or set LEAN_TEAM_PROJECTS_DIR".format(error), file=sys.stderr)
    row = dict(v=1, date=dt.date.today().isoformat(), until=until, session=session,
               project=args.project or directory.name, skill_version=VERSION,
               task=args.task, kind=args.kind, success=args.success,
               review_rounds=args.review_rounds, causes=causes,
               user_corrections=args.user_corrections, rules_applied=rules,
               candidates_new=new, tokens=tokens, limits=limits, note=args.note)
    encoded = json.dumps(row, ensure_ascii=False)
    if args.dry_run:
        print(encoded)
        return
    path = data_dir() / "metrics.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    # A pre-existing legacy final line need not end with a newline.
    with path.open("a+b") as stream:
        stream.seek(0, 2)
        if stream.tell():
            stream.seek(-1, 2)
            if stream.read(1) != b"\n":
                stream.write(b"\n")
        stream.write((encoded + "\n").encode("utf-8"))
    print("Logged {}: {} ({}, {})".format(session[:8], args.task.replace("\n", " ").replace("\r", " "),
                                           args.kind, args.success))
    print("\n".join(status_lines(status_data(args))))


def hook_input():
    try:
        # Claude Code sends UTF-8; on Windows the console default would be the ANSI code page.
        raw = sys.stdin.buffer.read() if hasattr(sys.stdin, "buffer") else sys.stdin.read()
        value = json.loads(raw.decode("utf-8", "replace") if isinstance(raw, bytes) else raw)
        return (value, True) if isinstance(value, dict) else ({}, False)
    except (ValueError, OSError):
        return {}, False


def marker(session, suffix):
    if not valid_session(session):
        return None
    return data_dir() / "sessions" / (session + suffix)


def touch(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()


def one_line(value, cap=220):
    value = " ".join(str(value).split())
    return value if len(value) <= cap else value[:cap - 1] + "…"


def used_skill(path):
    # Most transcript lines have neither substring; avoid decoding those lines.
    if path.stat().st_size > MAX_TRANSCRIPT:
        return False
    with path.open(encoding="utf-8", errors="replace") as stream:
        for line in stream:
            if "lean-team" not in line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if not isinstance(row, dict):
                continue
            message = row.get("message", {})
            if not isinstance(message, dict):
                continue
            content = message.get("content", [])
            if row.get("type") == "user":
                texts = [content] if isinstance(content, str) else [
                    part.get("text", "") for part in content if isinstance(part, dict)
                ] if isinstance(content, list) else []
                if any(isinstance(text, str) and "<command-name>/lean-team" in text for text in texts):
                    return True
            if row.get("type") == "assistant" and isinstance(content, list):
                for block in content:
                    if not isinstance(block, dict) or block.get("type") != "tool_use" or block.get("name") != "Skill":
                        continue
                    inputs = block.get("input")
                    if isinstance(inputs, dict) and "lean-team" in str(inputs.get("skill", "")):
                        return True
    return False


def start_command(args):
    hook, valid = hook_input()
    if config_value() != "remind":
        return
    launcher = Path(__file__).resolve().with_name("lt.sh").as_posix()
    header = ('lean-team {} is installed. For multi-step work (builds, research, refactors, '
              'anything you would delegate) load the lean-team skill first; do small fixes yourself.').format(VERSION)
    # The path stays on its own line so a long install path is never cut.
    lines = [one_line(header), 'Tool: bash "{}" status | tokens | log'.format(launcher)]
    if not valid:
        print("\n".join(lines))
        return
    directory = project_dir(args, hook)
    layer = directory / ".claude/lean-team.md"
    if layer.is_file():
        lines.append(one_line("Project layer: {} ({} lines) — read it after loading the skill.".format(
            layer.as_posix(), line_count(layer))))
    count = iterations()
    if count >= 5:
        lines.append("Learning: {} iterations since the last consolidation — consolidate first (lt.sh status).".format(count))
    transcript = hook.get("transcript_path")
    if isinstance(transcript, str) and transcript:
        current = Path(transcript)
        choices = []
        for path in current.parent.glob("*.jsonl"):
            if path != current and path.stem != session_id(args, hook):
                stat = path.stat()
                if stat.st_size <= MAX_TRANSCRIPT:
                    choices.append((stat.st_mtime_ns, path.as_posix(), path))
        if choices:
            previous = max(choices)[2]
            nudged = marker(previous.stem, ".nudged")
            logged = any(row.get("session") == previous.stem for row in json_lines(data_dir() / "metrics.jsonl"))
            if nudged is not None and not nudged.exists() and not logged and used_skill(previous):
                lines.append(one_line('Last session {} used lean-team but logged no metrics: bash "{}" log --session {} ... (or ignore).'.format(
                    previous.stem[:8], launcher, previous.stem)))
                touch(nudged)
    print("\n".join(lines[:5]))


def prompt_command(args):
    hook, valid = hook_input()
    if not valid or config_value() == "off":
        return
    prompt = hook.get("prompt")
    hinted = marker(session_id(args, hook), ".hinted")
    if not isinstance(prompt, str) or hinted is None:
        return
    folded = prompt.casefold()
    if "/lean-team" in folded or hinted.exists():
        return
    if any(keyword in folded for keyword in KEYWORDS):
        touch(hinted)
        print("lean-team: the user wants to save tokens — load the lean-team skill before planning, if it is not loaded yet.")


def parser():
    root = Parser(description=__doc__)
    root.add_argument("--debug", action="store_true")
    commands = root.add_subparsers(dest="command", required=True)
    for name in ("start", "prompt", "tokens", "log", "status", "consolidated", "config"):
        command = commands.add_parser(name)
        command.add_argument("--debug", action="store_true", default=argparse.SUPPRESS)
        if name in ("start", "prompt", "tokens", "log"):
            command.add_argument("--session")
        if name in ("start", "prompt", "log", "status"):
            command.add_argument("--project-dir")
            command.add_argument("--project")
        if name in ("tokens", "status"):
            command.add_argument("--json", action="store_true")
        if name == "tokens":
            window = command.add_mutually_exclusive_group()
            window.add_argument("--since")
            window.add_argument("--since-last-log", action="store_true")
        elif name == "log":
            for option in ("task", "kind", "success", "rules", "new", "causes", "external", "limits"):
                command.add_argument("--" + option)
            command.add_argument("--review-rounds", default="0")
            command.add_argument("--user-corrections", default="0")
            command.add_argument("--note", default="")
            command.add_argument("--dry-run", action="store_true")
        elif name == "status":
            command.add_argument("--open", action="store_true")
        elif name == "config":
            command.add_argument("--auto")
    return root


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = None
    try:
        args = parser().parse_args(argv)
        if args.command in ("start", "prompt"):
            # Buffer output so exceptions cannot leave partial hook instructions.
            output = io.StringIO()
            original = sys.stdout
            try:
                sys.stdout = output
                (start_command if args.command == "start" else prompt_command)(args)
            except Exception:
                return 0
            finally:
                sys.stdout = original
            print(output.getvalue(), end="")
        elif args.command == "tokens":
            tokens_command(args)
        elif args.command == "log":
            log_command(args)
        elif args.command == "status":
            status_command(args)
        elif args.command == "consolidated":
            count = metric_count()
            write_object(data_dir() / "state.json", dict(
                consolidated_at_line=count, date=dt.date.today().isoformat()))
            print("Consolidated through metrics line {}.".format(count))
        elif args.command == "config":
            if args.auto is not None:
                if args.auto not in AUTO:
                    raise ValidationError("invalid --auto; choose remind|keywords|off")
                config = read_object(data_dir() / "config.json")
                config["auto"] = args.auto
                write_object(data_dir() / "config.json", config)
            print(config_value())
        return 0
    except Exception as error:
        if args is not None and args.debug:
            raise
        problems = error.problems if isinstance(error, ValidationError) else [str(error)]
        for problem in problems:
            message = str(problem)
            if not isinstance(error, ValidationError):
                message += "; check the session, paths and file permissions, then retry"
            print(one_line(message, 2000), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
