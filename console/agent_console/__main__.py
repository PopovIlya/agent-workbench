import sys

if len(sys.argv) > 1 and sys.argv[1] == "compare":
    from .compare import cli_main

    sys.exit(cli_main(sys.argv[2:]))
else:
    from .server import main

    main()
