from league.models import Match, Participant


def participant_for(league, user) -> Participant:
    return Participant.objects.get(league=league, user=user)


def match_between(league, user_a, user_b, leg: int = 1) -> Match:
    pa = participant_for(league, user_a)
    pb = participant_for(league, user_b)
    return Match.objects.get(
        league=league,
        leg=leg,
        home__in=[pa, pb],
        away__in=[pa, pb],
    )


def user_is_home(match, user) -> bool:
    return match.home.user_id == user.id


def round_one_pair(league):
    """Users and match of the first fixture of round 1.

    Round 1 is always open (the sequential round lock only blocks later rounds),
    so tests about result rules can rely on it regardless of the draw.
    """
    match = (
        Match.objects.filter(league=league, round__number=1)
        .select_related("home__user", "away__user")
        .order_by("id")
        .first()
    )
    return match.home.user, match.away.user, match


def outsider_for(league, match):
    """A participant who is not involved in the match (may be None)."""
    participant = (
        league.participants.select_related("user")
        .exclude(user_id__in=[match.home.user_id, match.away.user_id])
        .order_by("id")
        .first()
    )
    return participant.user if participant else None


def winning_score_for(match, user, goals_winner=2, goals_loser=0):
    """Return (home_goals, away_goals) where ``user`` wins."""
    if user_is_home(match, user):
        return goals_winner, goals_loser
    return goals_loser, goals_winner


def losing_score_for(match, user, goals_winner=2, goals_loser=0):
    """Return (home_goals, away_goals) where ``user`` loses."""
    if user_is_home(match, user):
        return goals_loser, goals_winner
    return goals_winner, goals_loser
