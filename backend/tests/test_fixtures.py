import pytest

from core.exceptions import AppError
from league.models import League, Match, Participant, Round
from league.services.fixtures import build_schedule, generate_fixtures
from league.services.results import report_result


def _enroll(league, make_user, enroll, count):
    users = [
        make_user(f"p{i}@teste.com", f"Jogador {i}", f"Time {i}")
        for i in range(count)
    ]
    enroll(users)
    return users


@pytest.mark.django_db
@pytest.mark.parametrize("n", [4, 5, 6, 7, 10])
def test_round_robin_shape_pairs_and_byes(league, make_user, enroll, n):
    users = _enroll(league, make_user, enroll, n)
    participant_ids = {
        Participant.objects.get(league=league, user=user).id for user in users
    }

    result = generate_fixtures(league, seed=42)
    assert result.created is True

    rounds_per_leg = n - 1 if n % 2 == 0 else n
    rounds = list(Round.objects.filter(league=league).order_by("number"))
    assert len(rounds) == rounds_per_leg * 2
    assert [r.number for r in rounds] == list(range(1, rounds_per_leg * 2 + 1))
    assert Match.objects.filter(league=league).count() == n * (n - 1)

    for leg in (1, 2):
        leg_rounds = [r for r in rounds if r.leg == leg]
        assert len(leg_rounds) == rounds_per_leg
        resting_players = []
        for round_obj in leg_rounds:
            matches = list(round_obj.matches.all())
            teams = [m.home_id for m in matches] + [m.away_id for m in matches]
            # No player appears twice in the same round.
            assert len(teams) == len(set(teams))
            if n % 2 == 0:
                assert len(matches) == n // 2
            else:
                assert len(matches) == (n - 1) // 2
                resting = participant_ids - set(teams)
                assert len(resting) == 1
                resting_players.extend(resting)
        if n % 2 == 1:
            # Everyone rests exactly once per leg.
            assert len(resting_players) == len(set(resting_players)) == n

        # Every pair meets exactly once per leg.
        pairs = {
            frozenset((m.home_id, m.away_id))
            for m in Match.objects.filter(league=league, leg=leg)
        }
        assert len(pairs) == n * (n - 1) // 2

    # Return leg mirrors the first one with home/away reversed.
    leg1 = {
        (m.home_id, m.away_id)
        for m in Match.objects.filter(league=league, leg=1)
    }
    leg2 = {
        (m.home_id, m.away_id)
        for m in Match.objects.filter(league=league, leg=2)
    }
    assert leg2 == {(away, home) for home, away in leg1}


@pytest.mark.django_db
def test_build_schedule_is_deterministic_with_seed(league, make_user, enroll):
    users = _enroll(league, make_user, enroll, 6)
    ids = [Participant.objects.get(league=league, user=u).id for u in users]
    first = build_schedule(ids, seed=7)
    second = build_schedule(ids, seed=7)
    assert first == second
    # Every round contains every participant exactly once for even N.
    for round_pairs in first:
        teams = [team for pair in round_pairs for team in pair]
        assert sorted(teams) == sorted(ids)


@pytest.mark.django_db
def test_generation_requires_two_players(league, api, admin):
    api.force_authenticate(admin)
    response = api.post("/api/admin/generate-fixtures/", {}, format="json")
    assert response.status_code == 400
    body = response.json()
    assert body["code"] == "NOT_ENOUGH_PLAYERS"
    assert body["message"] == "São necessários pelo menos 2 jogadores para gerar os confrontos."


@pytest.mark.django_db
def test_admin_generation_sets_league_state(league, players, api, admin):
    api.force_authenticate(admin)
    response = api.post("/api/admin/generate-fixtures/", {}, format="json")
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == "FIXTURES_GENERATED"
    assert body["data"]["matches"] == 3 * 2  # 3 players, single round robin x2
    assert body["data"]["rounds"] == 3 * 2

    league.refresh_from_db()
    assert league.status == League.Status.IN_PROGRESS
    assert league.fixture_seed is not None
    assert league.registration_open is False


@pytest.mark.django_db
def test_only_admin_can_generate(league, players, api, make_user):
    regular = make_user("regular@teste.com", "Regular", "Regular FC")
    api.force_authenticate(regular)
    response = api.post("/api/admin/generate-fixtures/", {}, format="json")
    assert response.status_code == 403
    assert response.json()["code"] == "ADMIN_ONLY"
    assert Match.objects.filter(league=league).count() == 0


@pytest.mark.django_db
def test_fixture_generation_rolls_back_validation_errors(
    league, make_user, enroll, monkeypatch
):
    _enroll(league, make_user, enroll, 4)

    def broken_schedule(ids, seed=None):
        return [[(ids[0], ids[0])]]  # invalid: same team twice

    monkeypatch.setattr(
        "league.services.fixtures.build_schedule", broken_schedule
    )
    with pytest.raises(AppError):
        generate_fixtures(league, seed=1)

    assert Match.objects.filter(league=league).count() == 0
    assert Round.objects.filter(league=league).count() == 0
    league.refresh_from_db()
    assert league.fixtures_generated_at is None


@pytest.mark.django_db
def test_result_reported_by_admin_updates_standings(league, players, api, admin):
    api.force_authenticate(admin)
    api.post("/api/admin/generate-fixtures/", {}, format="json")
    match = Match.objects.filter(league=league).first()
    report_result(match, admin, 1, 0)

    table = api.get("/api/standings/").json()
    assert table[0]["wins"] == 1
    assert table[0]["points"] == 3
