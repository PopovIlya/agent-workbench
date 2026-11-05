import sys

from . import server

if len(sys.argv) > 1 and sys.argv[1] == "compare":
    from . import compare_cli

    sys.exit(compare_cli.main(sys.argv[2:]))
server.main()
