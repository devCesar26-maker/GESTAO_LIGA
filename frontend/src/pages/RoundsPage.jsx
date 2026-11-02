import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { leagueApi } from "../api/endpoints";
import MatchCard from "../components/MatchCard";
import { EmptyState, ErrorState, LoadingState } from "../components/PageState";
import StatusBadge from "../components/StatusBadge";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";

export default function RoundsPage() {
  const { user } = useAuth();
  const { notify } = useToast();

  const [league, setLeague] = useState(null);
  const [rounds, setRounds] = useState([]);
  const [leg, setLeg] = useState("all");
  const [mine, setMine] = useState(false);
  const [selectedRound, setSelectedRound] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const load = useCallback(
    async ({ silent = false } = {}) => {
      if (!silent) setLoading(true);
      setError(false);
      try {
        const [roundsResponse, leagueResponse] = await Promise.all([
          leagueApi.getRounds({ leg: leg === "all" ? undefined : leg, mine }),
          leagueApi.getLeague(),
        ]);
        setRounds(roundsResponse.data);
        setLeague(leagueResponse.data);
      } catch {
        setError(true);
      } finally {
        if (!silent) setLoading(false);
      }
    },
    [leg, mine],
  );

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    setSelectedRound(null);
  }, [leg, mine]);

  const currentRound = league?.current_round;
  const activeRound = useMemo(() => {
    if (rounds.length === 0) return null;
    return (
      rounds.find((round) => round.number === selectedRound) ||
      rounds.find((round) => round.number === currentRound) ||
      rounds[0]
    );
  }, [rounds, selectedRound, currentRound]);

  const runAction = useCallback(
    async (request) => {
      const { data } = await request();
      notify(data.message, "success");
      await load({ silent: true });
    },
    [load, notify],
  );

  const handleReport = (match, home, away) =>
    runAction(() => leagueApi.reportResult(match.id, home, away));
  const handleCorrect = (match, home, away, note) =>
    runAction(() => leagueApi.correctResult(match.id, home, away, note));
  const handleKickoff = (match, kickoffAt) =>
    runAction(() => leagueApi.updateKickoff(match.id, kickoffAt));
  const handleContest = (match, reason) =>
    runAction(() => leagueApi.contestResult(match.id, reason));
  const handleConfirm = (match) => runAction(() => leagueApi.confirmResult(match.id));

  if (loading) return <LoadingState label="Carregando as rodadas..." />;
  if (error) return <ErrorState onRetry={() => load()} />;

  return (
    <div className="page">
      <section className="page-head">
        <div>
          <p className="eyebrow">Calendário</p>
          <h1 className="page-title">Rodadas</h1>
          <p className="page-subtitle">
            Confira os confrontos, agende datas e registre os resultados.
          </p>
        </div>
        {league && <StatusBadge status={league.status} />}
      </section>

      {rounds.length === 0 ? (
        <EmptyState
          icon="⚽"
          title="Os confrontos ainda não foram gerados"
          description={
            league?.players_count
              ? `${league.players_count} jogador(es) já estão inscritos. Aguarde o administrador gerar os confrontos.`
              : "Assim que houver jogadores inscritos, o administrador poderá gerar os confrontos."
          }
          action={
            !user && (
              <Link to="/cadastro" className="button">
                Inscrever-se na liga
              </Link>
            )
          }
        />
      ) : (
        <>
          <section className="rounds-toolbar" aria-label="Filtros de rodadas">
            <div className="tabs" role="tablist" aria-label="Turno">
              {[
                { value: "all", label: "Todos" },
                { value: 1, label: "1º turno" },
                { value: 2, label: "2º turno" },
              ].map((option) => (
                <button
                  key={option.value}
                  type="button"
                  role="tab"
                  aria-selected={leg === option.value}
                  className={`tab${leg === option.value ? " active" : ""}`}
                  onClick={() => setLeg(option.value)}
                >
                  {option.label}
                </button>
              ))}
            </div>

            <label className="switch">
              <input
                type="checkbox"
                checked={mine}
                onChange={(event) => setMine(event.target.checked)}
              />
              <span className="switch-track" aria-hidden="true">
                <span className="switch-thumb" />
              </span>
              <span>Minhas partidas</span>
            </label>
          </section>

          {user && mine && rounds.length === 0 ? (
            <EmptyState
              icon="🔎"
              title="Nenhuma partida sua neste filtro"
              description="Tente outro turno ou desative o filtro “Minhas partidas”."
            />
          ) : rounds.length === 0 ? (
            <EmptyState
              icon="🔎"
              title="Nenhuma partida neste turno"
              description="Escolha outro turno para ver as partidas."
            />
          ) : (
            <>
              <div className="round-chips" role="group" aria-label="Escolher rodada">
                {rounds.map((round) => {
                  const isCurrent = round.number === currentRound;
                  const isActive = activeRound?.number === round.number;
                  const isLocked = round.state === "locked";
                  return (
                    <button
                      key={round.id}
                      type="button"
                      className={`round-chip${isActive ? " active" : ""}${isCurrent ? " current" : ""}${isLocked ? " is-locked" : ""}`}
                      onClick={() => setSelectedRound(round.number)}
                      aria-pressed={isActive}
                      title={
                        isLocked
                          ? "Rodada bloqueada: todas as partidas da rodada anterior precisam ser encerradas primeiro."
                          : isCurrent
                            ? "Rodada atual"
                            : undefined
                      }
                    >
                      {isCurrent && <span className="current-dot" aria-hidden="true" />}
                      {isLocked && (
                        <span className="round-lock" aria-label="Rodada bloqueada">
                          🔒
                        </span>
                      )}
                      <span>R{round.number}</span>
                      <small>{round.leg === 1 ? "1º" : "2º"}</small>
                    </button>
                  );
                })}
              </div>

              {activeRound && (
                <section className="round-section" aria-label={`Rodada ${activeRound.number}`}>
                  <header className="round-header">
                    <h2>
                      Rodada {activeRound.number}
                      <span className="round-leg">{activeRound.leg_label}</span>
                    </h2>
                    <span className="round-count">
                      {activeRound.matches.length} partida
                      {activeRound.matches.length === 1 ? "" : "s"}
                    </span>
                  </header>

                  {activeRound.state === "locked" && (
                    <div className="notice notice-warning" role="status">
                      <strong>Rodada bloqueada.</strong>
                      <span>
                        Só é possível lançar resultados depois que todas as partidas da rodada
                        anterior forem encerradas. Alterar a data continua liberado.
                      </span>
                    </div>
                  )}

                  <div className="match-list">
                    {activeRound.matches.map((match) => (
                      <MatchCard
                        key={match.id}
                        match={match}
                        user={user}
                        onReport={handleReport}
                        onCorrect={handleCorrect}
                        onKickoff={handleKickoff}
                        onContest={handleContest}
                        onConfirm={handleConfirm}
                      />
                    ))}
                  </div>
                </section>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}
