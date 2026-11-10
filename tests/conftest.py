"""Rend les modules de test importables entre eux (ex : FakeGarmin)."""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
