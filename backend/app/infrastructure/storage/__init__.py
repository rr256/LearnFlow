"""Adapters that keep bytes on a local filesystem.

Distinct from `persistence`, which adapts the database, and from `providers`,
which talks to services over a network. This package is the **only** place in the
backend that touches a filesystem.
"""
