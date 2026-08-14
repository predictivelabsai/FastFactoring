"""Compatibility entrypoint for the checked-in FastSME locale workflow.

Use ``python -m scripts.update_i18n`` to validate catalogues or add
``--translate`` during explicit translation maintenance.
"""

from scripts.update_i18n import main


if __name__ == "__main__":
    raise SystemExit(main())
