import argparse


def main(argv=None):
    parser = argparse.ArgumentParser(description="Hr\u00f6nir Encyclopedia CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    def _placeholder_handler(name):
        def handler(args):
            print(f"{name} command is in development.")
        return handler

    for cmd in ["synthesize", "validate", "submit", "tree", "ranking", "export"]:
        sub = subparsers.add_parser(cmd, help="in development")
        sub.set_defaults(func=_placeholder_handler(cmd))

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()

