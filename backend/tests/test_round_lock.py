"""Sequential round lock: round N only opens after round N-1 is closed."""
import threading

import pytest
from django.db import connections
from rest_framework.test import APIClient

from core.messages import MESSAGES
from league.models import League, Match, Round

ROUND_LOCK_MESSAGE = MESSAGES["ROUND_NOT_OPEN"]


@pytest.fixture
def four_players(league, make_user, enroll):
    users = [
        make_user(f"p{i}@teste.com", f"Jogador {i}", f"Time {i}") for i in range(1, 5)
    ]
    enroll(users)
    return users


@pytest.fixture
def generated(league, four_players, api, admin):
    api.force_authenticate(admin)
    assert api.post("/api/admin/generate-fixtures/", {}, format="json").status_code == 200
    return league


def round_matches(league, number):
    return list(Round.objects.get(league=league, number=number).matches.order_by("id"))


def report(api, user, match, home_goals=1, away_goals=0):
    api.force_authenticate(user)
    return api.post(
        f"/api/matches/{match.pk}/result/",
        {"home_goals": home_goals, "away_goals": away_goals},
        format="json",
    )


def fill_round(api, admin, league, number):
    """Admin reports every pending match of the round."""
    for match in round_matches(league, number):
        response = report(api, admin, match, 2, 1)
        assert response.status_code == 200, response.json()


def states_by_number(api):
    rounds = api.get("/api/rounds/").json()
    return {round_data["number"]: round_data["state"] for round_data in rounds}


@pytest.mark.django_db
def test_first_round_is_open_and_the_next_one_is_locked(generated, api, admin):
    api.force_authenticate(admin)
    states = states_by_number(api)

    assert states[1] == "open"
    assert states[2] == "locked"
    assert all(state == "locked" for number, state in states.items() if number > 1)

    round_two_match = round_matches(generated, 2)[0]
    payload = api.get(f"/api/matches/{round_two_match.pk}/").json()
    assert payload["round_state"] == "locked"
    assert payload["permissions"]["round_locked"] is True
    assert payload["permissions"]["can_report"] is False


@pytest.mark.django_db
def test_result_in_a_locked_round_returns_round_not_open(generated, four_players, api, admin):
    alice = four_players[0]
    round_two_match = round_matches(generated, 2)[0]

    response = report(api, admin, round_two_match, 3, 0)
    assert response.status_code == 409
    assert response.json() == {
        "code": "ROUND_NOT_OPEN",
        "message": ROUND_LOCK_MESSAGE,
    }
    round_two_match.refresh_from_db()
    assert round_two_match.home_goals is None

    # The same rule applies to the players involved (checked before writing).
    if alice in (round_two_match.home.user, round_two_match.away.user):
        player_response = report(api, alice, round_two_match, 3, 0)
        assert player_response.status_code == 409
        assert player_response.json()["code"] == "ROUND_NOT_OPEN"


@pytest.mark.django_db
def test_round_opens_when_the_previous_one_is_closed(generated, api, admin):
    fill_round(api, admin, generated, 1)

    api.force_authenticate(admin)
    states = states_by_number(api)
    assert states[1] == "closed"
    assert states[2] == "open"
    assert states[3] == "locked"

    response = report(api, admin, round_matches(generated, 2)[0], 1, 0)
    assert response.status_code == 200
    assert response.json()["code"] == "RESULT_REPORTED"


@pytest.mark.django_db
def test_contested_matches_count_as_closed(generated, api, admin):
    round_one = round_matches(generated, 1)

    # A player reports the win; the opponent contests it.
    winner = round_one[0].home.user
    loser = round_one[0].away.user
    assert report(api, winner, round_one[0], 2, 0).status_code == 200

    api.force_authenticate(loser)
    contest = api.post(
        f"/api/matches/{round_one[0].pk}/contest/", {"reason": "placar errado"}, format="json"
    )
    assert contest.status_code == 200
    assert contest.json()["match"]["status"] == "CONTESTED"

    # Second match of the round is still pending, so round 2 stays locked.
    api.force_authenticate(admin)
    assert states_by_number(api)[2] == "locked"
    assert report(api, admin, round_matches(generated, 2)[0], 1, 0).status_code == 409

    # Closing the remaining match of round 1 opens round 2, even contested.
    assert report(api, admin, round_one[1], 1, 0).status_code == 200
    assert states_by_number(api)[2] == "open"
    assert report(api, admin, round_matches(generated, 2)[0], 1, 0).status_code == 200


@pytest.mark.django_db
def test_round_with_a_bye_still_closes(league, players, api, admin):
    """Three players: one rests each round and the bye never blocks anything."""
    api.force_authenticate(admin)
    assert api.post("/api/admin/generate-fixtures/", {}, format="json").status_code == 200

    round_one = round_matches(league, 1)
    assert len(round_one) == 1  # odd league: one match per round, one player rests
    assert states_by_number(api)[2] == "locked"

    assert report(api, admin, round_one[0], 1, 0).status_code == 200
    assert states_by_number(api)[1] == "closed"
    assert states_by_number(api)[2] == "open"


@pytest.mark.django_db
def test_second_leg_waits_for_the_last_round_of_the_first(generated, api, admin):
    fill_round(api, admin, generated, 1)
    fill_round(api, admin, generated, 2)

    api.force_authenticate(admin)
    states = states_by_number(api)
    assert states[3] == "open"  # last round of leg 1
    assert states[4] == "locked"  # first round of leg 2

    assert report(api, admin, round_matches(generated, 4)[0], 1, 0).status_code == 409

    fill_round(api, admin, generated, 3)
    states = states_by_number(api)
    assert states[3] == "closed"
    assert states[4] == "open"
    assert report(api, admin, round_matches(generated, 4)[0], 1, 0).status_code == 200


@pytest.mark.django_db
def test_correcting_an_old_result_does_not_block_later_rounds(generated, api, admin):
    fill_round(api, admin, generated, 1)
    round_two = round_matches(generated, 2)
    assert report(api, admin, round_two[0], 1, 0).status_code == 200

    first_round_match = round_matches(generated, 1)[0]
    api.force_authenticate(admin)
    correction = api.patch(
        f"/api/matches/{first_round_match.pk}/result/",
        {"home_goals": 5, "away_goals": 4, "note": "Placar corrigido"},
        format="json",
    )
    assert correction.status_code == 200
    assert correction.json()["code"] == "RESULT_CORRECTED"

    # The later round stays open and the standings are recalculated.
    assert states_by_number(api)[2] == "open"
    assert report(api, admin, round_two[1], 1, 0).status_code == 200

    table = api.get("/api/standings/").json()
    first_round_match.refresh_from_db()
    winner_team = first_round_match.home.team_name if first_round_match.home_goals > first_round_match.away_goals else first_round_match.away.team_name
    assert any(row["team_name"] == winner_team and row["points"] >= 3 for row in table)


@pytest.mark.django_db
def test_kickoff_change_is_allowed_on_a_locked_round(generated, four_players, api):
    round_two_match = round_matches(generated, 2)[0]
    player = round_two_match.home.user

    api.force_authenticate(player)
    response = api.patch(
        f"/api/matches/{round_two_match.pk}/kickoff/",
        {"kickoff_at": "2026-12-01T20:30:00-03:00"},
        format="json",
    )
    assert response.status_code == 200
    assert response.json()["code"] == "KICKOFF_UPDATED"
    round_two_match.refresh_from_db()
    assert round_two_match.kickoff_at is not None


@pytest.mark.django_db(transaction=True)
def test_two_simultaneous_reports_cannot_bypass_the_lock(generated, admin):
    """Both concurrent writes must fail while round 1 is incomplete."""
    targets = [match.pk for match in round_matches(generated, 2)]
    assert len(targets) == 2

    results = []
    barrier = threading.Barrier(len(targets))

    def call(match_pk):
        try:
            client = APIClient()
            client.force_authenticate(admin)
            barrier.wait(timeout=10)
            response = client.post(
                f"/api/matches/{match_pk}/result/",
                {"home_goals": 1, "away_goals": 0},
                format="json",
            )
            results.append((response.status_code, response.json().get("code")))
        finally:
            connections.close_all()

    threads = [threading.Thread(target=call, args=(pk,)) for pk in targets]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert len(results) == 2
    assert all(status == 409 and code == "ROUND_NOT_OPEN" for status, code in results)
    assert Match.objects.filter(league=League.objects.get(), round__number=2, home_goals__isnull=False).count() == 0
