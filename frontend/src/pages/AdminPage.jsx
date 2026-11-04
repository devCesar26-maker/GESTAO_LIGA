import { useCallback, useEffect, useState } from "react";

import { leagueApi } from "../api/endpoints";
import ConfirmDialog from "../components/ConfirmDialog";
import { EmptyState, ErrorState, LoadingState } from "../components/PageState";
import ResultDialog from "../components/ResultDialog";
import StatusBadge from "../components/StatusBadge";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";

const emptyEnroll = { email: "", name: "", team_name: "", password: "" };

export default function AdminPage() {
  const { user } = useAuth();
  const { notify } = useToast();

  const [overview, setOverview] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [busy, setBusy] = useState("");
  const [showReset, setShowReset] = useState(false);
  const [correction, setCorrection] = useState(null);
  const [enroll, setEnroll] = useState(emptyEnroll);
  const [participantToRemove, setParticipantToRemove] = useState(null);
  const [leagueName, setLeagueName] = useState("");
  const [roundModeChange, setRoundModeChange] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(false);
    try {
      const { data } = await leagueApi.getOverview();
      setOverview(data);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const league = overview?.league;
  const participants = overview?.participants || [];
  const contested = overview?.contested_matches || [];
  const pending = overview?.pending_matches_list || [];
  const fixturesGenerated = Boolean(league?.fixtures_generated_at);
  const hasResults = Boolean(overview?.has_results);
  const removeMessage = participantToRemove
    ? `${participantToRemove.player_name} (${participantToRemove.team_name}) será removido da liga. A conta de login continuará existindo.${
        fixturesGenerated && !hasResults
          ? " Os confrontos serão regerados sem ele."
          : ""
      }${
        hasResults
          ? " Se ele já tiver resultados lançados, a remoção será bloqueada para preservar o histórico."
          : ""
      }`
    : "";

  useEffect(() => {
    if (league?.name) setLeagueName(league.name);
  }, [league?.name]);

  const generate = async () => {
    setBusy("generate");
    try {
      const { data } = await leagueApi.generateFixtures();
      notify(data.message, "success");
      await load();
    } catch {
      // Toast handled globally.
    } finally {
      setBusy("");
    }
  };

  const resetFixtures = async () => {
    const { data } = await leagueApi.resetFixtures();
    notify(data.message, "success");
    await load();
  };

  const confirmMatch = async (match) => {
    setBusy(`confirm-${match.id}`);
    try {
      const { data } = await leagueApi.confirmResult(match.id);
      notify(data.message, "success");
      await load();
    } catch {
      // Toast handled globally.
    } finally {
      setBusy("");
    }
  };

  const correctResult = async (home, away, note) => {
    if (!correction) return;
    setBusy(`correct-${correction.id}`);
    try {
      const { data } = await leagueApi.correctResult(correction.id, home, away, note);
      notify(data.message, "success");
      await load();
    } finally {
      setBusy("");
    }
  };

  const renameLeague = async (event) => {
    event.preventDefault();
    setBusy("league-name");
    try {
      const { data } = await leagueApi.updateLeagueName(leagueName.trim());
      notify(data.message, "success");
      // The header/title listen to this event and refresh the name.
      window.dispatchEvent(new Event("liga:updated"));
      await load();
    } catch {
      // Toast handled globally.
    } finally {
      setBusy("");
    }
  };

  const changeRoundMode = async () => {
    if (roundModeChange === null) return;
    setBusy("round-mode");
    try {
      const { data } = await leagueApi.updateLeagueMode(roundModeChange);
      notify(data.message, "success");
      await load();
    } finally {
      setBusy("");
    }
  };

  const registerWalkover = async (match, absentSide) => {
    setBusy(`wo-${match.id}`);
    try {
      const { data } = await leagueApi.registerWalkover(match.id, absentSide);
      notify(data.message, "success");
      await load();
    } catch {
      // Toast handled globally.
    } finally {
      setBusy("");
    }
  };

  const enrollPlayer = async (event) => {
    event.preventDefault();
    setBusy("enroll");
    try {
      const payload = { email: enroll.email.trim() };
      if (enroll.name.trim()) payload.name = enroll.name.trim();
      if (enroll.team_name.trim()) payload.team_name = enroll.team_name.trim();
      if (enroll.password) payload.password = enroll.password;
      const { data } = await leagueApi.enrollParticipant(payload);
      notify(data.message, "success");
      setEnroll(emptyEnroll);
      await load();
    } catch {
      // Toast handled globally.
    } finally {
      setBusy("");
    }
  };

  const removePlayer = async () => {
    if (!participantToRemove) return;
    setBusy(`remove-${participantToRemove.id}`);
    try {
      const { data } = await leagueApi.removeParticipant(participantToRemove.id);
      notify(data.message, "success");
      await load();
    } finally {
      setBusy("");
    }
  };

  if (loading) return <LoadingState label="Carregando o painel..." />;
  if (error) return <ErrorState onRetry={load} />;

  return (
    <div className="page">
      <section className="page-head">
        <div>
          <p className="eyebrow">Administração</p>
          <h1 className="page-title">Painel da liga</h1>
          <p className="page-subtitle">Gerencie confrontos, correções e inscrições.</p>
        </div>
        {league && <StatusBadge status={league.status} />}
      </section>

      <section className="stat-grid" aria-label="Resumo da liga">
        <div className="stat-card">
          <span className="stat-label">Jogadores</span>
          <strong>{participants.length}</strong>
        </div>
        <div className="stat-card">
          <span className="stat-label">Partidas pendentes</span>
          <strong>{overview?.pending_matches ?? 0}</strong>
        </div>
        <div className="stat-card">
          <span className="stat-label">Partidas finalizadas</span>
          <strong>{overview?.finished_matches ?? 0}</strong>
        </div>
        <div className="stat-card stat-card-alert">
          <span className="stat-label">Contestadas</span>
          <strong>{contested.length}</strong>
        </div>
      </section>

      <section className="panel">
        <header className="panel-head">
          <h2>Nome da liga</h2>
          <p className="panel-subtitle">
            Aparece no cabeçalho, no título da página e na classificação. Pode ser alterado a
            qualquer momento, inclusive com a liga em andamento.
          </p>
        </header>

        <form className="stack" onSubmit={renameLeague}>
          <label className="field">
            <span>Nome exibido</span>
            <input
              type="text"
              required
              minLength="3"
              maxLength="60"
              value={leagueName}
              onChange={(event) => setLeagueName(event.target.value)}
              placeholder="Liga eFootball"
            />
            <small>De 3 a 60 caracteres. Espaços extras são removidos.</small>
          </label>
          <button
            type="submit"
            className="button"
            disabled={busy === "league-name" || leagueName.trim().length < 3}
          >
            {busy === "league-name" ? "Salvando..." : "Salvar nome"}
          </button>
        </form>
      </section>

      <section className="panel">
        <header className="panel-head">
          <h2>Modo de rodadas</h2>
          <p className="panel-subtitle">
            Controla quantas rodadas podem ficar abertas ao mesmo tempo. A alteração é registrada
            na auditoria e não apaga resultados já lançados.
          </p>
        </header>

        <label className="switch">
          <input
            type="checkbox"
            checked={Boolean(league?.single_round_mode)}
            onChange={(event) =>
              setRoundModeChange(event.target.checked)
            }
            disabled={busy === "round-mode"}
            aria-describedby="round-mode-help"
          />
          <span className="switch-track" aria-hidden="true">
            <span className="switch-thumb" />
          </span>
          <span>Modo 1 rodada por vez</span>
        </label>
        <p className="panel-footnote" id="round-mode-help">
          Ativado: uma rodada por vez. Desativado: duas rodadas ao mesmo tempo (1 e 2, depois 3 e
          4...).
        </p>
      </section>

      <section className="panel">
        <header className="panel-head">
          <h2>Confrontos</h2>
          <p className="panel-subtitle">
            {fixturesGenerated
              ? `${league.rounds_count} rodadas e ${league.matches_count} partidas geradas.`
              : "Ainda não há confrontos gerados para esta liga."}
          </p>
        </header>

        <div className="inline-actions">
          <span
            className="tooltip-wrap"
            title={
              fixturesGenerated
                ? "Os confrontos já foram gerados. Use “Resetar e regerar” se precisar refazer."
                : participants.length < 2
                  ? "São necessários pelo menos 2 jogadores para gerar os confrontos."
                  : "Gerar as partidas do 1º e do 2º turno."
            }
          >
            <button
              type="button"
              className="button"
              onClick={generate}
              disabled={fixturesGenerated || participants.length < 2 || busy === "generate"}
            >
              {busy === "generate" ? "Gerando..." : "Gerar confrontos"}
            </button>
          </span>

          <span
            className="tooltip-wrap"
            title={
              hasResults
                ? "Não é possível regerar os confrontos, pois já existem resultados lançados."
                : "Apaga os confrontos atuais e sorteia novamente."
            }
          >
            <button
              type="button"
              className="button button-ghost"
              onClick={() => setShowReset(true)}
              disabled={hasResults || busy === "reset"}
            >
              Resetar e regerar
            </button>
          </span>
        </div>

        {fixturesGenerated && (
          <p className="panel-footnote">
            Sorteio auditável com semente <code>{league.fixture_seed}</code>.
          </p>
        )}

        {!fixturesGenerated && participants.length < 2 && (
          <div className="notice notice-info">
            <strong>Faltam jogadores.</strong>
            <span>Inscreva pelo menos 2 pessoas para gerar os confrontos.</span>
          </div>
        )}
      </section>

      <section className="panel">
        <header className="panel-head">
          <h2>Lançar W.O.</h2>
          <p className="panel-subtitle">
            Use quando um jogador não comparecer: quem jogou vence por 3 a 0, a partida é encerrada
            e a rodada pode avançar.
          </p>
        </header>

        {pending.length === 0 ? (
          <EmptyState icon="📅" title="Nenhuma partida pendente" />
        ) : (
          <ul className="wo-list">
            {pending.map((match) => {
              const locked = match.round_state === "locked";
              const disabled = locked || busy === `wo-${match.id}`;
              return (
                <li key={match.id} className="wo-row">
                  <span className="wo-match">
                    <strong>
                      R{match.round_number} · {match.home.team_name} × {match.away.team_name}
                    </strong>
                    {locked && (
                      <small className="muted">
                        🔒 Esta rodada será liberada quando as rodadas anteriores forem encerradas.
                      </small>
                    )}
                  </span>
                  <span className="inline-actions">
                    <button
                      type="button"
                      className="button button-small button-ghost"
                      onClick={() => registerWalkover(match, "home")}
                      disabled={disabled}
                      title={`${match.home.team_name} não compareceu — vitória de ${match.away.team_name}`}
                    >
                      Faltou {match.home.team_name}
                    </button>
                    <button
                      type="button"
                      className="button button-small button-ghost"
                      onClick={() => registerWalkover(match, "away")}
                      disabled={disabled}
                      title={`${match.away.team_name} não compareceu — vitória de ${match.home.team_name}`}
                    >
                      Faltou {match.away.team_name}
                    </button>
                  </span>
                </li>
              );
            })}
          </ul>
        )}
      </section>

      <section className="panel">
        <header className="panel-head">
          <h2>Resultados contestados</h2>
          <p className="panel-subtitle">
            Enquanto contestados, os placares continuam valendo na classificação.
          </p>
        </header>

        {contested.length === 0 ? (
          <EmptyState
            icon="✅"
            title="Nenhuma contestação pendente"
            description="Quando alguém contestar um resultado, a partida aparece aqui."
          />
        ) : (
          <ul className="admin-match-list">
            {contested.map((match) => (
              <li key={match.id} className="admin-match">
                <div className="admin-match-info">
                  <strong>
                    {match.home.team_name} {match.home_goals} × {match.away_goals}{" "}
                    {match.away.team_name}
                  </strong>
                  <span className="muted">
                    Rodada {match.round_number} · contestado por{" "}
                    {match.contested_by_name || "jogador"}
                  </span>
                  {match.contest_reason && (
                    <em className="admin-match-reason">“{match.contest_reason}”</em>
                  )}
                </div>
                <div className="inline-actions">
                  <button
                    type="button"
                    className="button button-small button-ghost"
                    onClick={() => setCorrection(match)}
                  >
                    Corrigir
                  </button>
                  <button
                    type="button"
                    className="button button-small"
                    onClick={() => confirmMatch(match)}
                    disabled={busy === `confirm-${match.id}`}
                  >
                    {busy === `confirm-${match.id}` ? "Confirmando..." : "Confirmar"}
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <div className="admin-grid">
        <section className="panel">
          <header className="panel-head">
            <h2>Jogadores inscritos</h2>
            <p className="panel-subtitle">{participants.length} participante(s).</p>
          </header>

          {participants.length === 0 ? (
            <EmptyState icon="👥" title="Ninguém inscrito ainda" />
          ) : (
            <ul className="participant-list">
              {participants.map((participant) => (
                <li key={participant.id}>
                  <div className="participant-info">
                    <span className="participant-team">{participant.team_name}</span>
                    <span>{participant.player_name}</span>
                    <span className="muted participant-email">{participant.email}</span>
                  </div>
                  <button
                    type="button"
                    className="button button-small button-ghost participant-remove"
                    onClick={() => setParticipantToRemove(participant)}
                    disabled={busy === `remove-${participant.id}`}
                    title="Remover da liga. A conta de login será mantida."
                  >
                    {busy === `remove-${participant.id}` ? "Removendo..." : "Remover"}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="panel">
          <header className="panel-head">
            <h2>Inscrever jogador</h2>
            <p className="panel-subtitle">
              Para um email sem conta, informe também nome, time e senha provisória.
            </p>
          </header>

          <form className="stack" onSubmit={enrollPlayer}>
            <label className="field">
              <span>Email</span>
              <input
                type="email"
                required
                value={enroll.email}
                onChange={(event) =>
                  setEnroll((current) => ({ ...current, email: event.target.value }))
                }
                placeholder="jogador@email.com"
              />
            </label>
            <label className="field">
              <span>Nome (para conta nova)</span>
              <input
                type="text"
                maxLength="120"
                value={enroll.name}
                onChange={(event) =>
                  setEnroll((current) => ({ ...current, name: event.target.value }))
                }
              />
            </label>
            <label className="field">
              <span>Nome do time (para conta nova)</span>
              <input
                type="text"
                maxLength="60"
                value={enroll.team_name}
                onChange={(event) =>
                  setEnroll((current) => ({ ...current, team_name: event.target.value }))
                }
              />
            </label>
            <label className="field">
              <span>Senha provisória (para conta nova)</span>
              <input
                type="password"
                autoComplete="new-password"
                value={enroll.password}
                onChange={(event) =>
                  setEnroll((current) => ({ ...current, password: event.target.value }))
                }
                placeholder="Mínimo de 8 caracteres"
              />
            </label>
            <button type="submit" className="button" disabled={busy === "enroll"}>
              {busy === "enroll" ? "Inscrevendo..." : "Inscrever jogador"}
            </button>
          </form>
        </section>
      </div>

      {roundModeChange !== null && (
        <ConfirmDialog
          title={
            roundModeChange
              ? "Ativar o modo 1 rodada por vez?"
              : "Permitir 2 rodadas ao mesmo tempo?"
          }
          message={
            roundModeChange
              ? "Apenas uma rodada ficará aberta por vez: a próxima só é liberada quando a anterior for encerrada. Resultados já lançados são mantidos."
              : "As rodadas ficarão abertas em pares fixos: 1 e 2, depois 3 e 4, e assim por diante. A virada de turno não muda os pares e resultados já lançados são mantidos."
          }
          confirmLabel="Alterar modo"
          onConfirm={changeRoundMode}
          onClose={() => setRoundModeChange(null)}
        />
      )}

      {participantToRemove && (
        <ConfirmDialog
          title="Remover jogador?"
          message={removeMessage}
          confirmLabel="Remover"
          danger
          onConfirm={removePlayer}
          onClose={() => setParticipantToRemove(null)}
        />
      )}

      {showReset && (
        <ConfirmDialog
          title="Resetar e regerar confrontos?"
          message="Todos os confrontos atuais serão apagados e um novo sorteio será feito. Isso só é possível porque nenhuma partida tem resultado lançado."
          confirmLabel="Resetar e regerar"
          danger
          onConfirm={resetFixtures}
          onClose={() => setShowReset(false)}
        />
      )}

      {correction && (
        <ResultDialog
          match={correction}
          mode="correct"
          user={user}
          onClose={() => setCorrection(null)}
          onSubmit={correctResult}
        />
      )}
    </div>
  );
}
