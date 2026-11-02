"""Round-robin fixture generation (circle method), idempotent by design.

Rules implemented here:
* N players -> N-1 rounds per leg; an odd N gets a virtual BYE so one player
  rests each round and no match is created for the bye.
* Circle method guarantees every pair meets exactly once per leg and nobody
  plays twice in the same round.
* The return leg replays the same pairings with home/away reversed and rounds
  numbered sequentially after the first leg.
* Home/away assignment alternates by (round, pairing) parity for balance.
* Generation is wrapped in a transaction that locks the league row. Existing
  fixtures short-circuit the operation; unique constraints are the backstop.
"""
from __future__ import annotations

import random
import secrets
from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from core.exceptions import AppError
from core.messages import MESSAGES

from ..models import League, Match, Round


@dataclass
class FixtureGenerationResult:
    created: bool
    rounds: int
    matches: int
    seed: int | None
    league: League

    def as_dict(self) -> dict:
        return {
            "created": self.created,
            "rounds": self.rounds,
            "matches": self.matches,
            "seed": self.seed,
            "legs": 2 if self.rounds else 0,
        }

    @property
    def code(self) -> str:
        return "FIXTURES_GENERATED" if self.created else "FIXTURES_ALREADY_GENERATED"

    @property
    def message(self) -> str:
        return MESSAGES[self.code]


def build_schedule(participant_ids: list[int], seed: int | None = None) -> list[list[tuple[int, int]]]:
    """Return one leg of a round-robin schedule using the circle method.

    Each round is a list of ``(home_id, away_id)`` pairs. The same seed always
    produces the same draw, which makes the lottery auditable.
    """
    ids = list(participant_ids)
    rng = random.Random(seed)
    rng.shuffle(ids)

    if len(ids) % 2 == 1:
        ids.append(None)  # virtual BYE

    n = len(ids)
    if n < 2:
        return []

    rotation = ids[:]
    rounds: list[list[tuple[int, int]]] = []

    for round_index in range(n - 1):
        pairs: list[tuple[int, int]] = []
        for pair_index in range(n // 2):
            first = rotation[pair_index]
            second = rotation[n - 1 - pair_index]
            if first is None or second is None:
                continue  # the BYE player rests this round
            home, away = first, second
            if (round_index + pair_index) % 2 == 1:
                home, away = away, home
            pairs.append((home, away))
        rounds.append(pairs)
        # Rotate every player except the first one, keeping the circle intact.
        rotation = [rotation[0], rotation[-1], *rotation[1:-1]]

    return rounds


def _validate_schedule(schedule: list[list[tuple[int, int]]]) -> None:
    for round_pairs in schedule:
        teams = [team for pair in round_pairs for team in pair]
        if len(teams) != len(set(teams)):
            raise AppError("FIXTURE_VALIDATION_FAILED", 500)


def _validate_persisted(league: League, expected_matches: int) -> None:
    """Double-check the invariant straight from the database."""
    for round_obj in league.rounds.all():
        teams = []
        for home_id, away_id in round_obj.matches.values_list("home_id", "away_id"):
            teams.extend([home_id, away_id])
        if len(teams) != len(set(teams)):
            raise AppError("FIXTURE_VALIDATION_FAILED", 500)

    total = Match.objects.filter(league=league).count()
    if total != expected_matches:
        raise AppError("FIXTURE_VALIDATION_FAILED", 500)


def _lock_league(league: League) -> League:
    return League.objects.select_for_update().get(pk=league.pk)


def _generate_locked(league: League, seed: int | None = None) -> FixtureGenerationResult:
    """Create fixtures assuming the league row is already locked."""
    existing_matches = Match.objects.filter(league=league).count()
    if existing_matches or league.fixtures_generated_at is not None:
        return FixtureGenerationResult(
            created=False,
            rounds=Round.objects.filter(league=league).count(),
            matches=existing_matches,
            seed=league.fixture_seed,
            league=league,
        )

    participants = list(league.participants.order_by("id"))
    if len(participants) < 2:
        raise AppError("NOT_ENOUGH_PLAYERS", 400)

    seed = seed if seed is not None else secrets.randbelow(2**31)
    schedule = build_schedule([p.id for p in participants], seed)
    _validate_schedule(schedule)

    matches_created = 0
    rounds_per_leg = len(schedule)
    for leg in (1, 2):
        for index, pairs in enumerate(schedule, start=1):
            number = index if leg == 1 else rounds_per_leg + index
            round_obj, _ = Round.objects.get_or_create(
                league=league, number=number, defaults={"leg": leg}
            )
            if round_obj.leg != leg:
                round_obj.leg = leg
                round_obj.save(update_fields=["leg"])

            matches = []
            for home_id, away_id in pairs:
                if leg == 2:
                    home_id, away_id = away_id, home_id
                matches.append(
                    Match(
                        league=league,
                        round=round_obj,
                        leg=leg,
                        home_id=home_id,
                        away_id=away_id,
                        status=Match.Status.SCHEDULED,
                    )
                )
            Match.objects.bulk_create(matches, ignore_conflicts=True)
            matches_created += len(matches)

    expected = len(participants) * (len(participants) - 1)
    _validate_persisted(league, expected)

    league.fixtures_generated_at = timezone.now()
    league.fixture_seed = seed
    league.status = League.Status.IN_PROGRESS
    league.save(
        update_fields=["fixtures_generated_at", "fixture_seed", "status", "updated_at"]
    )

    return FixtureGenerationResult(
        created=True,
        rounds=Round.objects.filter(league=league).count(),
        matches=Match.objects.filter(league=league).count(),
        seed=seed,
        league=league,
    )


def generate_fixtures(league: League, seed: int | None = None) -> FixtureGenerationResult:
    """Idempotent fixture generation.

    Safe under double clicks, retries and concurrent requests: the league row
    is locked and an existing fixture set is returned untouched.
    """
    with transaction.atomic():
        locked = _lock_league(league)
        return _generate_locked(locked, seed=seed)


def reset_and_regenerate(league: League, seed: int | None = None) -> FixtureGenerationResult:
    """Delete and rebuild fixtures, only when no result has been registered."""
    with transaction.atomic():
        locked = _lock_league(league)

        has_results = (
            Match.objects.filter(league=locked)
            .exclude(home_goals__isnull=True, away_goals__isnull=True)
            .exists()
            or Match.objects.filter(
                league=locked,
                status__in=[Match.Status.FINISHED, Match.Status.CONTESTED],
            ).exists()
        )
        if has_results:
            raise AppError("CANNOT_REGENERATE", 409)

        Match.objects.filter(league=locked).delete()
        Round.objects.filter(league=locked).delete()
        locked.fixtures_generated_at = None
        locked.fixture_seed = None
        locked.save(update_fields=["fixtures_generated_at", "fixture_seed", "updated_at"])

        return _generate_locked(locked, seed=seed)
