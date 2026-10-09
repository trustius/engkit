import sys

from textkit.slugify import slugify


def main(argv):
    print(slugify(" ".join(argv)))


if __name__ == "__main__":
    main(sys.argv[1:])
