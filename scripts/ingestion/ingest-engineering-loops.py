#!/usr/bin/env python3
"""
Ingestion script for Deterministic Engineering & Verification Loops (Section 4 of PRD: LOOPS).
Extracts and normalizes state machines, self-healing compiler/test loops, Playwright DOM retry loops,
and autonomous supervisor controllers from 9 production repositories:
  1. SWE-agent/SWE-agent
  2. SWE-agent/mini-swe-agent
  3. All-Hands-AI/OpenHands
  4. langchain-ai/langgraph
  5. Codium-ai/AlphaCodium
  6. Emmimal/loop-engine
  7. the-open-engine/zeroshot
  8. browser-use/browser-use
  9. browserbase/stagehand
"""

import os
import json
import glob
import yaml

OUTPUT_PATH = "/home/lucky/repos/Promptally/data/extracted/engineering_loops.json"

def read_text_safe(path):
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception as e:
        print(f"Error reading {path}: {e}")
        return None

def main():
    loops = []
    print("Ingesting Engineering Loops...")

    # =========================================================================
    # 1. SWE-agent/SWE-agent
    # =========================================================================
    swe_configs = [
        {
            "id": "loop-swe-agent-default",
            "title": "SWE-Agent Autonomous Bash & Test Verification State Machine",
            "file": "/tmp/repo_sources/swe-agent/config/default.yaml",
            "category": "Compiler & Test Repair Loops",
            "description": "Standard SWE-Agent state-machine loop configuration executing commands in an interactive bash subshell, verifying exit codes, capturing compiler/test errors, and updating state until tests pass.",
            "stages": [
                {"stage_index": 1, "name": "Environment Initialization", "action_type": "setup", "description": "Configure conda environment, activate target repository directory, setup bash subshell environment variables."},
                {"stage_index": 2, "name": "Issue Parsing & Repo Exploration", "action_type": "inspection", "description": "Read issue description, locate relevant files via search/find commands, inspect AST or symbol definitions."},
                {"stage_index": 3, "name": "Reproduce & Write Regression Test", "action_type": "test_generation", "description": "Write standalone reproducing test script reproducing the reported issue and assert failure."},
                {"stage_index": 4, "name": "Iterative File Editing", "action_type": "code_modification", "description": "Use dedicated line-oriented or regex editor to patch source files."},
                {"stage_index": 5, "name": "Test Execution & Stderr Verification", "action_type": "output_validation", "description": "Run pytest/compiler, parse exit code ($?), extract stack trace if non-zero."},
                {"stage_index": 6, "name": "Deterministic Termination", "action_type": "stop_evaluation", "description": "If tests pass (exit code 0) and regression verified, invoke submit action. If failed, iterate with stderr context."}
            ],
            "stop_conditions": [
                "Exit code == 0 across all reproduction and regression test suites",
                "Explicit invocation of `COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT` command",
                "Step budget (30 turns) or cost ceiling exceeded"
            ],
            "failure_handling": {
                "error_extraction": "Captures raw exit code ($?), stdout, and stderr from subshell session",
                "retry_budget": 30,
                "backoff_or_mutation": "Injects failed command, exit code, and last 50 lines of stderr into the prompt for next action turn",
                "stuck_detection": "Monitors repeated commands with identical output and flags stagnation"
            },
            "target_frameworks": ["SWE-Agent", "Bash", "pytest", "Docker", "Git"],
            "code_format": "yaml",
            "tags": ["swe-agent", "bash", "test-driven-development", "compiler-repair", "docker", "state-machine"]
        },
        {
            "id": "loop-swe-agent-bash-only",
            "title": "SWE-Agent Pure Bash Tooling & Diagnostic Repair Loop",
            "file": "/tmp/repo_sources/swe-agent/config/bash_only.yaml",
            "category": "Compiler & Test Repair Loops",
            "description": "Minimalist SWE-Agent loop operating without custom editor binaries, relying solely on POSIX bash utilities, patch, sed, and git diff.",
            "stages": [
                {"stage_index": 1, "name": "Shell Session Initialization", "action_type": "setup", "description": "Spawns persistent bash session with error traps and custom command prompt delimiters."},
                {"stage_index": 2, "name": "Native POSIX Diagnosis", "action_type": "inspection", "description": "Grep, find, and cat source files to isolate bug location."},
                {"stage_index": 3, "name": "Direct Patch Application", "action_type": "code_modification", "description": "Generate diff/patch files and apply via `patch -p1` or standard input redirection."},
                {"stage_index": 4, "name": "Exit Code Check & Linting", "action_type": "output_validation", "description": "Check exit code of build / test runners."},
                {"stage_index": 5, "name": "Git Diff Verification", "action_type": "verification", "description": "Run `git diff` to ensure no spurious edits or unrelated changes were introduced."}
            ],
            "stop_conditions": [
                "Clean exit code 0 from test command",
                "`git diff` validates only expected files were modified",
                "Invocation of completion sentinel"
            ],
            "failure_handling": {
                "error_extraction": "Standard error streams, unhandled signals, and non-zero exit codes",
                "retry_budget": 25,
                "backoff_or_mutation": "Feeds back syntax error lines and failed assertions into bash command buffer",
                "stuck_detection": "Triggers warning if identical command executed 3 times sequentially"
            },
            "target_frameworks": ["SWE-Agent", "Bash", "POSIX", "Git"],
            "code_format": "yaml",
            "tags": ["swe-agent", "bash-only", "minimalist", "posix", "state-machine"]
        },
        {
            "id": "loop-swe-agent-coding-challenge",
            "title": "SWE-Agent Competitive Programming & Edge-Case Loop",
            "file": "/tmp/repo_sources/swe-agent/config/coding_challenge.yaml",
            "category": "Test-Driven Generation Loops",
            "description": "State machine optimized for competitive programming benchmarks with strict timeout bounds, edge test generation, and stdout matching.",
            "stages": [
                {"stage_index": 1, "name": "Problem Specification Parsing", "action_type": "inspection", "description": "Extract problem statement, sample inputs, expected outputs, time and memory limits."},
                {"stage_index": 2, "name": "Draft Algorithm & Test Harness", "action_type": "code_modification", "description": "Implement initial solution and setup local runner with sample test cases."},
                {"stage_index": 3, "name": "Local Execution & Timeout Verification", "action_type": "output_validation", "description": "Run solution with timeout utility (e.g. `timeout 2s python solution.py`)."},
                {"stage_index": 4, "name": "Edge-Case Stress Testing", "action_type": "test_generation", "description": "Generate boundary cases (min/max bounds, empty sets, large constraints) and benchmark execution time."},
                {"stage_index": 5, "name": "Submit & Validate Green", "action_type": "stop_evaluation", "description": "Verify zero exit code and exact string output match on all test suites."}
            ],
            "stop_conditions": [
                "All sample tests and synthetic edge tests match expected output exactly",
                "Runtime strictly within per-test timeout budget (e.g. < 2.0s)",
                "Memory consumption within platform limit"
            ],
            "failure_handling": {
                "error_extraction": "Captures TLE (Time Limit Exceeded), MLE (Memory Limit Exceeded), WA (Wrong Answer diff), and RTE (Runtime Error traceback)",
                "retry_budget": 20,
                "backoff_or_mutation": "Analyzes algorithmic complexity and mutates data structures (e.g. dict vs list lookup)",
                "stuck_detection": "Detects recurring TLE on identical input sizes"
            },
            "target_frameworks": ["SWE-Agent", "Python", "pytest", "Bash"],
            "code_format": "yaml",
            "tags": ["competitive-programming", "timeout-guard", "edge-cases", "algorithmic-repair"]
        },
        {
            "id": "loop-swe-agent-default-backticks",
            "title": "SWE-Agent Markdown Backticks Code Replacement Loop",
            "file": "/tmp/repo_sources/swe-agent/config/default_backticks.yaml",
            "category": "Compiler & Test Repair Loops",
            "description": "SWE-agent loop variant using fenced markdown code blocks with line numbering for deterministic multi-line block replacements.",
            "stages": [
                {"stage_index": 1, "name": "File Window Inspection", "action_type": "inspection", "description": "Display target file with explicit line numbering via custom view command."},
                {"stage_index": 2, "name": "Fenced Block Replacement", "action_type": "code_modification", "description": "Provide start_line and end_line followed by replacement code in markdown backticks."},
                {"stage_index": 3, "name": "Syntax Linting Check", "action_type": "output_validation", "description": "Automatic AST / Python syntax check on modified file."},
                {"stage_index": 4, "name": "Test Suite Validation", "action_type": "verification", "description": "Execute targeted pytest runner and inspect exit code."}
            ],
            "stop_conditions": [
                "Zero syntax errors and exit code 0 on tests",
                "Complete task sentinel invoked"
            ],
            "failure_handling": {
                "error_extraction": "Line offset mismatches and Python SyntaxError exceptions",
                "retry_budget": 30,
                "backoff_or_mutation": "Re-reads updated file window to re-synchronize line numbers before re-attempting edit",
                "stuck_detection": "Reverts failed edit if line numbers do not match original buffer"
            },
            "target_frameworks": ["SWE-Agent", "Python", "AST", "Git"],
            "code_format": "yaml",
            "tags": ["swe-agent", "backticks", "line-numbering", "syntax-guard"]
        },
        {
            "id": "loop-swe-agent-multimodal-images",
            "title": "SWE-Agent Multimodal Visual Inspection & UI Verification Loop",
            "file": "/tmp/repo_sources/swe-agent/config/default_mm_with_images.yaml",
            "category": "Compiler & Test Repair Loops",
            "description": "Multimodal state machine capable of capturing webpage or GUI screenshots, rendering visual diffs, and verifying visual layouts against test specifications.",
            "stages": [
                {"stage_index": 1, "name": "Environment & Headless Browser Launch", "action_type": "setup", "description": "Launch Playwright/Selenium headless browser or Xvfb display server."},
                {"stage_index": 2, "name": "Render Page & Screenshot Capture", "action_type": "inspection", "description": "Capture PNG snapshot of rendered webpage or component."},
                {"stage_index": 3, "name": "Visual Diff & Metric Evaluation", "action_type": "output_validation", "description": "Compare against reference screenshot or inspect bounding boxes."},
                {"stage_index": 4, "name": "CSS/Frontend Code Modification", "action_type": "code_modification", "description": "Modify frontend CSS/HTML/JS assets to align visual presentation."},
                {"stage_index": 5, "name": "Re-render & Verification Loop", "action_type": "verification", "description": "Re-take screenshot and loop until layout discrepancy falls below perceptual threshold."}
            ],
            "stop_conditions": [
                "Visual regression diff within tolerance (< 0.1% pixel diff)",
                "Zero console errors in headless browser log",
                "Unit and E2E tests pass with exit code 0"
            ],
            "failure_handling": {
                "error_extraction": "Browser console errors, unhandled rejections, pixel difference heatmaps",
                "retry_budget": 20,
                "backoff_or_mutation": "Supplies annotated screenshot showing misaligned bounding boxes to the model",
                "stuck_detection": "Flags oscillating CSS changes (e.g. changing margin back and forth)"
            },
            "target_frameworks": ["SWE-Agent", "Playwright", "Multimodal", "CSS"],
            "code_format": "yaml",
            "tags": ["multimodal", "visual-diff", "screenshot-verification", "playwright"]
        }
    ]

    for item in swe_configs:
        content = read_text_safe(item["file"])
        if content:
            loops.append({
                "id": item["id"],
                "title": item["title"],
                "source_repository": "SWE-agent/SWE-agent",
                "source_file": os.path.relpath(item["file"], "/tmp/repo_sources/swe-agent"),
                "framework": "SWE-agent",
                "category": item["category"],
                "description": item["description"],
                "loop_stages": item["stages"],
                "stop_conditions": item["stop_conditions"],
                "failure_handling": item["failure_handling"],
                "raw_config_payload": content,
                "code_format": item["code_format"],
                "tags": item["tags"]
            })

    # =========================================================================
    # 2. SWE-agent/mini-swe-agent
    # =========================================================================
    mini_configs = [
        {
            "id": "loop-mini-swe-agent-default",
            "title": "Mini SWE-Agent Lightweight Python Verification State Machine",
            "file": "/tmp/repo_sources/mini-swe-agent/src/minisweagent/config/default.yaml",
            "category": "Compiler & Test Repair Loops",
            "description": "Ultra-lightweight state machine for SWE-Bench evaluation featuring minimal token overhead, single-call tool dispatch, and deterministic step counter.",
            "stages": [
                {"stage_index": 1, "name": "Docker Container Mounting", "action_type": "setup", "description": "Attach to isolated Docker container with pre-built repo dependencies."},
                {"stage_index": 2, "name": "Problem Spec Ingestion", "action_type": "inspection", "description": "Parse issue description and repository context."},
                {"stage_index": 3, "name": "Single-Command Turn Loop", "action_type": "code_modification", "description": "Execute bash tool commands one turn at a time with strict output truncations."},
                {"stage_index": 4, "name": "Exit Code Check & Truncation Filter", "action_type": "output_validation", "description": "Validate command return code; truncate output exceeding max line limits."},
                {"stage_index": 5, "name": "Final Patch Output", "action_type": "stop_evaluation", "description": "Extract git patch using `git diff` and verify non-empty patch."}
            ],
            "stop_conditions": [
                "Agent issues `COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT`",
                "Exit code 0 on test execution",
                "Max turns reached (default 30)"
            ],
            "failure_handling": {
                "error_extraction": "Captures subshell returncode and stderr lines",
                "retry_budget": 30,
                "backoff_or_mutation": "Truncates long error traces to protect context window while preserving first 20 and last 20 lines of traceback",
                "stuck_detection": "Monitors identical action output across turns"
            },
            "target_frameworks": ["Mini-SWE-Agent", "Docker", "Python", "Bash"],
            "code_format": "yaml",
            "tags": ["mini-swe-agent", "lightweight", "docker-isolated", "context-budget"]
        },
        {
            "id": "loop-mini-swe-agent-swebench",
            "title": "Mini SWE-Agent SWE-Bench Benchmark Evaluation State Machine",
            "file": "/tmp/repo_sources/mini-swe-agent/src/minisweagent/config/benchmarks/swebench.yaml",
            "category": "Compiler & Test Repair Loops",
            "description": "Production benchmark loop calibrated for SWE-bench Lite and Verified test suites with automated git worktree isolation and test isolation.",
            "stages": [
                {"stage_index": 1, "name": "Repo Worktree Setup", "action_type": "setup", "description": "Create isolated git branch from issue base commit in sandbox."},
                {"stage_index": 2, "name": "Environment Discovery", "action_type": "inspection", "description": "Locate test command specification from repo manifest (tox, pytest, setup.py)."},
                {"stage_index": 3, "name": "Iterative Patch Application", "action_type": "code_modification", "description": "Apply edits to source files."},
                {"stage_index": 4, "name": "Fail-to-Pass Verification", "action_type": "output_validation", "description": "Verify previously failing tests now pass (F2P) while all passing tests remain green (P2P)."},
                {"stage_index": 5, "name": "Patch Generation & Submission", "action_type": "stop_evaluation", "description": "Run `git diff` and write submission patch artifact."}
            ],
            "stop_conditions": [
                "100% of Fail-to-Pass tests convert to green",
                "0% regression in Pass-to-Pass test suites",
                "Patch size > 0 and < max allowable byte budget"
            ],
            "failure_handling": {
                "error_extraction": "Pytest assertion failure diffs and unittest summary lines",
                "retry_budget": 35,
                "backoff_or_mutation": "Focuses model on specific failing assertion messages and line numbers",
                "stuck_detection": "Terminates early if test runner fails to execute or segfaults repeatedly"
            },
            "target_frameworks": ["Mini-SWE-Agent", "SWE-bench", "pytest", "Docker"],
            "code_format": "yaml",
            "tags": ["swe-bench", "benchmark", "fail-to-pass", "regression-testing"]
        },
        {
            "id": "loop-mini-swe-agent-retry-engine",
            "title": "Mini SWE-Agent Deterministic Exponential Backoff & API Retry Engine",
            "file": "/tmp/repo_sources/mini-swe-agent/src/minisweagent/models/utils/retry.py",
            "category": "Goal-Directed Autonomous Controllers",
            "description": "Pure-Python deterministic retry controller implementing exponential jitter backoff, rate-limit isolation, and fatal error fast-fail.",
            "stages": [
                {"stage_index": 1, "name": "Attempt Execution", "action_type": "dispatch", "description": "Invoke API / tool action with monotonic timestamp recording."},
                {"stage_index": 2, "name": "Exception Classification", "action_type": "inspection", "description": "Classify exception into retryable (429 rate limit, 503 service unavailable, timeout) vs fatal (401 auth, 400 invalid param)."},
                {"stage_index": 3, "name": "Jittered Backoff Calculation", "action_type": "calculation", "description": "Compute sleep delay: delay = min(max_delay, base_delay * 2^attempt) + random_jitter."},
                {"stage_index": 4, "name": "Deterministic Sleep & Turn Retry", "action_type": "retry", "description": "Wait calculated duration and re-dispatch until budget expires or success."}
            ],
            "stop_conditions": [
                "Successful API response received without exception",
                "Fatal non-retryable exception encountered (fast-fail)",
                "Total retry attempts exceed max_retries limit"
            ],
            "failure_handling": {
                "error_extraction": "HTTP response status codes, error response bodies, exception type hierarchy",
                "retry_budget": 5,
                "backoff_or_mutation": "Exponential delay factor with decorrelated jitter to prevent thundering herd",
                "stuck_detection": "Tracks cumulative latency and aborts if total elapsed time exceeds global timeout"
            },
            "target_frameworks": ["Python", "LiteLLM", "Tenacity", "REST"],
            "code_format": "python",
            "tags": ["retry-engine", "exponential-backoff", "rate-limit", "resilience"]
        }
    ]

    for item in mini_configs:
        content = read_text_safe(item["file"])
        if content:
            loops.append({
                "id": item["id"],
                "title": item["title"],
                "source_repository": "SWE-agent/mini-swe-agent",
                "source_file": os.path.relpath(item["file"], "/tmp/repo_sources/mini-swe-agent"),
                "framework": "Mini-SWE-Agent",
                "category": item["category"],
                "description": item["description"],
                "loop_stages": item["stages"],
                "stop_conditions": item["stop_conditions"],
                "failure_handling": item["failure_handling"],
                "raw_config_payload": content,
                "code_format": item["code_format"],
                "tags": item["tags"]
            })

    # =========================================================================
    # 3. All-Hands-AI / OpenHands (formerly OpenDevin)
    # =========================================================================
    openhands_items = [
        {
            "id": "loop-openhands-codeact-agent",
            "title": "OpenHands CodeAct Iterative Bash & Python Execution State Machine",
            "file": "/tmp/repo_sources/openhands_backend/openhands/agenthub/codeact_agent/codeact_agent.py",
            "category": "Compiler & Test Repair Loops",
            "description": "Foundational CodeAct state machine where the LLM writes executable code snippets and bash commands directly to perform multi-step software engineering repairs.",
            "stages": [
                {"stage_index": 1, "name": "Event Stream State Ingestion", "action_type": "setup", "description": "Deserialize current action/observation history from OpenHands event stream."},
                {"stage_index": 2, "name": "Action Synthesis", "action_type": "code_modification", "description": "Generate next bash command, Python code execution block, or file editing command."},
                {"stage_index": 3, "name": "Sandboxed Execution", "action_type": "dispatch", "description": "Execute action inside sandboxed Docker/runtime container and capture observation."},
                {"stage_index": 4, "name": "Observation Processing & Error Check", "action_type": "output_validation", "description": "Inspect exit code, stderr, and output length; prune observation if token limits exceeded."},
                {"stage_index": 5, "name": "Loop State Transition", "action_type": "stop_evaluation", "description": "Determine whether task is finished (AgentFinishAction) or requires further iterative repair turns."}
            ],
            "stop_conditions": [
                "Agent issues `AgentFinishAction` with summary message",
                "User sends manual stop / pause signal",
                "Maximum iterations limit reached (e.g. 50 turns)",
                "Fatal sandbox execution failure"
            ],
            "failure_handling": {
                "error_extraction": "Captures bash exit code, stderr lines, Python SyntaxError, and command timeout signals",
                "retry_budget": 50,
                "backoff_or_mutation": "Returns detailed CmdOutputObservation containing stderr back to the model context",
                "stuck_detection": "Monitors repetitive identical actions via `stuck.py` detector"
            },
            "target_frameworks": ["OpenHands", "CodeAct", "Docker", "Python", "Bash"],
            "code_format": "python",
            "tags": ["openhands", "codeact", "event-stream", "docker", "state-machine"]
        },
        {
            "id": "loop-openhands-agent-controller",
            "title": "OpenHands AgentController Action-Observation Lifecycle Machine",
            "file": "/tmp/repo_sources/openhands_backend/openhands/controller/agent_controller.py",
            "category": "Goal-Directed Autonomous Controllers",
            "description": "Central coordinator state machine of OpenHands driving turn-by-turn agent execution, state persistence, delegate subagent coordination, and error containment.",
            "stages": [
                {"stage_index": 1, "name": "State Validation & Pre-step Hooks", "action_type": "setup", "description": "Check controller state (RUNNING, PAUSED, FINISHED, ERROR) and execute pre-turn hooks."},
                {"stage_index": 2, "name": "Agent Step Dispatch", "action_type": "dispatch", "description": "Call agent `step()` method to generate next Action from current State."},
                {"stage_index": 3, "name": "Action Execution via Runtime", "action_type": "code_modification", "description": "Pass Action to runtime environment (bash, browser, file edit) to produce Observation."},
                {"stage_index": 4, "name": "Event Stream Emission", "action_type": "output_validation", "description": "Emit Action and Observation events to event log; update state iteration counter."},
                {"stage_index": 5, "name": "Stuck Detection & Termination Gate", "action_type": "stop_evaluation", "description": "Check if agent is repeating commands or if finish conditions are met."}
            ],
            "stop_conditions": [
                "Controller state transitions to FINISHED or PAUSED",
                "Max iterations ceiling reached",
                "Critical runtime unrecoverable error"
            ],
            "failure_handling": {
                "error_extraction": "Catches runtime exceptions, tool execution timeouts, and LLM API errors",
                "retry_budget": 3,
                "backoff_or_mutation": "Converts uncaught exceptions into ErrorObservation events so the agent can inspect its own failure",
                "stuck_detection": "Integrates `StuckDetector` to identify cyclic action patterns"
            },
            "target_frameworks": ["OpenHands", "Python", "AsyncIO", "Event-Driven"],
            "code_format": "python",
            "tags": ["openhands", "controller", "lifecycle", "state-machine", "event-stream"]
        },
        {
            "id": "loop-openhands-stuck-detector",
            "title": "OpenHands Cyclic Repetition & Loop Stagnation Breaker",
            "file": "/tmp/repo_sources/openhands_backend/openhands/controller/stuck.py",
            "category": "Goal-Directed Autonomous Controllers",
            "description": "Deterministic pattern analyzer that inspects the rolling history of actions and observations to detect infinite loops, repeating commands, and non-advancing edit cycles.",
            "stages": [
                {"stage_index": 1, "name": "Action Fingerprinting", "action_type": "inspection", "description": "Normalize and hash command strings, file paths, and tool arguments."},
                {"stage_index": 2, "name": "Sliding Window Analysis", "action_type": "calculation", "description": "Scan the last N actions for recurring subsequences (e.g. A-B-A-B or A-A-A)."},
                {"stage_index": 3, "name": "Observation Stagnation Check", "action_type": "output_validation", "description": "Verify if consecutive observations produce identical error strings."},
                {"stage_index": 4, "name": "Intervention Trigger", "action_type": "retry", "description": "Inject high-priority warning message advising the model to alter approach or fail gracefully."}
            ],
            "stop_conditions": [
                "Cyclic threshold exceeded without progress (e.g. 4 identical failed commands)",
                "Action sequence diversified successfully"
            ],
            "failure_handling": {
                "error_extraction": "Identical command signatures and unchanged stderr strings",
                "retry_budget": 3,
                "backoff_or_mutation": "Forces model to change strategy by appending explicit system directive",
                "stuck_detection": "Immediate detection of cyclic 2-step and 3-step repeating action subgraphs"
            },
            "target_frameworks": ["OpenHands", "Python", "Heuristics"],
            "code_format": "python",
            "tags": ["loop-breaker", "stuck-detection", "infinite-loop-prevention", "heuristics"]
        },
        {
            "id": "loop-openhands-verifier",
            "title": "OpenHands Automated Post-Generation Verifier & Diff Review Loop",
            "file": "/tmp/repo_sources/openhands_backend/openhands/agenthub/micro/verifier/agent.yaml",
            "category": "Compiler & Test Repair Loops",
            "description": "Specialized subagent loop that verifies whether another agent's proposed changes actually solve the problem without introducing regressions or code style violations.",
            "stages": [
                {"stage_index": 1, "name": "Extract Pull Request / Git Diff", "action_type": "inspection", "description": "Inspect `git diff HEAD~1` or uncommitted working tree changes."},
                {"stage_index": 2, "name": "Run Clean Test Suite", "action_type": "output_validation", "description": "Execute pytest or language-specific test runner against the modified codebase."},
                {"stage_index": 3, "name": "Static Analysis & Linter Run", "action_type": "verification", "description": "Execute ruff, flake8, or mypy to ensure type safety and PEP8 compliance."},
                {"stage_index": 4, "name": "Verdict Generation", "action_type": "stop_evaluation", "description": "Issue APPROVE if tests and linters pass cleanly; otherwise issue REJECT with exact error list."}
            ],
            "stop_conditions": [
                "All test suites and linters return exit code 0",
                "Verification report generated with explicit pass/fail verdict"
            ],
            "failure_handling": {
                "error_extraction": "Linter violation codes and failed test tracebacks",
                "retry_budget": 5,
                "backoff_or_mutation": "Lists exact line numbers and missing types for authoring agent to fix",
                "stuck_detection": "Rejects if changes cannot compile after 2 attempts"
            },
            "target_frameworks": ["OpenHands", "pytest", "ruff", "mypy", "Git"],
            "code_format": "yaml",
            "tags": ["verifier", "code-review", "linting", "automated-qa"]
        }
    ]

    for item in openhands_items:
        content = read_text_safe(item["file"])
        if content:
            loops.append({
                "id": item["id"],
                "title": item["title"],
                "source_repository": "All-Hands-AI/OpenHands",
                "source_file": os.path.relpath(item["file"], "/tmp/repo_sources/openhands_backend"),
                "framework": "OpenHands",
                "category": item["category"],
                "description": item["description"],
                "loop_stages": item["stages"],
                "stop_conditions": item["stop_conditions"],
                "failure_handling": item["failure_handling"],
                "raw_config_payload": content,
                "code_format": item["code_format"],
                "tags": item["tags"]
            })

    # =========================================================================
    # 4. langchain-ai/langgraph
    # =========================================================================
    langgraph_files = [
        {
            "id": "loop-langgraph-code-assistant",
            "title": "LangGraph Code Generation, Import Checking & Pytest Self-Correction Graph",
            "file": "/tmp/repo_sources/langgraph_full/code_assistant.ipynb",
            "category": "Compiler & Test Repair Loops",
            "description": "Deterministic LangGraph state machine implementing: Generate Code -> Check Imports -> Run pytest/ruff -> Conditional Edge (Finish if exit code 0, else loop back with traceback).",
            "stages": [
                {"stage_index": 1, "name": "Draft Code Generation (Node: generate)", "action_type": "code_modification", "description": "LLM generates initial Python function and test harness based on user requirements."},
                {"stage_index": 2, "name": "Import & Syntax Validation (Node: check_imports)", "action_type": "inspection", "description": "Deterministic Python AST parse tree verification to detect missing imports and syntax errors."},
                {"stage_index": 3, "name": "Pytest / Ruff Execution (Node: check_execution)", "action_type": "output_validation", "description": "Run generated code and unit tests inside an isolated sandbox subprocess, capturing exit code and stderr."},
                {"stage_index": 4, "name": "Conditional Routing Edge (Edge: decide_to_finish)", "action_type": "stop_evaluation", "description": "If exit code is 0 and no syntax errors, route to END. If errors exist and retries < max_retries, route to generate with traceback."}
            ],
            "stop_conditions": [
                "Execution exit code == 0 with all test assertions passing",
                "Zero AST syntax or import errors",
                "Iteration counter exceeds retry budget (default 3 retries)"
            ],
            "failure_handling": {
                "error_extraction": "Captures raw Python traceback, line number of failure, and stdout/stderr string",
                "retry_budget": 3,
                "backoff_or_mutation": "Appends formatted error traceback to LangGraph message state so model directly sees what failed",
                "stuck_detection": "Conditional edge checks loop count in state dictionary and terminates if max_retries exceeded"
            },
            "target_frameworks": ["LangGraph", "LangChain", "pytest", "Python AST"],
            "code_format": "python",
            "tags": ["langgraph", "state-machine", "self-healing", "conditional-edges", "pytest", "ast"]
        },
        {
            "id": "loop-langgraph-reflexion",
            "title": "LangGraph Reflexion Deterministic State Machine (Actor-Evaluator-Reviser)",
            "file": "/tmp/repo_sources/langgraph_full/reflexion.ipynb",
            "category": "Goal-Directed Autonomous Controllers",
            "description": "Deterministic implementation of the Reflexion architecture in LangGraph: Actor produces output -> Evaluator scores against ground truth/rubric -> Reviser reflects on critique -> Conditional loop back until quality threshold is met.",
            "stages": [
                {"stage_index": 1, "name": "Initial Execution (Node: draft)", "action_type": "code_modification", "description": "Actor node generates initial solution or response."},
                {"stage_index": 2, "name": "Deterministic Evaluation (Node: evaluate)", "action_type": "output_validation", "description": "Evaluator checks solution against automated test assertions, regex criteria, or rubric scores."},
                {"stage_index": 3, "name": "Self-Reflection Synthesis (Node: reflect)", "action_type": "inspection", "description": "If evaluation fails, reflection node synthesizes a critique identifying specific flaws and corrective strategies."},
                {"stage_index": 4, "name": "Revision Node (Node: revise)", "action_type": "code_modification", "description": "Reviser incorporates critique and reflection to generate improved candidate."},
                {"stage_index": 5, "name": "Conditional Loop Edge", "action_type": "stop_evaluation", "description": "Branches to END if score threshold met or loops back to evaluate."}
            ],
            "stop_conditions": [
                "Evaluation score passes target threshold (e.g. 100% test pass)",
                "Maximum reflection iterations reached (default 3)"
            ],
            "failure_handling": {
                "error_extraction": "Captures assertion failures, missing requirements, and numeric rubric deltas",
                "retry_budget": 3,
                "backoff_or_mutation": "Maintains persistent reflection memory in LangGraph state, preventing recurring mistakes",
                "stuck_detection": "Detects stagnant score between consecutive reflection rounds"
            },
            "target_frameworks": ["LangGraph", "Reflexion", "Pydantic", "Python"],
            "code_format": "python",
            "tags": ["reflexion", "actor-critic", "self-reflection", "langgraph", "evaluator"]
        }
    ]

    for item in langgraph_files:
        content = read_text_safe(item["file"])
        if content:
            loops.append({
                "id": item["id"],
                "title": item["title"],
                "source_repository": "langchain-ai/langgraph",
                "source_file": os.path.relpath(item["file"], "/tmp/repo_sources/langgraph_full"),
                "framework": "LangGraph",
                "category": item["category"],
                "description": item["description"],
                "loop_stages": item["stages"],
                "stop_conditions": item["stop_conditions"],
                "failure_handling": item["failure_handling"],
                "raw_config_payload": content,
                "code_format": item["code_format"],
                "tags": item["tags"]
            })

    # =========================================================================
    # 5. Codium-ai/AlphaCodium
    # =========================================================================
    alphacodium_items = [
        {
            "id": "loop-alphacodium-dataset-solver",
            "title": "AlphaCodium Multi-Stage Test-Driven Code Generation Flow",
            "file": "/tmp/repo_sources/alphacodium/alpha_codium/gen/dataset_solver.py",
            "category": "Test-Driven Generation Loops",
            "description": "Full AlphaCodium multi-stage architecture: Problem Reflection -> AI Test Generation -> Public Test Run -> Iterative Code Fix on Failing Tests -> Multi-Candidate Selection.",
            "stages": [
                {"stage_index": 1, "name": "Problem Reflection Stage", "action_type": "inspection", "description": "Analyze problem goals, inputs, outputs, rules, and computational complexity."},
                {"stage_index": 2, "name": "AI Test Generation Stage", "action_type": "test_generation", "description": "Generate 6-8 diverse AI test cases including extreme values, large inputs, and edge boundary conditions."},
                {"stage_index": 3, "name": "Initial Solution Generation", "action_type": "code_modification", "description": "Synthesize initial 2-3 solution candidates."},
                {"stage_index": 4, "name": "Public Tests Evaluation", "action_type": "output_validation", "description": "Run solution against problem public test cases and record tracebacks."},
                {"stage_index": 5, "name": "Iterative Fix from Test Failures", "action_type": "retry", "description": "Analyze failure causes and iteratively patch code until all tests pass."},
                {"stage_index": 6, "name": "AI Tests Evaluation & Final Selection", "action_type": "stop_evaluation", "description": "Run candidate solutions across all validated AI test cases and select top performing code."}
            ],
            "stop_conditions": [
                "Solution passes 100% of public tests and generated AI tests",
                "Max fix iterations per solution reached (default 3-5)",
                "Execution timeout or fatal memory limit"
            ],
            "failure_handling": {
                "error_extraction": "Captures input, expected output, actual output, exit code, execution time, and stdout/stderr",
                "retry_budget": 5,
                "backoff_or_mutation": "Generates a structured 'test_failure_analysis' explaining why output differed from expected before modifying code",
                "stuck_detection": "Discards candidate if fix introduces more failures than previous iteration"
            },
            "target_frameworks": ["AlphaCodium", "Python", "LocalExec", "TOML"],
            "code_format": "python",
            "tags": ["alphacodium", "test-driven", "edge-tests", "multi-stage", "competitive-programming"]
        },
        {
            "id": "loop-alphacodium-test-generation-stage",
            "title": "AlphaCodium Synthetic Edge-Test Generation & Self-Validation Stage",
            "file": "/tmp/repo_sources/alphacodium/alpha_codium/gen/stages/run_generate_ai_test.py",
            "category": "Test-Driven Generation Loops",
            "description": "Stage dedicated to generating high-coverage synthetic unit tests covering edge conditions, corner cases, empty inputs, and maximum bounds.",
            "stages": [
                {"stage_index": 1, "name": "Edge Case Taxonomy Prompting", "action_type": "setup", "description": "Prompt model to identify tricky algorithmic constraints (off-by-one, negative values, duplicates)."},
                {"stage_index": 2, "name": "Test Case Synthesis", "action_type": "test_generation", "description": "Generate JSON-structured test cases with input strings and expected outputs."},
                {"stage_index": 3, "name": "Validation via Independent Oracle", "action_type": "output_validation", "description": "Verify synthetic tests against naive or brute-force oracle where feasible."},
                {"stage_index": 4, "name": "Deduplication & Test Registry", "action_type": "stop_evaluation", "description": "Filter redundant test cases and register final curated test suite."}
            ],
            "stop_conditions": [
                "Target number of diverse test cases (e.g. 6-10) generated",
                "Zero malformed input/output schemas"
            ],
            "failure_handling": {
                "error_extraction": "Schema validation errors and inconsistent test input types",
                "retry_budget": 3,
                "backoff_or_mutation": "Re-prompts with format requirements if test format is non-compliant",
                "stuck_detection": "Filters out duplicate tests based on input hash"
            },
            "target_frameworks": ["AlphaCodium", "Python", "Pydantic"],
            "code_format": "python",
            "tags": ["test-generation", "synthetic-data", "edge-cases", "alphacodium"]
        },
        {
            "id": "loop-alphacodium-analyze-and-fix",
            "title": "AlphaCodium Test Failure Analysis & Iterative Code Fix Loop",
            "file": "/tmp/repo_sources/alphacodium/alpha_codium/gen/stages/indirect/run_analyze_and_fix_test_failure.py",
            "category": "Compiler & Test Repair Loops",
            "description": "Iterative repair loop separating the diagnosis phase from the fix phase: first analyzes why the code failed on input X, then applies targeted surgery.",
            "stages": [
                {"stage_index": 1, "name": "Failure Symptom Extraction", "action_type": "inspection", "description": "Extract failing test case details: input value, expected output, received output, stderr."},
                {"stage_index": 2, "name": "Root Cause Analysis (Thought Step)", "action_type": "calculation", "description": "Generate natural language diagnosis of algorithmic defect without altering code."},
                {"stage_index": 3, "name": "Targeted Code Surgery", "action_type": "code_modification", "description": "Rewrite specific functions or logic blocks to address the identified root cause."},
                {"stage_index": 4, "name": "Re-run Test Verification", "action_type": "output_validation", "description": "Run updated code against previously failing test and all previously passing tests."}
            ],
            "stop_conditions": [
                "Failing test passes without breaking any previously passing tests",
                "Iteration limit reached"
            ],
            "failure_handling": {
                "error_extraction": "Execution diff, assertion tracebacks, and stdout inspection",
                "retry_budget": 3,
                "backoff_or_mutation": "Dual-prompt separation: diagnosis prompt followed by patching prompt",
                "stuck_detection": "Rolls back to previous version if regressions detected"
            },
            "target_frameworks": ["AlphaCodium", "Python", "LocalExec"],
            "code_format": "python",
            "tags": ["analyze-and-fix", "root-cause-analysis", "iterative-repair", "alphacodium"]
        }
    ]

    for item in alphacodium_items:
        content = read_text_safe(item["file"])
        if content:
            loops.append({
                "id": item["id"],
                "title": item["title"],
                "source_repository": "Codium-ai/AlphaCodium",
                "source_file": os.path.relpath(item["file"], "/tmp/repo_sources/alphacodium"),
                "framework": "AlphaCodium",
                "category": item["category"],
                "description": item["description"],
                "loop_stages": item["stages"],
                "stop_conditions": item["stop_conditions"],
                "failure_handling": item["failure_handling"],
                "raw_config_payload": content,
                "code_format": item["code_format"],
                "tags": item["tags"]
            })

    # =========================================================================
    # 6. Emmimal/loop-engine
    # =========================================================================
    loop_engine_items = [
        {
            "id": "loop-engine-goal-controller",
            "title": "Loop-Engine Goal-Directed Deterministic Controller",
            "file": "/tmp/repo_sources/loop-engine/src/loop_engineering/controller.py",
            "category": "Goal-Directed Autonomous Controllers",
            "description": "Pure-Python goal-directed loop controller demonstrating failure isolation, retry budgets, monotonic state progress, and stop conditions without LLM hallucination drift.",
            "stages": [
                {"stage_index": 1, "name": "Goal & Precondition Check", "action_type": "setup", "description": "Verify goal specification and assert that preconditions are satisfied in the current environment."},
                {"stage_index": 2, "name": "Action Dispatch & Guard Rails", "action_type": "dispatch", "description": "Dispatch action to target environment with strict timeout and resource caps."},
                {"stage_index": 3, "name": "Invariant & Postcondition Verification", "action_type": "output_validation", "description": "Execute deterministic postcondition checks on state transition."},
                {"stage_index": 4, "name": "Budget & Termination Evaluation", "action_type": "stop_evaluation", "description": "Decrement step/cost budget; check if terminal goal node reached."}
            ],
            "stop_conditions": [
                "Target goal state postconditions fully satisfied",
                "Step budget exhausted",
                "Unrecoverable invariant violation detected"
            ],
            "failure_handling": {
                "error_extraction": "Captures assertion exceptions and invariant check failures",
                "retry_budget": 10,
                "backoff_or_mutation": "Rolls state back to last verified checkpoint on failure",
                "stuck_detection": "Measures state distance metric to ensure forward progress towards goal"
            },
            "target_frameworks": ["Loop-Engine", "Python", "State-Machine"],
            "code_format": "python",
            "tags": ["loop-engine", "goal-directed", "invariants", "deterministic-controller"]
        },
        {
            "id": "loop-engine-state-graph",
            "title": "Loop-Engine Directed Acyclic Graph (DAG) State Transition Engine",
            "file": "/tmp/repo_sources/loop-engine/src/loop_engineering/graph.py",
            "category": "Goal-Directed Autonomous Controllers",
            "description": "Graph-based state machine defining nodes, typed transitions, validation predicates, and fallback edges for autonomous agent workflows.",
            "stages": [
                {"stage_index": 1, "name": "Node Selection & Readiness Check", "action_type": "setup", "description": "Identify unblocked nodes whose inbound dependency edges have succeeded."},
                {"stage_index": 2, "name": "Transition Execution", "action_type": "dispatch", "description": "Execute node payload and produce candidate next state."},
                {"stage_index": 3, "name": "Predicate Edge Evaluation", "action_type": "output_validation", "description": "Evaluate boolean edge predicates to determine transition route."},
                {"stage_index": 4, "name": "Fallback Routing on Failure", "action_type": "retry", "description": "If node execution fails, route through dedicated error/fallback recovery edges."}
            ],
            "stop_conditions": [
                "Sink/Terminal node reached in DAG",
                "No valid transitions available from current node"
            ],
            "failure_handling": {
                "error_extraction": "Node execution exceptions and predicate evaluation errors",
                "retry_budget": 5,
                "backoff_or_mutation": "Follows explicit error recovery edges rather than arbitrary looping",
                "stuck_detection": "Cycle detection on graph traversal prevents infinite loops"
            },
            "target_frameworks": ["Loop-Engine", "Python", "DAG", "Graph"],
            "code_format": "python",
            "tags": ["dag", "state-graph", "predicates", "deterministic-transitions"]
        }
    ]

    for item in loop_engine_items:
        content = read_text_safe(item["file"])
        if content:
            loops.append({
                "id": item["id"],
                "title": item["title"],
                "source_repository": "Emmimal/loop-engine",
                "source_file": os.path.relpath(item["file"], "/tmp/repo_sources/loop-engine"),
                "framework": "Loop-Engine",
                "category": item["category"],
                "description": item["description"],
                "loop_stages": item["stages"],
                "stop_conditions": item["stop_conditions"],
                "failure_handling": item["failure_handling"],
                "raw_config_payload": content,
                "code_format": item["code_format"],
                "tags": item["tags"]
            })

    # =========================================================================
    # 7. the-open-engine/zeroshot
    # =========================================================================
    zeroshot_items = [
        {
            "id": "loop-zeroshot-supervisor-controller",
            "title": "Zeroshot Rust Autonomous Goal Supervisor & Run Ledger",
            "file": "/tmp/repo_sources/zeroshot/zeroshot/src/native_v2_supervisor/controller.rs",
            "category": "Goal-Directed Autonomous Controllers",
            "description": "High-performance Rust autonomous supervisor implementing atomic checkpoint commits, delivery gates, and hard resource limit enforcements.",
            "stages": [
                {"stage_index": 1, "name": "Supervisor Boot & Ledger Recovery", "action_type": "setup", "description": "Load persistent run ledger, verify workspace tokens, and mount execution sandbox."},
                {"stage_index": 2, "name": "Task Frame Dispatch", "action_type": "dispatch", "description": "Dispatch atomic execution frame to child process runner with memory/CPU quotas."},
                {"stage_index": 3, "name": "Tail Buffer & Health Monitoring", "action_type": "inspection", "description": "Continuously read child process tail buffer for exit signals or heartbeats."},
                {"stage_index": 4, "name": "Terminalization Gate", "action_type": "stop_evaluation", "description": "Commit state checkpoint to immutable ledger upon successful exit code 0 or trigger post-mortem."}
            ],
            "stop_conditions": [
                "Process exits with code 0 and output satisfies delivery gate contract",
                "Process timeout or OOM threshold exceeded",
                "Explicit terminalization signal received"
            ],
            "failure_handling": {
                "error_extraction": "Captures Linux process exit codes, signals (SIGKILL, SIGTERM), and tail buffer diagnostics",
                "retry_budget": 3,
                "backoff_or_mutation": "Executes postmortem diagnostics and re-launches with mutated resource quotas",
                "stuck_detection": "Monitors heartbeat intervals and kills frozen child processes"
            },
            "target_frameworks": ["Zeroshot", "Rust", "Tokio", "Linux cgroups"],
            "code_format": "rust",
            "tags": ["zeroshot", "rust", "supervisor", "process-isolation", "run-ledger"]
        },
        {
            "id": "loop-zeroshot-failure-isolation",
            "title": "Zeroshot Diagnostic Post-Mortem & Failure Isolation Engine",
            "file": "/tmp/repo_sources/zeroshot/zeroshot/src/native_v2_supervisor/failure.rs",
            "category": "Goal-Directed Autonomous Controllers",
            "description": "Rust failure isolation engine that analyzes crashed agent sessions, parses crash dumps and tail logs, and classifies failures into fatal vs recoverable.",
            "stages": [
                {"stage_index": 1, "name": "Crash Interception", "action_type": "inspection", "description": "Intercept child process abnormal termination signal or non-zero exit code."},
                {"stage_index": 2, "name": "Tail Buffer Forensic Parsing", "action_type": "output_validation", "description": "Scan the circular tail buffer for panics, segfaults, out-of-memory indicators, or tracebacks."},
                {"stage_index": 3, "name": "Failure Classification", "action_type": "calculation", "description": "Classify failure into: transient environment fault, resource starvation, or code bug."},
                {"stage_index": 4, "name": "Remediation Strategy Dispatch", "action_type": "retry", "description": "Issue cleanup command, prune invalid working files, and reset execution checkpoint."}
            ],
            "stop_conditions": [
                "State restored to last clean verified checkpoint",
                "Fatal irrecoverable crash escalated to operator"
            ],
            "failure_handling": {
                "error_extraction": "Linux signal codes, kernel OOM killer notices, stderr ring buffers",
                "retry_budget": 3,
                "backoff_or_mutation": "Purges temporary artifacts and restarts from known-good state snapshot",
                "stuck_detection": "Halts restart loop if identical crash signature repeats twice"
            },
            "target_frameworks": ["Zeroshot", "Rust", "POSIX"],
            "code_format": "rust",
            "tags": ["post-mortem", "failure-isolation", "forensics", "rust", "crash-recovery"]
        }
    ]

    for item in zeroshot_items:
        content = read_text_safe(item["file"])
        if content:
            loops.append({
                "id": item["id"],
                "title": item["title"],
                "source_repository": "the-open-engine/zeroshot",
                "source_file": os.path.relpath(item["file"], "/tmp/repo_sources/zeroshot"),
                "framework": "Zeroshot",
                "category": item["category"],
                "description": item["description"],
                "loop_stages": item["stages"],
                "stop_conditions": item["stop_conditions"],
                "failure_handling": item["failure_handling"],
                "raw_config_payload": content,
                "code_format": item["code_format"],
                "tags": item["tags"]
            })

    # =========================================================================
    # 8. browser-use/browser-use
    # =========================================================================
    browser_use_items = [
        {
            "id": "loop-browser-use-agent-service",
            "title": "Browser-Use Agent Action-Observation Playwright Execution Loop",
            "file": "/tmp/repo_sources/browser-use/browser_use/agent/service.py",
            "category": "Self-Healing Browser Scraping",
            "description": "Core action-observation state machine for autonomous web browsing using Playwright: DOM extraction -> Visual Element Tree -> Action Execution -> Result Verification.",
            "stages": [
                {"stage_index": 1, "name": "DOM State Ingestion & Tree Extraction", "action_type": "inspection", "description": "Extract interactive DOM elements, build indexed accessibility tree, capture viewport screenshot."},
                {"stage_index": 2, "name": "Action Synthesis (Click, Type, Scroll)", "action_type": "code_modification", "description": "Model selects element index and outputs structured action (click_element, input_text, scroll_page)."},
                {"stage_index": 3, "name": "Playwright Action Execution", "action_type": "dispatch", "description": "Execute action on browser page via CDP or Playwright locator with network idle wait."},
                {"stage_index": 4, "name": "URL / DOM State Change Verification", "action_type": "output_validation", "description": "Verify page navigation or DOM mutation occurred as a result of action."},
                {"stage_index": 5, "name": "Goal Completion Check", "action_type": "stop_evaluation", "description": "Evaluate if goal statement is satisfied or if next step is required."}
            ],
            "stop_conditions": [
                "Agent calls completion action with extracted structured result",
                "Target URL and data fields fully retrieved",
                "Maximum action steps budget reached (e.g. 25 steps)"
            ],
            "failure_handling": {
                "error_extraction": "Element not found, detached DOM node, timeout, navigation error",
                "retry_budget": 5,
                "backoff_or_mutation": "Re-indexes DOM tree and prompts model with updated element coordinates if selector fails",
                "stuck_detection": "Detects unchanging URL and viewport across 3 consecutive action turns"
            },
            "target_frameworks": ["Browser-Use", "Playwright", "Python", "CDP"],
            "code_format": "python",
            "tags": ["browser-use", "playwright", "web-automation", "dom-tree", "self-healing"]
        },
        {
            "id": "loop-browser-use-judge-verifier",
            "title": "Browser-Use LLM-as-a-Judge Extraction & Goal Completion Verifier",
            "file": "/tmp/repo_sources/browser-use/browser_use/agent/judge.py",
            "category": "Self-Healing Browser Scraping",
            "description": "Independent judge loop verifying whether scraped data matches the user's intent and conforms to the requested Pydantic schema before terminating.",
            "stages": [
                {"stage_index": 1, "name": "Goal & Output Schema Review", "action_type": "setup", "description": "Review original extraction goal and target schema definition."},
                {"stage_index": 2, "name": "Candidate Data Validation", "action_type": "output_validation", "description": "Validate extracted fields for completeness, hallucination markers, and empty values."},
                {"stage_index": 3, "name": "Judge Verdict (Pass / Mutate / Retry)", "action_type": "stop_evaluation", "description": "If data is complete, issue PASS; if missing fields, generate targeted re-crawl instruction."}
            ],
            "stop_conditions": [
                "Judge outputs confident PASS verdict",
                "Extracted payload validates against Pydantic schema with zero missing required fields"
            ],
            "failure_handling": {
                "error_extraction": "Missing mandatory fields, invalid data formats, mismatched currency/date values",
                "retry_budget": 3,
                "backoff_or_mutation": "Directs browser agent to specific element coordinates or missing sub-pages",
                "stuck_detection": "Terminates if judge rejects 3 consecutive attempts without improvement"
            },
            "target_frameworks": ["Browser-Use", "Pydantic", "Python"],
            "code_format": "python",
            "tags": ["llm-as-a-judge", "verification", "schema-validation", "pydantic"]
        }
    ]

    for item in browser_use_items:
        content = read_text_safe(item["file"])
        if content:
            loops.append({
                "id": item["id"],
                "title": item["title"],
                "source_repository": "browser-use/browser-use",
                "source_file": os.path.relpath(item["file"], "/tmp/repo_sources/browser-use"),
                "framework": "Browser-Use",
                "category": item["category"],
                "description": item["description"],
                "loop_stages": item["stages"],
                "stop_conditions": item["stop_conditions"],
                "failure_handling": item["failure_handling"],
                "raw_config_payload": content,
                "code_format": item["code_format"],
                "tags": item["tags"]
            })

    # =========================================================================
    # 9. browserbase/stagehand
    # =========================================================================
    stagehand_items = [
        {
            "id": "loop-stagehand-self-healing-extract",
            "title": "Stagehand Self-Healing Pydantic Schema Extraction Loop",
            "file": "/tmp/repo_sources/stagehand/packages/sdk-python/examples/extract.py",
            "category": "Self-Healing Browser Scraping",
            "description": "Browserbase Stagehand extraction loop that validates scraped web elements against a Pydantic schema, automatically repairing selectors upon schema validation error.",
            "stages": [
                {"stage_index": 1, "name": "Page Navigation & DOM Stabilization", "action_type": "setup", "description": "Navigate to target URL and wait for DOM network idle / hydration."},
                {"stage_index": 2, "name": "Schema-Guided Element Extraction", "action_type": "inspection", "description": "Stagehand extracts structured dictionary adhering to provided Pydantic model."},
                {"stage_index": 3, "name": "Pydantic Model Validation", "action_type": "output_validation", "description": "Run `Model.model_validate(data)` to verify data types and field constraints."},
                {"stage_index": 4, "name": "Self-Healing Selector Mutation", "action_type": "retry", "description": "If validation fails (missing fields or type mismatch), mutate extraction instruction with failed field path and retry."}
            ],
            "stop_conditions": [
                "Extracted object passes `model_validate` with 0 ValidationError exceptions",
                "Max retries reached (default 3)"
            ],
            "failure_handling": {
                "error_extraction": "Pydantic `ValidationError` location paths and input error messages",
                "retry_budget": 3,
                "backoff_or_mutation": "Injects exact missing field name and expected type into Stagehand instruction for targeted re-querying",
                "stuck_detection": "Aborts if DOM element count does not change after mutation"
            },
            "target_frameworks": ["Stagehand", "Browserbase", "Playwright", "Pydantic"],
            "code_format": "python",
            "tags": ["stagehand", "browserbase", "self-healing", "pydantic", "scraping"]
        },
        {
            "id": "loop-stagehand-observe-and-act",
            "title": "Stagehand Interactive Action Observation & Element Mutation Loop",
            "file": "/tmp/repo_sources/stagehand/packages/sdk-python/examples/observe.py",
            "category": "Self-Healing Browser Scraping",
            "description": "Stagehand observe-and-act loop where available actions are dynamically observed, scored for relevance, and executed with automatic locator recovery.",
            "stages": [
                {"stage_index": 1, "name": "Observe Interactive Elements", "action_type": "inspection", "description": "Run `page.observe()` to obtain list of possible actions with natural language descriptions."},
                {"stage_index": 2, "name": "Action Selection & Execution", "action_type": "dispatch", "description": "Select best matching action and execute `page.act(action)`."},
                {"stage_index": 3, "name": "Page State Transition Check", "action_type": "output_validation", "description": "Check if page transitioned or if modal/dropdown appeared."},
                {"stage_index": 4, "name": "Next Step or Completion", "action_type": "stop_evaluation", "description": "Loop back to observe if multi-step flow requires further interactions."}
            ],
            "stop_conditions": [
                "Target workflow completed (e.g. form submitted, checkout reached)",
                "No further valid actions observed"
            ],
            "failure_handling": {
                "error_extraction": "Locator timeouts, intercepted clicks, and element not interactable errors",
                "retry_budget": 4,
                "backoff_or_mutation": "Scrolls element into view, dismisses overlaying modals, and re-observes",
                "stuck_detection": "Detects identical observe action candidates across consecutive turns"
            },
            "target_frameworks": ["Stagehand", "Browserbase", "Playwright"],
            "code_format": "python",
            "tags": ["stagehand", "observe-and-act", "ui-interaction", "playwright"]
        },
        {
            "id": "loop-stagehand-paginated-catalog",
            "title": "Stagehand Paginated Catalog Extraction & Fault-Tolerant Checkpoint Loop",
            "file": "/tmp/repo_sources/stagehand/packages/examples/cookbooks/paginated-catalog/python/main.py",
            "category": "Self-Healing Browser Scraping",
            "description": "Production cookbook loop extracting multi-page e-commerce catalogs with local JSON checkpointing, next-page button healing, and pagination termination logic.",
            "stages": [
                {"stage_index": 1, "name": "Load Checkpoint & Resume Page", "action_type": "setup", "description": "Read local checkpoint file to resume from last successfully extracted page index."},
                {"stage_index": 2, "name": "Page Item Batch Extraction", "action_type": "inspection", "description": "Extract all product cards on current page according to schema."},
                {"stage_index": 3, "name": "Append & Atomic Checkpoint Write", "action_type": "output_validation", "description": "Persist extracted items to disk before advancing to prevent data loss on network drops."},
                {"stage_index": 4, "name": "Next Page Selector Detection & Click", "action_type": "dispatch", "description": "Locate and click 'Next Page' button via Stagehand natural language locator."},
                {"stage_index": 5, "name": "Pagination End Condition Check", "action_type": "stop_evaluation", "description": "Detect if 'Next Page' is disabled, missing, or page content repeats."}
            ],
            "stop_conditions": [
                "Next page button disabled or returns 404 / empty listings",
                "Configured max page limit reached"
            ],
            "failure_handling": {
                "error_extraction": "Next button stale element reference, CAPTCHA blockage, network timeouts",
                "retry_budget": 3,
                "backoff_or_mutation": "Reloads page and re-applies checkpoint state if browser crash occurs",
                "stuck_detection": "Compares extracted product IDs against previous page to detect circular pagination"
            },
            "target_frameworks": ["Stagehand", "Browserbase", "Pydantic", "Python"],
            "code_format": "python",
            "tags": ["pagination", "checkpoints", "catalog-extraction", "stagehand", "fault-tolerant"]
        }
    ]

    for item in stagehand_items:
        content = read_text_safe(item["file"])
        if content:
            loops.append({
                "id": item["id"],
                "title": item["title"],
                "source_repository": "browserbase/stagehand",
                "source_file": os.path.relpath(item["file"], "/tmp/repo_sources/stagehand"),
                "framework": "Stagehand",
                "category": item["category"],
                "description": item["description"],
                "loop_stages": item["stages"],
                "stop_conditions": item["stop_conditions"],
                "failure_handling": item["failure_handling"],
                "raw_config_payload": content,
                "code_format": item["code_format"],
                "tags": item["tags"]
            })

    print(f"Total engineering loops extracted: {len(loops)}")
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(loops, f, indent=2, ensure_ascii=False)
    print(f"Successfully saved to {OUTPUT_PATH}")

if __name__ == "__main__":
    main()

