# Presence of this conftest at the repository root makes pytest insert the
# root onto sys.path during collection (default "prepend" import mode), so the
# top-level maybot_agent / maybot_control_center packages import correctly under
# a bare `pytest` invocation (as CI runs it), not just `python -m pytest`.
