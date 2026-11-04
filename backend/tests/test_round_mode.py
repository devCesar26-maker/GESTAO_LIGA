"""Configurable round blocks: one round at a time or fixed pairs (1,2), (3,4)...

With ``single_round_mode`` enabled the original sequential lock is preserved.
With it disabled, both rounds of a pair open together and both must be closed
before the next pair may receive a new result. Existing results are never
deleted when the setting changes.
"""
import threading

import pytest
from django.db import connections
from django.utils import timezone
from rest_framework.test import APIClient

from core.messages import MESSAGES
from league.models import League, LeagueChangeLog, Match, Participant, Round
from league.services.rounds import block_number

from .helpers import winning_score_for

ROUND_LOCK_MESSAGE = MESSAGES["ROUND_NOT_OPEN"]


def enroll_players(make_user, enroll, count, prefix="p"):
    users = [
        make_user(f"{prefix}{index}@teste.com", f"Jogador {index}", f"Time {index}")
        for index in range(1, count + 1)
    ]
    enroll(users)
    return users


def generate(api, admin):
    api.force_authenticate(admin)
    response = api.post("/api/admin/generate-fixtures/", {}, format="json")
    assert response.status_code == 200, response.json()
    return response


def set_mode(api, admin, single_round_mode):
    api.force_authenticate(admin)
    response = api.patch(
        "/api/admin/league/",
        {"single_round_mode": single_round_mode},
        format="json",
    )
    assert response.status_code == 200, response.json()
    return response


def round_matches(league, number):
    return list(
        Match.objects.filter(league=league, round__number=number)
        .select_related("home__user", "away__user")
        .order_by("id")
    )


def report(api, user, match, home_goals=1, away_goals=0):
    api.force_authenticate(user)
    return api.post(
        f"/api/matches/{match.pk}/result/",
        {"home_goals": home_goals, "away_goals": away_goals},
        format="json",
    )


def fill_round(api, admin, league, number):
    api.force_authenticate(admin)
    pending = Match.objects.filter(
        league=league, round__number=number, home_goals__isnull=True
    ).order_by("id")
    for match in pending:
        response = api.post(
            f"/api/matches/{match.pk}/result/",
            {"home_goals": 1, "away_goals": 0},
            format="json",
        )
        assert response.status_code == 200, response.json()


def close_rounds_directly(league, numbers, admin):
    """Setup helper: mark all matches of the given rounds as finished."""
    Match.objects.filter(league=league, round__number__in=numbers).update(
        status=Match.Status.FINISHED,
        home_goals=1,
        away_goals=0,
        is_walkover=False,
        result_reported_by=admin,
        result_reported_at=timezone.now(),
    )


def states_by_number(api):
    rounds = api.get("/api/rounds/").json()
    return {round_data["number"]: round_data["state"] for round_data in rounds}


@pytest.mark.django_db
def test_single_round_mode_is_the_default_and_is_exposed_publicly(league, api):
    league.refresh_from_db()
    assert league.single_round_mode is True
    assert api.get("/api/league/").json()["single_round_mode"] is True


@pytest.mark.django_db
def test_only_admin_changes_the_mode_and_the_change_is_audited(league, api, admin, make_user):
    regular = make_user("regular@teste.com", "Regular", "Regular FC")

    api.force_authenticate(regular)
    denied = api.patch(
        "/api/admin/league/", {"single_round_mode": False}, format="json"
    )
    assert denied.status_code == 403
    assert denied.json()["code"] == "ADMIN_ONLY"
    league.refresh_from_db()
    assert league.single_round_mode is True

    changed = set_mode(api, admin, False).json()
    assert changed["changed"] is True
    assert changed["league"]["single_round_mode"] is False
    assert api.get("/api/league/").json()["single_round_mode"] is False
    league.refresh_from_db()
    assert league.single_round_mode is False

    log = LeagueChangeLog.objects.get(league=league)
    assert log.action == LeagueChangeLog.Action.SINGLE_ROUND_MODE_CHANGED
    assert log.previous == {"single_round_mode": True}
    assert log.new == {"single_round_mode": False}
    assert log.user == admin

    # Same value again is a no-op and writes no extra audit row.
    same = set_mode(api, admin, False).json()
    assert same["changed"] is False
    assert same["code"] == "NOTHING_CHANGED"
    assert LeagueChangeLog.objects.filter(league=league).count() == 1

    set_mode(api, admin, True)
    assert LeagueChangeLog.objects.filter(league=league).count() == 2


@pytest.mark.django_db
def test_enabled_mode_keeps_one_round_at_a_time(
    league, api, admin, make_user, enroll
):
    enroll_players(make_user, enroll, 4)
    generate(api, admin)

    assert states_by_number(api)[1] == "open"
    assert states_by_number(api)[2] == "locked"

    fill_round(api, admin, league, 1)
    states = states_by_number(api)
    assert states[1] == "closed"
    assert states[2] == "open"
    assert states[3] == "locked"


@pytest.mark.django_db
def test_disabled_mode_opens_the_pair_and_requires_both_rounds_closed(
    league, api, admin, make_user, enroll
):
    enroll_players(make_user, enroll, 4)
    generate(api, admin)
    set_mode(api, admin, False)

    states = states_by_number(api)
    assert states[1] == "open"
    assert states[2] == "open"
    assert states[3] == "locked"
    assert states[4] == "locked"

    # Both rounds of the first pair accept results from the start.
    assert report(api, admin, round_matches(league, 1)[0]).status_code == 200
    assert report(api, admin, round_matches(league, 2)[0]).status_code == 200

    # Closing only round 1 does not release the next pair.
    fill_round(api, admin, league, 1)
    states = states_by_number(api)
    assert states[1] == "closed"
    assert states[2] == "open"
    assert states[3] == "locked"

    blocked = report(api, admin, round_matches(league, 3)[0])
    assert blocked.status_code == 409
    assert blocked.json() == {
        "code": "ROUND_NOT_OPEN",
        "message": ROUND_LOCK_MESSAGE,
    }

    # Closing round 2 releases rounds 3 and 4 together.
    fill_round(api, admin, league, 2)
    states = states_by_number(api)
    assert states[1] == "closed"
    assert states[2] == "closed"
    assert states[3] == "open"
    assert states[4] == "open"
    assert states[5] == "locked"


@pytest.mark.django_db
def test_eleven_players_have_22_rounds_and_fixed_pairs_across_the_turnaround(
    league, api, admin, make_user, enroll
):
    users = enroll_players(make_user, enroll, 11, prefix="eleven")
    participant_ids = set(
        Participant.objects.filter(league=league, user__in=users).values_list(
            "id", flat=True
        )
    )
    generate(api, admin)
    set_mode(api, admin, False)

    rounds = list(Round.objects.filter(league=league).order_by("number"))
    assert [round_obj.number for round_obj in rounds] == list(range(1, 23))
    assert len(rounds) == 22

    for leg in (1, 2):
        resting = []
        leg_rounds = [round_obj for round_obj in rounds if round_obj.leg == leg]
        assert len(leg_rounds) == 11
        for round_obj in leg_rounds:
            matches = round_matches(league, round_obj.number)
            assert len(matches) == 5
            teams = [match.home_id for match in matches] + [
                match.away_id for match in matches
            ]
            assert len(teams) == len(set(teams)) == 10
            bye = participant_ids - set(teams)
            assert len(bye) == 1
            resting.extend(bye)
        # Each player rests exactly once per leg.
        assert len(resting) == 11
        assert set(resting) == participant_ids

    # Fixed pairs, including the one that crosses from leg 1 to leg 2.
    assert block_number(11) == 6
    assert block_number(12) == 6
    assert Round.objects.get(league=league, number=11).leg == 1
    assert Round.objects.get(league=league, number=12).leg == 2

    states = states_by_number(api)
    assert states[1] == states[2] == "open"
    assert states[3] == states[4] == "locked"

    # Close the first five pairs without touching the crossing pair.
    close_rounds_directly(league, range(1, 11), admin)
    states = states_by_number(api)
    assert all(states[number] == "closed" for number in range(1, 11))
    assert states[11] == states[12] == "open"
    assert states[13] == states[14] == "locked"

    # A match in each round of the crossing pair can be registered normally.
    assert report(api, admin, round_matches(league, 11)[0]).status_code == 200
    assert report(api, admin, round_matches(league, 12)[0]).status_code == 200

    # The last pair (21, 22) is also complete: no lone round at the end.
    close_rounds_directly(league, range(11, 21), admin)
    states = states_by_number(api)
    assert states[21] == states[22] == "open"
    assert states[20] == "closed"


@pytest.mark.django_db
def test_even_players_pair_crosses_the_turnaround(
    league, api, admin, make_user, enroll
):
    enroll_players(make_user, enroll, 10, prefix="even")
    generate(api, admin)
    set_mode(api, admin, False)

    rounds = list(Round.objects.filter(league=league).order_by("number"))
    assert len(rounds) == 18
    assert all(len(round_matches(league, number)) == 5 for number in range(1, 19))
    assert Round.objects.get(league=league, number=9).leg == 1
    assert Round.objects.get(league=league, number=10).leg == 2

    close_rounds_directly(league, range(1, 9), admin)
    states = states_by_number(api)
    assert states[9] == states[10] == "open"
    assert states[11] == states[12] == "locked"

    assert report(api, admin, round_matches(league, 9)[0]).status_code == 200
    assert report(api, admin, round_matches(league, 10)[0]).status_code == 200

    fill_round(api, admin, league, 9)
    fill_round(api, admin, league, 10)
    states = states_by_number(api)
    assert states[9] == states[10] == "closed"
    assert states[11] == states[12] == "open"


@pytest.mark.django_db
def test_odd_total_rounds_leaves_the_last_round_alone_in_its_block(
    league, api, admin, make_user, enroll
):
    enroll_players(make_user, enroll, 3, prefix="odd")
    generate(api, admin)
    set_mode(api, admin, False)

    # Simulate an odd total: keep rounds 1..5, drop the sixth.
    Round.objects.filter(league=league, number__gt=5).delete()
    assert Round.objects.filter(league=league).count() == 5
    assert block_number(5) == 3

    states = states_by_number(api)
    assert states[1] == states[2] == "open"
    assert states[3] == states[4] == "locked"
    assert states[5] == "locked"

    close_rounds_directly(league, [1, 2], admin)
    states = states_by_number(api)
    assert states[3] == states[4] == "open"
    assert states[5] == "locked"

    close_rounds_directly(league, [3, 4], admin)
    states = states_by_number(api)
    assert states[5] == "open"
    assert report(api, admin, round_matches(league, 5)[0]).status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize("single_round_mode", [True, False])
def test_a_round_with_a_bye_closes_in_both_modes(
    league, api, admin, make_user, enroll, single_round_mode
):
    enroll_players(make_user, enroll, 3, prefix=f"bye{single_round_mode}")
    generate(api, admin)
    set_mode(api, admin, single_round_mode)

    round_one = round_matches(league, 1)
    assert len(round_one) == 1  # one match, one player rests

    assert report(api, admin, round_one[0]).status_code == 200
    states = states_by_number(api)
    assert states[1] == "closed"
    assert states[2] == "open"

    # The next round can receive a result as soon as the bye round closes.
    assert report(api, admin, round_matches(league, 2)[0]).status_code == 200


@pytest.mark.django_db
def test_one_player_can_have_a_pending_match_in_both_open_rounds(
    league, api, admin, make_user, enroll
):
    enroll_players(make_user, enroll, 4, prefix="pair")
    generate(api, admin)
    set_mode(api, admin, False)

    round_one_match = round_matches(league, 1)[0]
    player = round_one_match.home.user
    round_two_match = next(
        match
        for match in round_matches(league, 2)
        if player.id in (match.home.user_id, match.away.user_id)
    )

    first_score = winning_score_for(round_one_match, player)
    second_score = winning_score_for(round_two_match, player)
    assert report(api, player, round_one_match, *first_score).status_code == 200
    assert report(api, player, round_two_match, *second_score).status_code == 200

    round_one_match.refresh_from_db()
    round_two_match.refresh_from_db()
    assert round_one_match.status == Match.Status.FINISHED
    assert round_two_match.status == Match.Status.FINISHED


@pytest.mark.django_db
@pytest.mark.parametrize("single_round_mode", [True, False])
def test_contested_and_walkover_count_as_closed_in_both_modes(
    league, api, admin, make_user, enroll, single_round_mode
):
    enroll_players(make_user, enroll, 4, prefix=f"closed{single_round_mode}")
    generate(api, admin)
    set_mode(api, admin, single_round_mode)

    first, second = round_matches(league, 1)

    # A normal result contested by the opponent still closes its match.
    winner = first.home.user
    loser = first.away.user
    assert report(api, winner, first, 2, 0).status_code == 200
    api.force_authenticate(loser)
    contested = api.post(
        f"/api/matches/{first.pk}/contest/",
        {"reason": "placar incorreto"},
        format="json",
    )
    assert contested.status_code == 200
    assert contested.json()["match"]["status"] == "CONTESTED"

    # A W.O. also closes its match.
    api.force_authenticate(admin)
    walkover = api.post(
        f"/api/matches/{second.pk}/walkover/",
        {"absent_side": "away"},
        format="json",
    )
    assert walkover.status_code == 200

    states = states_by_number(api)
    assert states[1] == "closed"
    assert states[2] == "open"
    if single_round_mode:
        assert states[3] == "locked"
    else:
        assert states[3] == "locked"  # pair 1 is not complete: round 2 is pending


@pytest.mark.django_db
def test_toggling_mid_league_keeps_results_and_recalculates_states(
    league, api, admin, make_user, enroll
):
    enroll_players(make_user, enroll, 4, prefix="toggle")
    generate(api, admin)
    set_mode(api, admin, False)

    round_one = round_matches(league, 1)
    round_two = round_matches(league, 2)

    # Round 2 accepts a result while round 1 is still incomplete.
    assert report(api, admin, round_two[0], 3, 2).status_code == 200
    round_two[0].refresh_from_db()
    existing_result = (round_two[0].home_goals, round_two[0].away_goals)
    assert existing_result == (3, 2)
    logs_before = round_two[0].logs.count()

    # Also leave round 1 partially filled.
    assert report(api, admin, round_one[0], 1, 0).status_code == 200

    # Switching to one-round mode never touches existing results.
    set_mode(api, admin, True)
    round_two[0].refresh_from_db()
    assert (round_two[0].home_goals, round_two[0].away_goals) == existing_result
    assert round_two[0].logs.count() == logs_before

    states = states_by_number(api)
    assert states[1] == "open"
    assert states[2] == "locked"

    # New results in the partially filled round are blocked while round 1 is open.
    blocked = report(api, admin, round_two[1], 1, 0)
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "ROUND_NOT_OPEN"

    # Correcting an existing result is still allowed while the round is locked.
    correction = api.patch(
        f"/api/matches/{round_two[0].pk}/result/",
        {"home_goals": 4, "away_goals": 2, "note": "correção permitida"},
        format="json",
    )
    assert correction.status_code == 200
    assert correction.json()["code"] == "RESULT_CORRECTED"
    round_two[0].refresh_from_db()
    assert (round_two[0].home_goals, round_two[0].away_goals) == (4, 2)

    # Finishing round 1 opens round 2 again under the current setting.
    fill_round(api, admin, league, 1)
    states = states_by_number(api)
    assert states[1] == "closed"
    assert states[2] == "open"
    assert report(api, admin, round_two[1], 1, 0).status_code == 200

    # Switching back to pairs recalculates the states without touching results.
    set_mode(api, admin, False)
    round_two[0].refresh_from_db()
    assert (round_two[0].home_goals, round_two[0].away_goals) == (4, 2)
    states = states_by_number(api)
    assert states[1] == states[2] == "closed"
    assert states[3] == states[4] == "open"


@pytest.mark.django_db(transaction=True)
def test_two_simultaneous_reports_cannot_bypass_a_locked_block(
    league, api, admin, make_user, enroll
):
    enroll_players(make_user, enroll, 4, prefix="concurrent")
    generate(api, admin)
    set_mode(api, admin, False)

    # Rounds 1 and 2 are open but still incomplete; rounds 3 and 4 are locked.
    targets = [match.pk for match in round_matches(league, 3)]
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
    assert (
        Match.objects.filter(
            league=League.objects.get(), round__number=3, home_goals__isnull=False
        ).count()
        == 0
    )


@pytest.mark.django_db(transaction=True)
def test_mode_change_during_a_report_is_serialized_by_the_league_lock(
    league, api, admin, make_user, enroll
):
    enroll_players(make_user, enroll, 4, prefix="togglethread")
    generate(api, admin)
    set_mode(api, admin, False)

    target = round_matches(league, 2)[0]
    report_result_holder = []
    toggle_holder = []
    barrier = threading.Barrier(2)

    def write_result():
        try:
            client = APIClient()
            client.force_authenticate(admin)
            barrier.wait(timeout=10)
            response = client.post(
                f"/api/matches/{target.pk}/result/",
                {"home_goals": 1, "away_goals": 0},
                format="json",
            )
            report_result_holder.append((response.status_code, response.json().get("code")))
        finally:
            connections.close_all()

    def toggle_mode():
        try:
            client = APIClient()
            client.force_authenticate(admin)
            barrier.wait(timeout=10)
            response = client.patch(
                "/api/admin/league/",
                {"single_round_mode": True},
                format="json",
            )
            toggle_holder.append(response.status_code)
        finally:
            connections.close_all()

    threads = [
        threading.Thread(target=write_result),
        threading.Thread(target=toggle_mode),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert report_result_holder and toggle_holder
    status, code = report_result_holder[0]
    assert toggle_holder[0] == 200

    league.refresh_from_db()
    target.refresh_from_db()

    if status == 200:
        # The report acquired the league lock first; it was valid under the
        # pair mode in force at that moment.
        assert code == "RESULT_REPORTED"
        assert league.single_round_mode is True
        assert target.home_goals == 1
        toggle_log = LeagueChangeLog.objects.get(
            league=league,
            action=LeagueChangeLog.Action.SINGLE_ROUND_MODE_CHANGED,
        )
        report_log = target.logs.get(action="RESULT_REPORTED")
        assert report_log.created_at <= toggle_log.created_at
    else:
        # The toggle acquired the lock first; the report then saw single mode
        # and round 1 was still incomplete.
        assert status == 409
        assert code == "ROUND_NOT_OPEN"
        assert target.home_goals is None
