"""python -m miniwebgen <stage> ...   the generation pipeline (miniwebgen.pipeline; --help lists the stages)
python -m miniwebgen replay ...    kept trajectories replayed through the agent harness into training rows
                                   (miniwebgen.replay_cli)"""
import sys

if len(sys.argv) > 1 and sys.argv[1] == "replay":
    from miniwebgen.replay_cli import main
else:
    from miniwebgen.pipeline import main

main()
