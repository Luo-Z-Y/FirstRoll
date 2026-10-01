# tools/release — sealed single-server (VPS) release control for FirstRoll.
#
# This package provides:
#   protocol       — dependency-free receipt primitives (hashing, inventory, outputs)
#   vps            — seal, verify and live-check the single-server release
#
# The deploy job fetches only protocol.py and vps.py from the CI-approved commit, so
# neither module may rely on initialisation in this file.
