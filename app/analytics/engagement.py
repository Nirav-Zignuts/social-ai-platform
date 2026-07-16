"""Shared engagement metric helpers for analytics."""

from __future__ import annotations


def engagement_numerator(
    *,
    likes: int | None,
    comments: int | None,
    saves: int | None,
    shares: int | None,
) -> int:
    return sum(x or 0 for x in (likes, comments, saves, shares))


def calculate_engagement_rate(
    *,
    likes: int | None,
    comments: int | None,
    saves: int | None,
    shares: int | None,
    reach: int | None,
) -> float | None:
    """
    (likes + comments + saves + shares) / reach, expressed as a percentage.

    Returns None when reach is missing or zero.
    """
    if reach is None or reach <= 0:
        return None
    return round(engagement_numerator(
        likes=likes,
        comments=comments,
        saves=saves,
        shares=shares,
    ) / reach * 100, 2)
