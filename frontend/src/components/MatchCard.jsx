import { useState } from "react";

import { formatKickoff } from "../lib/format";
import ContestDialog from "./ContestDialog";
import KickoffDialog from "./KickoffDialog";
import ResultDialog from "./ResultDialog";
import StatusBadge from "./StatusBadge";

const ROUND_LOCK_HINT =
  "Esta rodada será liberada quando as rodadas anteriores forem encerradas.";

function TeamSide({ participant, goals, opponentGoals, hasResult }) {
  const won = hasResult && goals > opponentGoals;
  const lost = hasResult && goals < opponentGoals;
  return (
    <div className={`team-side${won ? " winner" : ""}${lost ? " loser" : ""}`}>
      <span className="team-name">{participant.team_name}</span>
      <span className="team-player">{participant.player_name}</span>
      {hasResult && <span className="team-score">{goals}</span>}
    </div>
  );
}

export default function MatchCard({ match, user, onReport, onCorrect, onKickoff, onContest, onConfirm }) {
  const [dialog, setDialog] = useState(null);
  const permissions = match.permissions || {};
  const roundLocked = match.round_state === "locked" || Boolean(permissions.round_locked);
  const mine = Boolean(
    user && (match.home.user_id === user.id || match.away.user_id === user.id),
  );
  const canAct =
    permissions.can_report ||
    permissions.can_set_kickoff ||
    permissions.can_contest ||
    permissions.can_correct ||
    permissions.can_confirm;

  return (
    <article
      className={`match-card${mine ? " is-mine" : ""}${match.status === "CONTESTED" ? " is-contested" : ""}`}
      aria-label={`${match.home.team_name} contra ${match.away.team_name}`}
    >
      <header className="match-meta">
        <span>Rodada {match.round_number}</span>
        <span className="match-time">{formatKickoff(match.kickoff_at)}</span>
        {match.is_walkover && (
          <span className="badge badge-walkover" title="Vitória por W.O. (3 a 0)">
            W.O.
          </span>
        )}
        <StatusBadge status={match.status} />
      </header>

      <div className="match-teams">
        <TeamSide
          participant={match.home}
          goals={match.home_goals}
          opponentGoals={match.away_goals}
          hasResult={match.has_result}
        />
        <span className="match-versus" aria-hidden="true">
          {match.has_result ? "×" : "vs"}
        </span>
        <TeamSide
          participant={match.away}
          goals={match.away_goals}
          opponentGoals={match.home_goals}
          hasResult={match.has_result}
        />
      </div>

      {mine && <p className="match-note mine-note">Sua partida</p>}

      {match.status === "CONTESTED" && (
        <p className="contest-note" role="note">
          Resultado contestado{match.contested_by_name ? ` por ${match.contested_by_name}` : ""}. O
          administrador vai revisar — o placar continua valendo até lá.
        </p>
      )}

      {match.has_result && match.reported_by_name && match.status !== "CONTESTED" && (
        <p className="match-note">Lançado por {match.reported_by_name}.</p>
      )}

      {roundLocked && match.status === "SCHEDULED" && (
        <p className="match-hint match-hint-locked" title={ROUND_LOCK_HINT}>
          <span aria-hidden="true">🔒</span> {ROUND_LOCK_HINT}
        </p>
      )}

      {canAct ? (
        <div className="match-actions">
          {permissions.can_report && (
            <button type="button" className="button button-small" onClick={() => setDialog("result")}>
              Inserir resultado
            </button>
          )}
          {permissions.can_set_kickoff && (
            <button
              type="button"
              className="button button-small button-ghost"
              onClick={() => setDialog("kickoff")}
            >
              Alterar data
            </button>
          )}
          {permissions.can_contest && (
            <button
              type="button"
              className="button button-small button-ghost"
              onClick={() => setDialog("contest")}
            >
              Contestar
            </button>
          )}
          {permissions.can_correct && (
            <button
              type="button"
              className="button button-small button-ghost"
              onClick={() => setDialog("result")}
            >
              Corrigir
            </button>
          )}
          {permissions.can_confirm && (
            <button
              type="button"
              className="button button-small"
              onClick={() => onConfirm(match)}
            >
              Confirmar
            </button>
          )}
        </div>
      ) : (
        match.status === "SCHEDULED" &&
        !roundLocked && (
          <p
            className="match-hint"
            title="Só os jogadores desta partida podem inserir o resultado ou alterar a data."
          >
            <span aria-hidden="true">🔒</span> Partida entre outros jogadores
          </p>
        )
      )}

      {dialog === "result" && (
        <ResultDialog
          match={match}
          user={user}
          mode={permissions.can_correct && !permissions.can_report ? "correct" : "report"}
          onClose={() => setDialog(null)}
          onSubmit={
            permissions.can_correct && !permissions.can_report
              ? (home, away, note) => onCorrect(match, home, away, note)
              : (home, away) => onReport(match, home, away)
          }
        />
      )}
      {dialog === "kickoff" && (
        <KickoffDialog
          match={match}
          onClose={() => setDialog(null)}
          onSubmit={(kickoffAt) => onKickoff(match, kickoffAt)}
        />
      )}
      {dialog === "contest" && (
        <ContestDialog
          match={match}
          onClose={() => setDialog(null)}
          onSubmit={(reason) => onContest(match, reason)}
        />
      )}
    </article>
  );
}
