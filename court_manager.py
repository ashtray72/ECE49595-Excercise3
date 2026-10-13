"""
court_manager.py
Turns Places search results into Court objects and keeps track of their state:
  - which courts are in use (max 3 at a time)
  - which court this user has selected (only one at a time)
State is saved to a local JSON file so it survives restarting the app.
Later, the JSON load/save can be swapped for calls to our backend API.
"""

import json
import os
from dataclasses import dataclass, asdict, fields

DEFAULT_STATE_FILE = "courts_state.json"


@dataclass
class Court:
    id: str            # Google place ID (stable across searches)
    name: str
    lat: float
    lon: float
    sport: str
    in_use: bool = False


class SelectionError(Exception):
    """Raised when a court can't be selected; the message is shown to the user."""


class CourtManager:
    def __init__(self, state_file=DEFAULT_STATE_FILE, max_in_use=3):
        self.state_file = state_file
        self.max_in_use = max_in_use
        self.courts = {}          # court id -> Court
        self.selected_id = None   # id of the court this user has selected
        self.load()

    # ---------- Queries ----------

    @property
    def in_use_count(self):
        return sum(1 for c in self.courts.values() if c.in_use)

    @property
    def selected_court(self):
        return self.courts.get(self.selected_id)

    def is_selected(self, court_id):
        return court_id == self.selected_id

    def status(self, court_id):
        """'selected', 'in_use', or 'free' (used by the GUI to pick marker colors)."""
        if self.is_selected(court_id):
            return "selected"
        if self.courts[court_id].in_use:
            return "in_use"
        return "free"

    # ---------- Updating from search results ----------

    def merge_results(self, results, sport):
        """
        Adds new search results without overwriting what we already know.
        `results` is the list of dicts from places_client.search_courts().
        Returns the Court objects for this search, in the same order.
        """
        merged = []
        for r in results:
            court = self.courts.get(r["id"])
            if court is None:
                # New court: starts out free
                court = Court(id=r["id"], name=r["name"], lat=r["lat"], lon=r["lon"], sport=sport)
                self.courts[court.id] = court
            else:
                # Known court: refresh details from Google, but keep its in_use status
                court.name, court.lat, court.lon = r["name"], r["lat"], r["lon"]
            merged.append(court)
        self.save()
        return merged

    # ---------- Selection rules ----------

    def select(self, court_id):
        """
        Selects a court for this user (and marks it in use).
        Rules:
          1. A court someone else is using can't be selected.
          2. A user can only hold one court; selecting a new one releases the old one.
          3. No more than `max_in_use` courts can be in use at once.
        Raises SelectionError with a user-facing message if a rule is broken.
        """
        court = self.courts.get(court_id)
        if court is None:
            raise SelectionError("That court is no longer available. Try loading courts again.")

        if self.is_selected(court_id):
            return court  # already ours, nothing to do

        if court.in_use:
            raise SelectionError(f"'{court.name}' is currently in use.")

        # Switching courts frees up the old one, so it doesn't count toward the limit
        in_use_after_release = self.in_use_count - (1 if self.selected_court else 0)
        if in_use_after_release >= self.max_in_use:
            raise SelectionError(
                f"The maximum of {self.max_in_use} courts in use has been reached."
            )

        self.release()          # rule 2: drop any previous selection
        court.in_use = True
        self.selected_id = court_id
        self.save()
        return court

    def release(self):
        """Releases this user's current court, if any."""
        if self.selected_court:
            self.selected_court.in_use = False
        self.selected_id = None
        self.save()

    # ---------- Saving / loading ----------

    def save(self):
        data = {
            "selected_id": self.selected_id,
            "courts": [asdict(c) for c in self.courts.values()],
        }
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def load(self):
        """Loads saved state. A missing or corrupted file just means starting fresh."""
        if not os.path.exists(self.state_file):
            return
        try:
            with open(self.state_file, encoding="utf-8") as f:
                data = json.load(f)
            allowed = {fld.name for fld in fields(Court)}
            self.courts = {
                c["id"]: Court(**{k: v for k, v in c.items() if k in allowed})
                for c in data.get("courts", [])
            }
            sel = data.get("selected_id")
            self.selected_id = sel if sel in self.courts else None
        except (json.JSONDecodeError, KeyError, TypeError):
            print(f"Warning: could not read {self.state_file}, starting with no saved courts.")
            self.courts, self.selected_id = {}, None
