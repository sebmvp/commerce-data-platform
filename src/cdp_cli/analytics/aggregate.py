"""Derive `insights.voice_profile` from content snapshots + listing outcomes.

A voice profile answers: "for this style of listing content (tone x hook
style), what engagement and conversion did it *actually* produce?" It is the
distilled, evidence-backed fact a copywriter works from — not vibes.

Profiles are versioned: each refresh closes `is_current` rows whose inputs
were superseded and writes a new version, keeping history auditable.
"""
from __future__ import annotations

import duckdb

MIN_SAMPLE = 2  # don't assert a profile off a single post


def refresh_voice_profiles(con: duckdb.DuckDBPyConnection) -> int:
    """Recompute current voice profiles. Returns number of new versions."""
    groups = con.execute(
        """
        SELECT
          c.tone,
          coalesce(nullif(string_split(c.cta, ' ')[1], ''), 'none') AS hook_style,
          coalesce(ch.channel_key, '')                     AS channel_key,
          count(DISTINCT c.caption_id)                    AS sample_size,
          avg(coalesce(s.saves, 0))                       AS avg_saves,
          avg(coalesce(s.inquiries, 0))                   AS avg_inquiries,
          avg(coalesce(s.conversions, 0))                 AS avg_conversions,
          avg(coalesce(s.engagement_rate, 0))             AS avg_er,
          min(s.observed_at)                              AS window_start,
          max(s.observed_at)                              AS window_end
        FROM insights.content_pieces c
        JOIN insights.content_snapshot s ON s.caption_id = c.caption_id
        LEFT JOIN core.channels ch ON ch.channel_key = c.channel_key
        WHERE c.status = 'published'
        GROUP BY c.tone, hook_style, coalesce(ch.channel_key, '')
        HAVING count(DISTINCT c.caption_id) >= ?
        """,
        [MIN_SAMPLE],
    ).fetchall()

    written = 0
    for (tone, hook_style, channel_key, sample, avg_saves, avg_inq,
         avg_conv, avg_er, w_start, w_end) in groups:
        # existing current version with identical rounded inputs -> skip
        existing = con.execute(
            """SELECT version, sample_size,
                      round(avg_watchers, 4), round(avg_conversion, 4)
               FROM insights.voice_profile
               WHERE content_type='listing_description' AND tone=?
                 AND hook_style=? AND coalesce(channel_key, '') = coalesce(?, '')
                 AND is_current""",
            [tone, hook_style, channel_key],
        ).fetchone()
        watchers = round(avg_saves + avg_inq, 4)
        conv = round(avg_conv, 4)
        if existing and existing[1] == sample and \
           round(existing[2] or 0, 4) == watchers and round(existing[3] or 0, 4) == conv:
            continue  # inputs unchanged — idempotent refresh

        if existing:
            con.execute(
                """UPDATE insights.voice_profile SET is_current=false
                   WHERE content_type='listing_description' AND tone=?
                     AND hook_style=? AND coalesce(channel_key,'')=coalesce(?, '')
                     AND is_current""",
                [tone, hook_style, channel_key],
            )
        version = (existing[0] + 1) if existing else 1
        summary = (
            f"**{tone}** / *{hook_style}* — over {sample} pieces, "
            f"avg {watchers:.1f} saves+inquiries and {conv:.2f} conversions "
            f"per piece (median-window engagement rate {avg_er:.3f})."
        )
        con.execute(
            """INSERT INTO insights.voice_profile
               (profile_id, content_type, tone, hook_style, channel_key,
                sample_size, avg_watchers, avg_conversion, summary_md,
                rules_json, version, is_current, source_window_start,
                source_window_end)
               VALUES (?, 'listing_description', ?, ?, ?, ?, ?, ?, ?, ?, ?, true, ?, ?)""",
            [f"vp_{tone}_{hook_style}_{(channel_key or 'any')}_{version}",
             tone, hook_style, channel_key, sample, watchers, conv, summary,
             '{"rule": "match tone+hook to evidence, not preference"}',
             version, w_start, w_end],
        )
        written += 1
    return written
