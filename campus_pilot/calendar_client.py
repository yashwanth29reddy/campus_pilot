"""Write events to Google Calendar.

Creates timed or all-day events from the Qwen-extracted details, tagged
with the source Gmail message id so we can trace/maintain them.
"""

from __future__ import annotations

import datetime as dt

from googleapiclient.errors import HttpError