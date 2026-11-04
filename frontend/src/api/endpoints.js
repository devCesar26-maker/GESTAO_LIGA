import { api } from "./client";

export const authApi = {
  csrf: () => api.get("/auth/csrf/", { __silent: true }),
  login: (email, password) => api.post("/auth/login/", { email, password }),
  register: (payload) => api.post("/auth/register/", payload),
  logout: () => api.post("/auth/logout/", {}, { __silent: true }),
  // The session is discovered by asking the API; 401 simply means "visitor".
  me: () => api.get("/auth/me/", { __silent: true }),
  updateProfile: (payload) => api.patch("/auth/me/", payload),
  requestPasswordReset: (email) =>
    api.post("/auth/password-reset/", { email }, { __silent: true }),
  confirmPasswordReset: (payload) =>
    api.post("/auth/password-reset/confirm/", payload, { __silent: true }),
};

export const leagueApi = {
  getLeague: () => api.get("/league/"),
  getParticipants: () => api.get("/participants/"),
  getStandings: () => api.get("/standings/"),
  getRounds: ({ leg, mine } = {}) => {
    const params = {};
    if (leg) params.leg = leg;
    if (mine) params.mine = 1;
    return api.get("/rounds/", { params });
  },
  getMatches: (params = {}) => api.get("/matches/", { params }),
  reportResult: (matchId, homeGoals, awayGoals) =>
    api.post(`/matches/${matchId}/result/`, {
      home_goals: homeGoals,
      away_goals: awayGoals,
    }),
  correctResult: (matchId, homeGoals, awayGoals, note) =>
    api.patch(`/matches/${matchId}/result/`, {
      home_goals: homeGoals,
      away_goals: awayGoals,
      note,
    }),
  updateKickoff: (matchId, kickoffAt) =>
    api.patch(`/matches/${matchId}/kickoff/`, { kickoff_at: kickoffAt }),
  contestResult: (matchId, reason) =>
    api.post(`/matches/${matchId}/contest/`, { reason }),
  confirmResult: (matchId) => api.post(`/matches/${matchId}/confirm/`),
  registerWalkover: (matchId, absentSide) =>
    api.post(`/matches/${matchId}/walkover/`, { absent_side: absentSide }),
  updateLeagueName: (name) => api.patch("/admin/league/", { name }),
  updateLeagueMode: (singleRoundMode) =>
    api.patch("/admin/league/", { single_round_mode: singleRoundMode }),
  generateFixtures: () => api.post("/admin/generate-fixtures/"),
  resetFixtures: () => api.post("/admin/reset-and-regenerate/"),
  getOverview: () => api.get("/admin/overview/"),
  enrollParticipant: (payload) => api.post("/admin/participants/", payload),
  removeParticipant: (participantId) =>
    api.delete(`/admin/participants/${participantId}/`),
};
