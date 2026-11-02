export default function StandingsTable({ rows, user }) {
  return (
    <div className="table-wrap" role="region" aria-label="Tabela de classificação" tabIndex="0">
      <table className="standings-table">
        <caption className="sr-only">
          Classificação da liga: posição, time, jogos, vitórias, empates, derrotas, gols pró,
          gols contra, saldo de gols e pontos.
        </caption>
        <thead>
          <tr>
            <th scope="col">Pos</th>
            <th scope="col">Time</th>
            <th scope="col" title="Jogos">J</th>
            <th scope="col" title="Vitórias">V</th>
            <th scope="col" title="Empates">E</th>
            <th scope="col" title="Derrotas">D</th>
            <th scope="col" title="Gols pró" className="col-detail">
              GP
            </th>
            <th scope="col" title="Gols contra" className="col-detail">
              GC
            </th>
            <th scope="col" title="Saldo de gols">SG</th>
            <th scope="col" title="Pontos">Pts</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const isMine = Boolean(user && row.user_id === user.id);
            return (
              <tr
                key={row.participant_id}
                className={`${isMine ? "is-mine" : ""}${row.position === 1 ? " is-leader" : ""}`}
              >
                <td className="position-cell">
                  <span className="position-number">{row.position}</span>
                  {row.position === 1 && (
                    <span className="leader-crown" aria-label="Líder" title="Líder da liga">
                      ♛
                    </span>
                  )}
                </td>
                <th scope="row" className="team-cell">
                  <span className="standings-team">{row.team_name}</span>
                  <span className="standings-player">
                    {row.player_name}
                    {isMine && <span className="you-tag">você</span>}
                  </span>
                </th>
                <td>{row.played}</td>
                <td>{row.wins}</td>
                <td>{row.draws}</td>
                <td>{row.losses}</td>
                <td className="col-detail">{row.goals_for}</td>
                <td className="col-detail">{row.goals_against}</td>
                <td className={row.goal_difference > 0 ? "positive" : row.goal_difference < 0 ? "negative" : ""}>
                  {row.goal_difference > 0 ? `+${row.goal_difference}` : row.goal_difference}
                </td>
                <td className="points-cell">{row.points}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
