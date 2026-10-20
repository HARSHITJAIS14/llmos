import subprocess
import time

from arc_cua import (
    DesktopExecutor,
    Subtask,
)

from arc_cua.backends import (
    MacOSHybridBackend,
)

from arc_cua.policies import (
    TypeSafeJevPolicy,
)


# -------------------------
# 1. Open WhatsApp
# -------------------------

print("Opening WhatsApp...")

subprocess.run(
    [
        "open",
        "-a",
        "WhatsApp",
    ],
    check=True,
)

time.sleep(4)


# -------------------------
# 2. Set up arc_cua
# -------------------------

executor = DesktopExecutor(
    backend=MacOSHybridBackend(
        ocr_recognition_level="fast",
        ocr_min_confidence=0.45,
    ),
    policy=TypeSafeJevPolicy(),
)


# -------------------------
# 3. Agent-supplied subtask
# -------------------------

task = Subtask(
    goal=(
        "In WhatsApp, search for 'justharshitj', open the chat, "
        "and send the message 'this is from my project'."
    ),

    inputs={
        "search_query": "justharshitj",
        "message": "this is from my project",
    },

    verification=(
        "The chat with 'justharshitj' is open.",
        "The message 'this is from my project' has been sent in the chat.",
    ),

    constraints=(
        "Do not send the message to anyone else.",
        "Do not delete any existing messages.",
    ),

    max_actions=15,
)


# -------------------------
# 4. Run
# -------------------------

print("\nTask: text justharshitj on WhatsApp")
print("Starting arc_cua...\n")

result = executor.run(task)


# -------------------------
# 5. Trace
# -------------------------

print("\n==============================")
print("RESULT")
print("==============================")

print(
    "status:",
    result.status.value,
)

print(
    "actions:",
    result.actions_taken,
)

if result.reason:
    print(
        "reason:",
        result.reason,
    )


print("==============================")
print("TRACE")
print("==============================")
for step in result.history:
    print(step.compact())
