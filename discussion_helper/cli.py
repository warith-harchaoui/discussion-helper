"""
The argparse command line — ``discussion-helper-argparse``.

Module summary
--------------
Two commands, and the second one is why this file is worth reading.

``talk`` opens the microphone and holds a conversation. ``rehearse`` holds the
same conversation with the microphone, the model and the sound card replaced
by fakes — the same loop, the same floor handling, the same interruption
logic, running in a second with nothing installed. It is how you check that
*this package* works before deciding whether the room does.

That distinction matters more than it looks. When a voice agent misbehaves,
the first question is always "is it the loop or is it the hardware", and
without something like ``rehearse`` the only way to ask it is to change one
thing and listen again.

Author
------
Warith HARCHAOUI — https://linkedin.com/in/warith-harchaoui
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from discussion_helper.discussion import Discussion, Policy
from discussion_helper.types import Conversation


def build_parser() -> argparse.ArgumentParser:
    """The parser, built separately so a test can read it without running it."""
    parser = argparse.ArgumentParser(
        prog="discussion-helper",
        description=(
            "Hold a spoken conversation: listen, answer, speak — and stop the "
            "moment the user cuts in."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  discussion-helper rehearse 'bonjour' 'ça va ?'   # no hardware\n"
            "  discussion-helper talk --voice ff_siwis\n"
            "  discussion-helper talk --no-barge-in             # strict half-duplex\n"
            "\n"
            "KNOWLEDGE.md explains the latency budget, turn detection and why\n"
            "echo decides your defaults.\n"
        ),
    )
    parser.add_argument("-V", "--version", action="version", version=_version_string())
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--no-barge-in",
        action="store_true",
        help="Strict half-duplex: the user may not interrupt. Correct on a "
        "speakerphone, where every reply would otherwise interrupt itself.",
    )
    common.add_argument(
        "--grace",
        type=float,
        default=0.35,
        metavar="SECONDS",
        help="How long after the agent starts speaking before an interruption "
        "is believed (default: %(default)s). Absorbs the agent's own voice "
        "when there is no echo cancellation.",
    )
    common.add_argument(
        "--max-sentences",
        type=int,
        default=0,
        help="Cap on reply length. 0 means no cap.",
    )
    common.add_argument(
        "--json",
        action="store_true",
        help="Write the transcript and the latency breakdown as JSON.",
    )

    p_talk = sub.add_parser("talk", parents=[common], help="Hold a conversation at the microphone.")
    p_talk.add_argument("--voice", default="", help="Voice to read with.")
    p_talk.add_argument("--language", default="", help="Language hint.")
    p_talk.add_argument("--device", default=None, help="Microphone name substring.")
    p_talk.add_argument(
        "--silence-timeout",
        type=float,
        default=30.0,
        metavar="SECONDS",
        help="Give up after this much silence (default: %(default)s). An open "
        "microphone in an empty room is an ordinary ending.",
    )

    p_rehearse = sub.add_parser(
        "rehearse",
        parents=[common],
        help="Run the same loop with fake parts — no microphone, model or speaker.",
    )
    p_rehearse.add_argument("turns", nargs="*", default=["bonjour"], help="What the user says.")
    p_rehearse.add_argument(
        "--interrupt-after",
        type=float,
        default=None,
        metavar="SECONDS",
        help="Stage a barge-in this long into the agent's reply.",
    )
    p_rehearse.add_argument(
        "--sentences", type=int, default=3, help="How long the fake reply runs."
    )
    return parser


def _version_string() -> str:
    from discussion_helper import __version__

    return f"%(prog)s {__version__}"


def _policy(args: argparse.Namespace) -> Policy:
    """The policy the flags describe."""
    return Policy(
        allow_barge_in=not args.no_barge_in,
        barge_in_grace_s=args.grace,
        max_reply_sentences=args.max_sentences,
        silence_timeout_s=getattr(args, "silence_timeout", 0.0),
    )


def _report(conversation: Conversation, as_json: bool) -> None:
    """Print the transcript, and where the latency went.

    The breakdown is printed even in the human-readable form, because a total
    says a conversation felt slow and nothing about which stage to fix.
    """
    if as_json:
        sys.stdout.write(
            json.dumps(
                {
                    "utterances": [
                        {
                            "speaker": u.speaker,
                            "text": u.text,
                            "interrupted": u.interrupted,
                        }
                        for u in conversation.utterances
                    ],
                    "timings": [t.as_dict() for t in conversation.timings],
                    "interruption_rate": round(conversation.interruption_rate, 3),
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n"
        )
        return

    for utterance in conversation.utterances:
        mark = " (cut off)" if utterance.interrupted else ""
        who = "you" if utterance.speaker == "user" else "it"
        sys.stdout.write(f"{who:>4}: {utterance.text}{mark}\n")

    if conversation.timings:
        sys.stdout.write("\n")
        for index, timing in enumerate(conversation.timings, start=1):
            sys.stdout.write(
                f"turn {index}: {timing.to_first_audio_s * 1000:.0f} ms to first "
                f"audio, slowest stage {timing.slowest_stage}\n"
            )


def _cmd_rehearse(args: argparse.Namespace) -> int:
    """Hold the conversation with fake parts."""
    from discussion_helper.testing import EchoResponder, ScriptedListener, SilentVoice

    talk = Discussion(
        ScriptedListener(args.turns, interrupt_after_s=args.interrupt_after),
        EchoResponder(sentences=args.sentences),
        SilentVoice(seconds_per_sentence=0.2),
        _policy(args),
    )
    _report(asyncio.run(talk.run()), args.json)
    return 0


def _cmd_talk(args: argparse.Namespace) -> int:
    """Hold the conversation at the microphone."""
    from discussion_helper.adapters import LocalResponder, SpeakerVoice, VocalListener

    async def run() -> Conversation:
        async with Discussion(
            VocalListener(language=args.language, device_name=args.device),
            LocalResponder(),
            SpeakerVoice(voice=args.voice, language=args.language),
            _policy(args),
        ) as talk:
            return await talk.run()

    try:
        conversation = asyncio.run(run())
    except RuntimeError as exc:
        # The adapters raise this with the install line for the half that is
        # missing, which is more use than a traceback about a module the
        # reader has never imported.
        sys.stderr.write(f"{exc}\n")
        return 1
    except KeyboardInterrupt:
        sys.stderr.write("\n")
        return 0
    _report(conversation, args.json)
    return 0


def main(argv: list[str] | None = None) -> int:
    """Dispatch to one of the two commands."""
    import os_helper as osh

    osh.init_logging()
    args = build_parser().parse_args(argv)
    if args.command == "rehearse":
        return _cmd_rehearse(args)
    if args.command == "talk":
        return _cmd_talk(args)
    return 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
