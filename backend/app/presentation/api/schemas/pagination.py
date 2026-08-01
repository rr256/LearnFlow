"""The pagination block collection responses carry.

`limit` and `offset` are the MVP pagination convention in
docs/api/conventions.md. The block reports the window that was applied together
with the total, so a client can tell a complete collection from a truncated one
without guessing from the number of items it received.
"""

from pydantic import BaseModel, Field

DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100


class Pagination(BaseModel):
    """The window applied to a collection, and how much there is in total."""

    limit: int = Field(description="Maximum number of items this response may contain.")
    offset: int = Field(description="Number of items skipped before this page.")
    total: int = Field(description="Total number of items available, ignoring the window.")
