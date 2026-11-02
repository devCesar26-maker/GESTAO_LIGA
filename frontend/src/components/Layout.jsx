import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";

import { leagueApi } from "../api/endpoints";
import { useAuth } from "../context/AuthContext";

const THEME_KEY = "liga.theme";
const DEFAULT_LEAGUE_NAME = "Liga eFootball";

function navClass({ isActive }) {
  return `nav-link${isActive ? " active" : ""}`;
}

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [theme, setTheme] = useState(() => localStorage.getItem(THEME_KEY) || "dark");
  const [leagueName, setLeagueName] = useState(DEFAULT_LEAGUE_NAME);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem(THEME_KEY, theme);
  }, [theme]);

  useEffect(() => {
    let active = true;

    const loadName = () =>
      leagueApi
        .getLeague()
        .then((response) => {
          if (active) setLeagueName(response.data?.name || DEFAULT_LEAGUE_NAME);
        })
        .catch(() => {
          // Keep the default name when the league is unreachable.
        });

    loadName();
    // The admin panel announces a rename so the header updates immediately.
    const onLeagueUpdated = () => loadName();
    window.addEventListener("liga:updated", onLeagueUpdated);
    return () => {
      active = false;
      window.removeEventListener("liga:updated", onLeagueUpdated);
    };
  }, []);

  useEffect(() => {
    document.title = leagueName;
  }, [leagueName]);

  const handleLogout = async () => {
    await logout();
    navigate("/", { replace: true });
  };

  return (
    <div className="app-shell">
      <a className="skip-link" href="#conteudo">
        Ir para o conteúdo
      </a>

      <header className="app-header">
        <div className="header-inner">
          <Link className="brand" to="/" aria-label={`${leagueName} — início`}>
            <span className="brand-ball" aria-hidden="true">
              ⚽
            </span>
            <span className="brand-text">{leagueName}</span>
          </Link>

          <nav className="desktop-nav" aria-label="Navegação principal">
            <NavLink to="/" end className={navClass}>
              Classificação
            </NavLink>
            <NavLink to="/rodadas" className={navClass}>
              Rodadas
            </NavLink>
            {user ? (
              <>
                <NavLink to="/perfil" className={navClass}>
                  Perfil
                </NavLink>
                {user.is_staff && (
                  <NavLink to="/admin" className={navClass}>
                    Admin
                  </NavLink>
                )}
              </>
            ) : null}
          </nav>

          <div className="header-actions">
            <button
              type="button"
              className="icon-button"
              onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
              aria-label={theme === "dark" ? "Ativar tema claro" : "Ativar tema escuro"}
              title={theme === "dark" ? "Tema claro" : "Tema escuro"}
            >
              {theme === "dark" ? "☀️" : "🌙"}
            </button>

            {user ? (
              <div className="user-chip">
                <span className="user-chip-name">{user.team_name || user.name}</span>
                <button type="button" className="link-button" onClick={handleLogout}>
                  Sair
                </button>
              </div>
            ) : (
              <Link className="button button-small" to="/login">
                Entrar
              </Link>
            )}
          </div>
        </div>
      </header>

      <main id="conteudo" className="app-main">
        <Outlet />
      </main>

      <nav className="bottom-nav" aria-label="Navegação principal no celular">
        <NavLink to="/" end className={navClass}>
          <span aria-hidden="true">🏆</span>
          <span>Classificação</span>
        </NavLink>
        <NavLink to="/rodadas" className={navClass}>
          <span aria-hidden="true">📅</span>
          <span>Rodadas</span>
        </NavLink>
        {user ? (
          <NavLink to="/perfil" className={navClass}>
            <span aria-hidden="true">👤</span>
            <span>Perfil</span>
          </NavLink>
        ) : (
          <NavLink to="/login" className={navClass}>
            <span aria-hidden="true">👤</span>
            <span>Entrar</span>
          </NavLink>
        )}
        {user?.is_staff && (
          <NavLink to="/admin" className={navClass}>
            <span aria-hidden="true">⚙️</span>
            <span>Admin</span>
          </NavLink>
        )}
      </nav>

      <footer className="app-footer">
        <p>{leagueName} — resultados lançados manualmente.</p>
        <p className="footer-note">
          Projeto independente, sem fins lucrativos e sem vínculo com a Konami.
        </p>
      </footer>
    </div>
  );
}
