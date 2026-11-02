"""Single source of truth for every user-facing API message.

The frontend never shows raw error details: it renders the ``message`` returned
by the API, which always comes from this table. Keeping all copy here makes it
trivial to adjust the tone of the app without touching business logic.
"""

MESSAGES = {
    # --- authentication / authorization -----------------------------------
    "NOT_AUTHENTICATED": "Faça login para continuar.",
    "TOKEN_EXPIRED": "Sua sessão expirou. Entre novamente para continuar.",
    "SESSION_EXPIRED": "Sua sessão expirou. Entre novamente para continuar.",
    "INVALID_TOKEN": "Sua sessão não é mais válida. Entre novamente para continuar.",
    "CSRF_FAILED": (
        "Não foi possível validar sua solicitação. Recarregue a página e tente de novo."
    ),
    "INVALID_CREDENTIALS": "Email ou senha incorretos.",
    "ADMIN_ONLY": "Esta ação é exclusiva do administrador da liga.",
    "FORBIDDEN": "Você não tem permissão para fazer isso.",
    "NOT_MATCH_PARTICIPANT": (
        "Você não pode alterar dados desse confronto, pois não está envolvido nele."
    ),
    "ONLY_WINNER_CAN_REPORT": (
        "Quem registra o resultado é o vencedor da partida. Peça ao seu adversário "
        "para lançar o placar, ou, se houver erro, entre em contato com o administrador."
    ),
    "CANNOT_CONTEST_OWN_RESULT": "Você não pode contestar um resultado que você mesmo registrou.",
    "LOGGED_IN": "Login realizado com sucesso.",
    # --- registration ------------------------------------------------------
    "REGISTRATION_CLOSED": (
        "As inscrições estão encerradas, pois os confrontos já foram gerados. "
        "Fale com o administrador para entrar na liga."
    ),
    "EMAIL_TAKEN": "Este email já está cadastrado. Tente entrar ou recuperar sua senha.",
    "WEAK_PASSWORD": "Sua senha precisa ter pelo menos 8 caracteres e não pode ser óbvia.",
    "USER_NOT_FOUND": "Não encontramos um usuário com este email.",
    "PLAYER_ALREADY_IN_LEAGUE": "Este jogador já está inscrito na liga.",
    "LEAGUE_NOT_OPEN": "A liga não está com inscrições abertas.",
    # --- fixtures ----------------------------------------------------------
    "FIXTURES_ALREADY_GENERATED": "Os confrontos já foram gerados. Nada foi alterado.",
    "FIXTURES_GENERATED": "Confrontos gerados com sucesso!",
    "FIXTURES_REGENERATED": "Confrontos resetados e gerados novamente com sucesso!",
    "FIXTURES_RESET": "Confrontos resetados. Agora você pode gerar novamente.",
    "CANNOT_REGENERATE": (
        "Não é possível regerar os confrontos, pois já existem resultados lançados."
    ),
    "NOT_ENOUGH_PLAYERS": "São necessários pelo menos 2 jogadores para gerar os confrontos.",
    "NO_ACTIVE_LEAGUE": "Nenhuma liga está ativa no momento. Fale com o administrador.",
    "FIXTURE_VALIDATION_FAILED": (
        "Não foi possível validar os confrontos gerados. Nada foi salvo."
    ),
    # --- matches / results --------------------------------------------------
    "MATCH_ALREADY_FINISHED": (
        "Esta partida já foi finalizada, então a data não pode mais ser alterada."
    ),
    "RESULT_ALREADY_REGISTERED": (
        "O resultado desta partida já foi registrado. Se algo estiver errado, "
        "use a opção Contestar."
    ),
    "RESULT_NOT_REGISTERED": "Esta partida ainda não tem resultado para contestar.",
    "CONTEST_WINDOW_CLOSED": (
        "O prazo para contestar este resultado já passou. Fale com o administrador."
    ),
    "CONTEST_ALREADY_REVIEWED": (
        "Este resultado já foi contestado e revisado pelo administrador. "
        "Se ainda houver erro, fale com ele."
    ),
    "INVALID_SCORE": "Informe um placar válido, com números inteiros de 0 a 30.",
    "ROUND_NOT_OPEN": (
        "Você ainda não pode lançar este resultado: todas as partidas da rodada "
        "anterior precisam ser encerradas primeiro."
    ),
    "INVALID_ABSENT_SIDE": (
        "Informe quem não compareceu: o mandante (home) ou o visitante (away)."
    ),
    "WALKOVER_REGISTERED": "W.O. registrado: 3 a 0 para quem compareceu.",
    "LEAGUE_NAME_TAKEN": "Já existe uma liga com este nome. Escolha outro.",
    "INVALID_LEAGUE_NAME": "O nome da liga deve ter entre 3 e 60 caracteres.",
    "INVALID_KICKOFF_DATE": "Informe uma data e hora válidas para a partida.",
    "RESULT_REPORTED": "Resultado registrado com sucesso!",
    "RESULT_CORRECTED": "Resultado corrigido e classificação atualizada.",
    "RESULT_CONFIRMED": "Resultado confirmado. A partida está encerrada.",
    "RESULT_CONTESTED": "Resultado contestado. O administrador foi avisado.",
    "KICKOFF_UPDATED": "Data e hora da partida atualizadas.",
    "NOTHING_CHANGED": "Nada foi alterado.",
    # --- generic -----------------------------------------------------------
    "LOGGED_OUT": "Você saiu da sua conta.",
    "PROFILE_UPDATED": "Perfil atualizado com sucesso.",
    "REGISTERED": "Cadastro realizado com sucesso!",
    "ADDED_TO_LEAGUE": "Jogador inscrito na liga. Gere os confrontos novamente para incluí-lo.",
    "PARTICIPANT_ADDED": "Jogador inscrito na liga com sucesso.",
    "LEAGUE_UPDATED": "Liga atualizada.",
    "INVALID_DATA": "Alguns dados estão inválidos. Revise as informações e tente novamente.",
    "IDEMPOTENCY_KEY_REUSED": (
        "Esta operação já foi enviada com outros dados. Recarregue a página e tente novamente."
    ),
    "METHOD_NOT_ALLOWED": "Esta ação não está disponível aqui.",
    "NOT_FOUND": "Não encontramos o que você procurava.",
    "TOO_MANY_REQUESTS": "Muitas tentativas em pouco tempo. Aguarde um instante e tente novamente.",
    "SERVER_ERROR": "Algo deu errado do nosso lado. Tente novamente em instantes.",
}

DEFAULT_MESSAGE = "Não foi possível concluir a ação. Tente novamente."


def message_for(code: str) -> str:
    """Return the friendly message for an error code."""
    return MESSAGES.get(code, DEFAULT_MESSAGE)
