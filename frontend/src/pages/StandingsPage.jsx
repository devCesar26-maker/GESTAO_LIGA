import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { leagueApi } from "../api/endpoints";
import { EmptyState, ErrorState, LoadingState } from "../components/PageState";
import StandingsTable from "../components/StandingsTable";
import StatusBadge from "../components/StatusBadge";
import { useAuth } from "../context/AuthContext";

export default function StandingsPage() {
  const { user } = useAuth();
  const [league, setLeague] = useState(null);
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(false);
    try {
      const [leagueResponse, standingsResponse] = await Promise.all([
        leagueApi.getLeague(),
        leagueApi.getStandings(),
      ]);
      setLeague(leagueResponse.data);
      setRows(standingsResponse.data);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) return <LoadingState label="Carregando a classificação..." />;
  if (error) return <ErrorState onRetry={load} />;

  return (
    <div className="page">
      <section className="page-hero">
        <div>
          <p className="eyebrow">Temporada atual</p>
          <h1 className="page-title">{league?.name || "Liga eFootball"}</h1>
          <div className="hero-meta">
            {league && <StatusBadge status={league.status} />}
            <span className="meta-chip">{league?.players_count ?? 0} jogadores</span>
            <span className="meta-chip">{league?.rounds_count ?? 0} rodadas</span>
            <span className="meta-chip">{league?.matches_count ?? 0} partidas</span>
          </div>
        </div>
        <div className="hero-callout">
          <span className="hero-callout-label">Rodada atual</span>
          <strong>{league?.current_round ?? "—"}</strong>
          <Link to="/rodadas" className="button button-small button-ghost">
            Ver rodadas
          </Link>
        </div>
      </section>

      {!league?.fixtures_generated_at && (
        <div className="notice notice-info">
          <strong>Os confrontos ainda não foram gerados.</strong>
          <span>
            {league?.players_count ?? 0} jogador(es) inscrito(s). Assim que o administrador gerar
            os confrontos, a liga começa.
          </span>
          {!user && (
            <Link to="/cadastro" className="button button-small">
              Inscrever-se
            </Link>
          )}
          {user?.is_staff && (
            <Link to="/admin" className="button button-small">
              Ir para o painel admin
            </Link>
          )}
        </div>
      )}

      <section className="panel">
        <header className="panel-head">
          <h2>Tabela de classificação</h2>
          <p className="panel-subtitle">Atualizada automaticamente a cada resultado registrado.</p>
        </header>

        {rows.length === 0 ? (
          <EmptyState
            icon="🏟️"
            title="Nenhum jogador inscrito ainda"
            description="Compartilhe o link com seus amigos para começar a liga."
            action={
              !user && (
                <Link to="/cadastro" className="button">
                  Criar minha conta
                </Link>
              )
            }
          />
        ) : (
          <>
            <StandingsTable rows={rows} user={user} />
            <p className="panel-footnote">
              Critérios de desempate: pontos, vitórias, saldo de gols, gols pró e, por último, o
              nome do time.
            </p>
          </>
        )}
      </section>
    </div>
  );
}
