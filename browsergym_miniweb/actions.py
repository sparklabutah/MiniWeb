"""Custom BrowserGym actions for MiniWeb.

`report_answer` is the agent's dedicated channel for its FINAL answer -- the value
the task asked for -- as opposed to `send_msg_to_user`, which stays for ordinary
progress notes. Separating them means grading reads the deliverable directly (not
guessing which chat line was the answer), and the call is a clean "I'm done"
signal for the episode.

BrowserGym includes a custom action by inspecting its SOURCE and exec'ing it in a
context where `send_message_to_user` (and `page`, etc.) are defined -- so the body
may reference those names freely, and must NOT depend on module-level names here
(they aren't in scope at exec time). Keep the marker literal inline; task.py uses
the same string via FINAL_ANSWER_PREFIX.

The docstring is parsed by BrowserGym's strict action-docstring grammar (a plain
one-line description, then an `Examples:` block) -- keep it ASCII and in that shape.
"""

# The marker task.py looks for. Kept in sync with the literal inside report_answer.
FINAL_ANSWER_PREFIX = "[FINAL ANSWER]"


def report_answer(answer: str):
    """
    Reports your FINAL answer to the task and ends the task. Call this exactly once, only after you have completed everything the task asks for and are confident in the answer. For progress notes or anything that is not the final answer, use send_msg_to_user instead.

    Examples:
        report_answer("Geralt of Rivia")
        report_answer("0")
        report_answer("Yes, it exists.")
    """
    send_message_to_user("[FINAL ANSWER] " + str(answer))
