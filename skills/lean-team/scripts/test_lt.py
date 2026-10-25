#!/usr/bin/env python3
"""Isolated contract tests: python -I skills/lean-team/scripts/test_lt.py."""

import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock


# -I omits the script directory. Do not create __pycache__ beside the two files.
sys.dont_write_bytecode = True
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import lt


METRIC_KEYS = ["v", "date", "until", "session", "project", "skill_version", "task",
               "kind", "success", "review_rounds", "causes", "user_corrections",
               "rules_applied", "candidates_new", "tokens", "limits", "note"]


def stamp(second):
    return "2026-10-25T12:00:{:02d}.000Z".format(second)


def call(ident="a", second=1, model="opus", side=False, **usage):
    return dict(type="assistant", timestamp=stamp(second), isSidechain=side,
                message=dict(id=ident, model=model, usage=usage))


def images(second=2, count=1, side=False):
    return dict(type="user", timestamp=stamp(second), isSidechain=side,
                message=dict(content=[dict(type="tool_result", content=[
                    dict(type="image", source={}) for _ in range(count)] + [dict(type="text", text="ok")])]))


def candidate(ident, kind="mechanical", effects=(), status="candidate", scope="project:COS",
              action="run verification", quality="same"):
    lines = ["## {} · {} · {} · {}".format(ident, kind, status, scope), "Action: " + action,
             "Metric: calls before 80 -> 60"]
    lines.extend("- 2026-10-25 COS/short8 v2.2.0: effect={}, quality={}".format(effect, quality)
                 for effect in effects)
    return "\n".join(lines) + "\n"


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="lt-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = self.root / "data"
        self.projects = self.root / "transcripts"
        self.project = self.root / "COS"
        self.project.mkdir()
        self.folder = self.projects / "encoded-project"
        self.folder.mkdir(parents=True)
        self.session = "current-session-123"
        self.transcript = self.folder / (self.session + ".jsonl")
        self.env = mock.patch.dict(os.environ, {
            "LEAN_TEAM_HOME": str(self.data),
            "LEAN_TEAM_PROJECTS_DIR": str(self.projects),
            "CLAUDE_PROJECT_DIR": str(self.project),
            "CLAUDE_CODE_SESSION_ID": self.session,
            "CLAUDE_CONFIG_DIR": str(self.root / "unused-config"),
        })
        self.env.start()
        self.addCleanup(self.env.stop)
        # A regression that resolves the real default home must fail, not touch it.
        patch = mock.patch.object(Path, "home", return_value=self.root / "fake-home")
        patch.start()
        self.addCleanup(patch.stop)

    def write(self, path, text):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def rows(self, rows, path=None):
        self.write(path or self.transcript, "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n")

    def cli(self, *args, **kwargs):
        stdin = kwargs.get("stdin", "")
        if not isinstance(stdin, str):
            stdin = json.dumps(stdin, ensure_ascii=False)
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr), mock.patch.object(sys, "stdin", io.StringIO(stdin)):
            code = lt.main(list(args))
        return code, stdout.getvalue(), stderr.getvalue()

    def ok(self, *args, **kwargs):
        code, out, err = self.cli(*args, **kwargs)
        self.assertEqual(code, 0, err)
        return out

    def tokens(self, *args):
        return json.loads(self.ok("tokens", "--json", *args))

    def status(self, *args):
        return json.loads(self.ok("status", "--json", *args))

    def log_args(self, *extra):
        return ("log", "--task", "fixture task", "--kind", "build", "--success", "yes") + extra

    def hook(self, **overrides):
        value = dict(session_id=self.session, transcript_path=str(self.transcript), cwd=str(self.project))
        value.update(overrides)
        return value

    def metrics(self):
        return list(lt.json_lines(self.data / "metrics.jsonl"))

    def test_tokens_deduplicate_keep_last_split_fallback_and_formula(self):
        self.rows([call(input_tokens=999), call(input_tokens=3, output_tokens=2,
                    cache_read_input_tokens=10, cache_creation_input_tokens=999,
                    cache_creation=dict(ephemeral_5m_input_tokens=4, ephemeral_1h_input_tokens=8)),
                   call("b", 2, input_tokens=1, output_tokens=1,
                        cache_read_input_tokens=20, cache_creation_input_tokens=8)])
        lead = self.tokens()["lead"]
        expected = dict(calls=2, input=4, write_5m=12, write_1h=8, read=30, output=3, effective=53)
        for key, value in expected.items():
            self.assertEqual(lead[key], value, key)
        self.assertEqual(lead["models"]["opus"], expected)

    def test_tokens_round_only_after_summing(self):
        self.rows([call(str(n), n, cache_creation_input_tokens=1) for n in range(1, 4)])
        self.assertEqual(self.tokens()["lead"]["effective"], 4)

    def test_tokens_missing_numbers_synthetic_and_malformed_lines(self):
        self.rows([call(), call("synthetic", 2, model="<synthetic>", input_tokens=100000),
                   dict(type="assistant", timestamp=stamp(2), message={})])
        with self.transcript.open("a", encoding="utf-8") as stream:
            stream.write("bad json\n[]\nnull\n")
        lead = self.tokens()["lead"]
        self.assertEqual(lead["calls"], 1)
        self.assertEqual(lead["effective"], 0)
        self.assertNotIn("<synthetic>", lead["models"])

    def test_tokens_sidechains_files_models_and_images(self):
        self.rows([call(input_tokens=3), call("side", 2, side=True, model="sonnet", input_tokens=7),
                   images(count=2), images(count=3, side=True)])
        agent = self.folder / self.session / "subagents" / "agent-a.jsonl"
        self.rows([call("agent", 5, model="haiku", input_tokens=11), images(6, 4)], agent)
        tokens = self.tokens()
        self.assertEqual(tokens["lead"]["input"], 3)
        self.assertEqual(tokens["lead"]["images"], 2)
        self.assertEqual(tokens["subagents"]["input"], 18)
        self.assertEqual(tokens["subagents"]["calls"], 2)
        self.assertEqual(tokens["subagents"]["images"], 7)
        self.assertEqual(set(tokens["subagents"]["models"]), {"sonnet", "haiku"})
        self.assertEqual(tokens["until"], stamp(2))

    def test_tokens_duplicate_across_subagent_file(self):
        self.rows([call("agent", side=True, input_tokens=4)])
        self.rows([call("agent", 2, input_tokens=9)], self.folder / self.session / "subagents/a.jsonl")
        totals = self.tokens()["subagents"]
        self.assertEqual((totals["calls"], totals["input"]), (1, 9))

    def test_tokens_since_strict_timestamp_window_and_until(self):
        no_timestamp = call("undated", input_tokens=999)
        del no_timestamp["timestamp"]
        invalid = call("invalid", input_tokens=999)
        invalid["timestamp"] = "yesterday"
        self.rows([call("old", 1, input_tokens=5), call("new", 2, input_tokens=7), no_timestamp, invalid])
        result = self.tokens("--since", stamp(1))
        self.assertEqual(result["lead"]["input"], 7)
        self.assertEqual(result["until"], stamp(2))
        result = self.tokens("--since", stamp(2))
        self.assertEqual(result["lead"]["calls"], 0)
        self.assertEqual(result["until"], stamp(2))

    def test_tokens_empty_window_without_since(self):
        self.rows([])
        result = self.tokens()
        self.assertIsNone(result["until"])
        self.assertEqual(result["external"], {})

    def test_tokens_since_last_log_and_repeat_log(self):
        self.rows([call(input_tokens=3)])
        self.ok(*self.log_args())
        self.assertEqual(self.tokens("--since-last-log")["lead"]["calls"], 0)
        with self.transcript.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(call("next", 3, input_tokens=8)) + "\n")
        self.assertEqual(self.tokens("--since-last-log")["lead"]["input"], 8)
        self.ok(*self.log_args())
        row = self.metrics()[-1]
        self.assertEqual(row["tokens"]["lead"]["input"], 8)
        self.assertEqual(row["until"], stamp(3))
        self.assertEqual(self.tokens("--since-last-log")["lead"]["calls"], 0)

    def test_tokens_since_last_log_ignores_other_and_legacy_rows(self):
        self.rows([call(input_tokens=3)])
        self.rows([dict(v=1, session="other", until=stamp(10)),
                   dict(session=self.session, until=stamp(10))], self.data / "metrics.jsonl")
        self.assertEqual(self.tokens("--since-last-log")["lead"]["calls"], 1)

    def test_tokens_newest_transcript_and_explicit_session(self):
        self.rows([call(input_tokens=1)])
        other = self.projects / "another" / (self.session + ".jsonl")
        self.rows([call(input_tokens=22)], other)
        os.utime(self.transcript, (10, 10))
        os.utime(other, (20, 20))
        self.assertEqual(self.tokens()["lead"]["input"], 22)
        alternate = "alternate-session"
        self.rows([call(input_tokens=33)], self.folder / (alternate + ".jsonl"))
        self.assertEqual(self.tokens("--session", alternate)["lead"]["input"], 33)

    def test_tokens_text_limits_format_and_many_models(self):
        self.rows([call(str(n), n, model="model-" + str(n), input_tokens=1234567,
                        output_tokens=45600) for n in range(12)])
        output = self.ok("tokens")
        self.assertLessEqual(len(output.splitlines()), 10)
        self.assertIn("1.23M", output)
        self.assertIn("45.6k", output)
        for n in range(12):
            self.assertIn("lead model-{} calls=1".format(n), output)
        self.assertIn("total calls=12", output)
        self.assertIn("images lead=0 subagents=0", output)

    def test_tokens_errors_no_traceback_or_writes(self):
        code, out, err = self.cli("tokens")
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertIn("transcript for session " + self.session + " not found under " + self.projects.as_posix(), err)
        self.assertNotIn("Traceback", err)
        self.assertFalse(self.data.exists())
        code, _, err = self.cli("tokens", "--since", "not-ISO")
        self.assertEqual(code, 2)
        self.assertIn("ISO 8601", err)
        code, _, _ = self.cli("tokens", "--since", stamp(1), "--since-last-log")
        self.assertEqual(code, 2)

    def test_log_missing_required_reports_all(self):
        code, out, err = self.cli("log")
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        for option in ("--task", "--kind", "--success"):
            self.assertIn("missing " + option, err)
        self.assertFalse(self.data.exists())

    def test_log_collects_all_validation_problems_without_writing(self):
        code, out, err = self.cli(*self.log_args(
            "--task", "a" * 81, "--kind", "bad", "--success", "bad",
            "--rules", "C999", "--new", "C998", "--causes", "unknown",
            "--review-rounds", "bad", "--user-corrections", "-1", "--note", "x" * 161,
            "--external", "bad", "--limits", "month=3"))
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        for text in ("--task", "--kind", "--success", "C999", "C998", "unknown cause",
                     "--review-rounds", "--user-corrections", "--note", "--external", "--limits"):
            self.assertIn(text, err)
        self.assertEqual(len(err.splitlines()), 11)
        self.assertFalse(self.data.exists())

    def test_log_accepts_rules_from_all_layers_and_new_candidates(self):
        self.rows([call()])
        self.write(self.data / "candidates.md", "## C-2026-10-22-cos4: legacy candidate\n" + candidate("C1"))
        self.write(self.data / "local.md", "Apply (C12) before planning.\n")
        self.write(self.project / ".claude/lean-team.md", "Use C-2026-10-25-a here.\n")
        self.ok(*self.log_args("--rules", "C-2026-10-22-cos4,C12,C-2026-10-25-a",
                              "--new", "C1,C-2026-10-22-cos4"))
        row = self.metrics()[0]
        self.assertEqual(row["rules_applied"], ["C-2026-10-22-cos4", "C12", "C-2026-10-25-a"])
        self.assertEqual(row["candidates_new"], ["C1", "C-2026-10-22-cos4"])
        code, _, err = self.cli(*self.log_args("--new", "C12"))
        self.assertEqual(code, 2)
        self.assertIn("write its heading", err)
        self.assertEqual(len(self.metrics()), 1)

    def test_log_rule_ids_must_be_whole_tokens(self):
        self.write(self.data / "local.md", "C123 C-2026-10-25-abc\n")
        code, _, _ = self.cli(*self.log_args("--rules", "C12,C-2026-10-25-a"))
        self.assertEqual(code, 2)
        self.assertFalse((self.data / "metrics.jsonl").exists())

    def test_log_dry_run_writes_nothing_and_schema_order(self):
        self.rows([call(input_tokens=1)])
        before = sorted(str(path) for path in self.root.rglob("*"))
        row = json.loads(self.ok(*self.log_args("--dry-run")))
        self.assertEqual(list(row), METRIC_KEYS)
        self.assertEqual(row["skill_version"], "2.2.1")
        self.assertEqual(row["tokens"]["lead"]["calls"], 1)
        self.assertEqual(sorted(str(path) for path in self.root.rglob("*")), before)
        self.assertFalse(self.data.exists())

    def test_log_written_schema_external_limits_defaults_and_summary(self):
        self.rows([call(input_tokens=1)])
        output = self.ok(*self.log_args("--external", "codex:gpt-6.1-sol=216000,other:m=0",
            "--limits", "week=+3,5h=+12", "--review-rounds", "2", "--user-corrections", "1",
            "--causes", "lead-error,user-correction", "--note", "fixture only"))
        row = self.metrics()[0]
        self.assertEqual(list(row), METRIC_KEYS)
        self.assertEqual(row["tokens"]["external"], {"codex:gpt-6.1-sol": 216000, "other:m": 0})
        self.assertEqual(row["limits"], {"week": 3, "5h": 12})
        self.assertEqual(row["review_rounds"], 2)
        self.assertEqual(row["user_corrections"], 1)
        self.assertEqual(row["causes"], ["lead-error", "user-correction"])
        self.assertEqual(row["project"], "COS")
        self.assertEqual(row["until"], stamp(1))
        self.assertLessEqual(len(output.splitlines()), 10)
        self.assertIn("1 iterations since consolidation", output)

    def test_log_limits_signed_fractional_and_bad_pairs(self):
        self.rows([call()])
        row = json.loads(self.ok(*self.log_args("--dry-run", "--limits", "week=-1.5,5h=0")))
        self.assertEqual(row["limits"], {"week": -1.5, "5h": 0})
        for external in ("m=1", "x:m=-1", "x:m=2.5"):
            with self.subTest(external=external):
                self.assertEqual(self.cli(*self.log_args("--external", external))[0], 2)
        for limits in ("week=nan", "5h=inf", "other=3", "week=x"):
            with self.subTest(limits=limits):
                self.assertEqual(self.cli(*self.log_args("--limits", limits))[0], 2)
        self.assertFalse(self.data.exists())

    def test_log_missing_transcript_warns_and_succeeds(self):
        code, output, error = self.cli(*self.log_args())
        self.assertEqual(code, 0)
        self.assertIn("warning: transcript", error)
        self.assertIn("Logged", output)
        row = self.metrics()[0]
        self.assertIsNone(row["tokens"])
        self.assertIsNone(row["until"])

    def test_log_appends_after_legacy_line_without_newline(self):
        self.rows([call()])
        self.write(self.data / "metrics.jsonl", '{"date":"2026-10-24","session":"old"}')
        self.ok(*self.log_args())
        self.assertEqual(len(self.metrics()), 2)
        self.assertEqual(lt.metric_count(), 2)

    def test_log_explicit_project_dir_name_and_session(self):
        other = self.root / "elsewhere"
        self.write(other / ".claude/lean-team.md", "C14\n")
        self.rows([call()])
        self.ok(*self.log_args("--project-dir", str(other), "--project", "Named", "--rules", "C14"))
        self.assertEqual(self.metrics()[0]["project"], "Named")

    def test_status_due_counts_nonempty_legacy_and_invalid_rows_reset(self):
        self.write(self.data / "metrics.jsonl", '\n{"date":"2026-10-25"}\nnot json\n{}\nnull\n\n')
        status = self.status()
        self.assertEqual(status["iterations_since_consolidation"], 4)
        self.assertFalse(status["due"])
        with (self.data / "metrics.jsonl").open("a", encoding="utf-8") as stream:
            stream.write('{"rules_applied":"not a list"}\n')
        self.assertTrue(self.status()["due"])
        self.assertIn("consolidate now", self.ok("status"))
        self.assertEqual(len(self.ok("consolidated").splitlines()), 1)
        state = json.loads((self.data / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["consolidated_at_line"], 5)
        self.assertRegex(state["date"], r"^\d{4}-\d{2}-\d{2}$")
        self.assertFalse(self.status()["due"])
        self.assertEqual(self.status()["iterations_since_consolidation"], 0)

    def test_status_thresholds_and_applied_v1_only(self):
        self.write(self.data / "candidates.md", "".join([
            candidate("C1", effects=["yes"]), candidate("C2", "large", ["yes"]),
            candidate("C3", "large", ["yes", "yes"], status="trial"),
            candidate("C4", "small", ["yes", "yes"]),
            candidate("C5", "small", ["yes", "no", "yes"]),
            candidate("C6", effects=["no"] * 5),
            candidate("C7", effects=["yes"], quality="worse"),
            candidate("C8", effects=["yes"], status="rule")]))
        self.rows([dict(v=1, rules_applied=["C1", "C1"]), dict(v=1, rules_applied=["C1"]),
                   dict(rules_applied=["C1"]), dict(v=1, rules_applied="C1")], self.data / "metrics.jsonl")
        status = self.status()
        self.assertEqual(status["ready"], ["C1", "C3", "C5"])
        self.assertEqual(status["retire"], ["C6"])
        self.assertEqual(status["check"], ["C7"])
        self.assertEqual(status["candidates"][0]["applied"], 2)
        self.assertEqual(status["strict"], 8)
        self.assertEqual(status["open"], 7)

    def test_status_strict_unformatted_evidence_and_action_boundaries(self):
        text = candidate("C-2026-10-25-a", effects=["yes"])
        text += "Action: ignore this second action\n- 2026-10-25 COS/s v2.2.0: no effect here\n"
        text += "## C9: old format\n- 2026-10-25 COS/s v2.2.0: effect=yes\n"
        text += "## C10 · large · unknown · personal\n"
        text += candidate("C11", effects=[]) + "- 2026-10-25 COS/s v2.2.0: effect=yes\n"
        text += "### Another heading\n- 2026-10-25 COS/s v2.2.0: effect=yes, quality=worse\n"
        self.write(self.data / "candidates.md", text)
        status = self.status()
        self.assertEqual((status["strict"], status["unformatted"]), (2, 2))
        self.assertEqual(status["candidates"][0]["action"], "run verification")
        self.assertEqual(status["candidates"][0]["total"], 1)
        self.assertEqual(status["candidates"][1]["total"], 1)
        self.assertEqual(status["check"], [])

    def test_status_caps_at_boundaries(self):
        self.write(self.data / "local.md", "line\n" * 60)
        self.write(self.project / ".claude/lean-team.md", "line\n" * 40)
        self.assertFalse(self.status()["caps"]["personal"]["over"])
        self.assertFalse(self.status()["caps"]["project"]["over"])
        self.write(self.data / "local.md", "line\n" * 61)
        self.write(self.project / ".claude/lean-team.md", "line\n" * 41)
        self.assertTrue(self.status()["caps"]["personal"]["over"])
        self.assertTrue(self.status()["caps"]["project"]["over"])
        self.assertIn("OVER", self.ok("status"))

    def test_status_open_scope_filter_and_action_length(self):
        self.write(self.data / "candidates.md", "".join([
            candidate("C5", scope="adapter:codex"), candidate("C1", scope="core"),
            candidate("C6", scope="recipe:media", status="trial", action="y" * 120),
            candidate("C2", scope="personal"), candidate("C3", scope="project:COS", action="x" * 120),
            candidate("C4", scope="project:OTHER"), candidate("C7", status="retired"),
            candidate("C8", scope="recipe:media", status="rule")]))
        lines = self.ok("status", "--open").splitlines()
        self.assertEqual([line.split(" · ")[0] for line in lines], ["C1", "C2", "C3", "C5", "C6"])
        self.assertEqual(len(lines[2].split(" · ")[-1]), 90)
        self.assertEqual(lines[3].split(" · ")[-1], "[adapter:codex] run verification")
        self.assertEqual(lines[4].split(" · ")[-1], "[recipe:media] " + "y" * 90)
        self.assertEqual(self.status()["open"], 5)
        other = self.ok("status", "--open", "--project", "OTHER").splitlines()
        self.assertEqual([line.split(" · ")[0] for line in other], ["C1", "C2", "C4", "C5", "C6"])
        self.assertEqual(self.status("--project", "OTHER")["open"], 5)
        self.assertIn("open=5", self.ok("status", "--project", "OTHER"))

    def test_status_output_limits_and_ready_overflow(self):
        self.write(self.data / "candidates.md", "".join(candidate("C" + str(n), effects=["yes"])
                                                       for n in range(1, 26)))
        lines = self.ok("status", "--open").splitlines()
        self.assertEqual([line.split(" · ")[0] for line in lines], ["C" + str(n) for n in range(1, 26)])
        self.assertEqual(self.status()["open"], 25)
        output = self.ok("status")
        self.assertLessEqual(len(output.splitlines()), 8)
        self.assertIn("+20", output)

    def test_status_and_config_reads_never_create_data(self):
        self.assertEqual(self.status()["strict"], 0)
        self.assertEqual(self.ok("status", "--open"), "")
        self.assertEqual(self.ok("config"), "remind\n")
        self.assertFalse(self.data.exists())

    def test_status_invalid_state_defaults_and_clamps(self):
        self.write(self.data / "state.json", '{"consolidated_at_line":"bad"}')
        self.assertEqual(self.status()["iterations_since_consolidation"], 0)
        self.write(self.data / "state.json", '{"consolidated_at_line":999}')
        self.assertEqual(self.status()["iterations_since_consolidation"], 0)

    def test_start_reminder_layer_due_and_line_caps(self):
        self.write(self.project / ".claude/lean-team.md", "one\ntwo\n")
        self.write(self.data / "metrics.jsonl", "{}\n" * 5)
        output = self.ok("start", stdin=self.hook())
        lines = output.splitlines()
        self.assertLessEqual(len(lines), 5)
        self.assertTrue(all(len(line) <= 220 for line in lines))
        self.assertIn("lean-team 2.2.1", lines[0])
        self.assertIn("load the lean-team skill first", lines[0])
        self.assertTrue(lines[1].startswith('Tool: bash "') and lines[1].endswith('lt.sh" status | tokens | log'))
        self.assertIn(self.project.as_posix() + "/.claude/lean-team.md (2 lines)", output)
        self.assertIn("Learning: 5 iterations", output)
        self.assertNotIn("\\", output)

    def test_start_off_and_keywords_quiet(self):
        for mode in ("off", "keywords"):
            self.ok("config", "--auto", mode)
            self.assertEqual(self.ok("start", stdin=self.hook()), "")

    def test_start_invalid_stdin_only_header(self):
        self.write(self.project / ".claude/lean-team.md", "exists\n")
        self.write(self.data / "metrics.jsonl", "{}\n" * 5)
        for value in ("", "not json", "[]", "null"):
            code, out, err = self.cli("start", stdin=value)
            self.assertEqual(code, 0)
            self.assertEqual(err, "")
            self.assertEqual(len(out.splitlines()), 2)

    def test_hooks_read_utf8_stdin_bytes(self):
        # Real hooks get UTF-8 bytes; a Windows console default (cp1251) must not garble them.
        payload = json.dumps({"session_id": "utf8-session", "prompt": "Давай сэкономим токены"},
                             ensure_ascii=False).encode("utf-8")
        env = dict(os.environ, LEAN_TEAM_HOME=str(self.data), PYTHONIOENCODING="cp1251")
        run = subprocess.run([sys.executable, str(SCRIPT_DIR / "lt.py"), "prompt"], input=payload,
                             capture_output=True, env=env, timeout=20)
        self.assertEqual(run.returncode, 0)
        self.assertIn(b"load the lean-team skill", run.stdout)

    def previous(self, ident="previous-session-456", tool=True):
        path = self.folder / (ident + ".jsonl")
        if tool:
            row = dict(type="assistant", message=dict(content=[
                dict(type="tool_use", name="Skill", input=dict(skill="plugin:lean-team"))]))
        else:
            row = dict(type="user", message=dict(content="<command-name>/lean-team</command-name>"))
        self.rows([row], path)
        return path

    def test_start_nudge_once_for_previous_skill_tool(self):
        previous = self.previous()
        output = self.ok("start", stdin=self.hook())
        self.assertIn("Last session previous", output)
        self.assertTrue((self.data / "sessions" / (previous.stem + ".nudged")).exists())
        self.assertNotIn("Last session", self.ok("start", stdin=self.hook()))

    def test_start_nudge_user_command_and_legacy_logged_suppression(self):
        previous = self.previous(tool=False)
        self.rows([dict(session=previous.stem)], self.data / "metrics.jsonl")
        self.assertNotIn("Last session", self.ok("start", stdin=self.hook()))
        self.assertFalse((self.data / "sessions").exists())
        self.write(self.data / "metrics.jsonl", "")
        self.assertIn("Last session", self.ok("start", stdin=self.hook()))

    def test_start_only_newest_other_eligible_transcript(self):
        older = self.previous()
        newer = self.folder / "newer.jsonl"
        self.rows([call()], newer)
        os.utime(older, (10, 10))
        os.utime(newer, (20, 20))
        self.assertNotIn("Last session", self.ok("start", stdin=self.hook()))
        self.rows([call()], self.transcript)
        os.utime(self.transcript, (100, 100))
        self.assertNotIn("Last session", self.ok("start", stdin=self.hook()))

    def test_start_skips_oversized_files_and_finishes_quickly(self):
        self.previous()
        oversized = self.folder / "huge.jsonl"
        with oversized.open("wb") as stream:
            stream.truncate(lt.MAX_TRANSCRIPT + 1)
        os.utime(oversized, (2000000000, 2000000000))
        before = time.monotonic()
        with mock.patch.object(lt, "used_skill", wraps=lt.used_skill) as scan:
            output = self.ok("start", stdin=self.hook())
        self.assertLess(time.monotonic() - before, 2)
        self.assertIn("Last session", output)
        self.assertTrue(all(args[0] != oversized for args, _ in scan.call_args_list))

    def test_start_swallows_exceptions_without_partial_output(self):
        self.previous()
        with mock.patch.object(lt, "used_skill", side_effect=OSError("fixture failure")):
            self.assertEqual(self.cli("start", stdin=self.hook()), (0, "", ""))

    def test_prompt_all_keywords_and_once_per_hook_session(self):
        keywords = ["LEAN-TEAM", "LEAN TEAM", "Экономим", "ТОКЕНЫ", "ДЕШЁВЫЙ", "дешевле",
                    "SAVE TOKENS", "fewer tokens", "cheap", "Token Budget"]
        for n, keyword in enumerate(keywords):
            with self.subTest(keyword=keyword):
                session = "hook-session-" + str(n)
                hook = self.hook(session_id=session, prompt="Please " + keyword)
                output = self.ok("prompt", stdin=hook)
                self.assertEqual(output, "lean-team: the user wants to save tokens — load the lean-team skill before planning, if it is not loaded yet.\n")
                self.assertTrue((self.data / "sessions" / (session + ".hinted")).exists())
                self.assertEqual(self.ok("prompt", stdin=hook), "")

    def test_prompt_command_off_irrelevant_and_invalid_quiet(self):
        for prompt in ("/lean-team save tokens", "Please fix typo", "/LEAN-TEAM cheap"):
            self.assertEqual(self.ok("prompt", stdin=self.hook(prompt=prompt)), "")
        for value in ("", "not json", "[]", "null", "{", '{"prompt":12}'):
            self.assertEqual(self.cli("prompt", stdin=value), (0, "", ""))
        self.assertFalse(self.data.exists())
        self.ok("config", "--auto", "off")
        self.assertEqual(self.ok("prompt", stdin=self.hook(prompt="cheap")), "")

    def test_prompt_keywords_mode_and_exception_quiet(self):
        self.ok("config", "--auto", "keywords")
        self.assertTrue(self.ok("prompt", stdin=self.hook(prompt="cheap")))
        with mock.patch.object(lt, "touch", side_effect=OSError("fixture failure")):
            self.assertEqual(self.cli("prompt", stdin=self.hook(session_id="next", prompt="cheap")), (0, "", ""))

    def test_hook_session_cannot_escape_marker_directory(self):
        for session in ("../escape", "..", "C:\\escape", "a/b"):
            self.assertEqual(self.ok("prompt", stdin=self.hook(session_id=session, prompt="cheap")), "")
        self.assertFalse(self.data.exists())

    def test_config_set_get_preserves_keys_invalid_defaults(self):
        self.write(self.data / "config.json", '{"other":42,"auto":"invalid"}')
        self.assertEqual(self.ok("config"), "remind\n")
        for mode in ("off", "keywords", "remind"):
            self.assertEqual(self.ok("config", "--auto", mode), mode + "\n")
            self.assertEqual(self.ok("config"), mode + "\n")
            self.assertEqual(json.loads((self.data / "config.json").read_text(encoding="utf-8"))["other"], 42)
        code, _, err = self.cli("config", "--auto", "bad")
        self.assertEqual(code, 2)
        self.assertIn("remind|keywords|off", err)
        for text in ("not json", "[]", "null"):
            self.write(self.data / "config.json", text)
            self.assertEqual(self.ok("config"), "remind\n")

    def test_path_defaults_stay_in_fixture_home(self):
        with mock.patch.dict(os.environ, {"LEAN_TEAM_HOME": "", "LEAN_TEAM_PROJECTS_DIR": ""}):
            self.assertEqual(lt.data_dir(), self.root / "fake-home/.claude/lean-team")
            self.assertEqual(lt.projects_dir(), self.root / "unused-config/projects")
            with mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": ""}):
                self.assertEqual(lt.projects_dir(), self.root / "fake-home/.claude/projects")
            self.assertEqual(self.ok("config"), "remind\n")
            self.assertFalse((self.root / "fake-home").exists())

    def test_project_resolution_hook_git_and_cwd_fallbacks(self):
        args = lt.parser().parse_args(["status"])
        hook_dir = self.root / "hook-project"
        with mock.patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": ""}):
            self.assertEqual(lt.project_dir(args, dict(cwd=str(hook_dir))), hook_dir.resolve())
            result = subprocess.CompletedProcess([], 0, str(self.project) + "\n", "")
            with mock.patch.object(lt.subprocess, "run", return_value=result) as run:
                self.assertEqual(lt.project_dir(args), self.project)
                self.assertEqual(run.call_args.kwargs["timeout"], 2)
            with mock.patch.object(lt.subprocess, "run", side_effect=subprocess.TimeoutExpired("git", 2)):
                self.assertEqual(lt.project_dir(args), Path.cwd())

    def test_cli_isolated_entrypoint_and_usage_errors(self):
        result = subprocess.run([sys.executable, "-I", "-B", str(SCRIPT_DIR / "lt.py"), "config"],
                                capture_output=True, encoding="utf-8", env=dict(os.environ), timeout=5)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "remind\n", ""))
        self.assertFalse(self.data.exists())
        for args in ((), ("unknown",), ("status", "--unknown")):
            code, out, err = self.cli(*args)
            self.assertEqual(code, 2)
            self.assertEqual(out, "")
            self.assertIn("--help", err)
            self.assertNotIn("Traceback", err)

    def test_debug_reraises_command_error(self):
        with self.assertRaises(FileNotFoundError):
            self.cli("--debug", "tokens")
        with self.assertRaises(FileNotFoundError):
            self.cli("tokens", "--debug")

    def test_version_matches_plugin_manifest(self):
        self.assertEqual(lt.VERSION, "2.2.1")
        manifest = SCRIPT_DIR.parents[2] / ".claude-plugin/plugin.json"
        if manifest.exists():
            self.assertEqual(lt.VERSION, json.loads(manifest.read_text(encoding="utf-8"))["version"],
                             "lead-owned plugin.json must be updated to the contract's 2.2.1")


if __name__ == "__main__":
    unittest.main(verbosity=1)
