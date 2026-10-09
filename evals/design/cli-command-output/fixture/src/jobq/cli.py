import sys

HELP = """usage: jobq <command>

commands:
  run <name>      start a job
  cancel <id>     cancel a job
"""


def main(argv):
    if len(argv) < 2:
        print(HELP)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
