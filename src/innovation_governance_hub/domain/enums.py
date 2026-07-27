from enum import StrEnum


class Stage(StrEnum):
    IDEA = "Ideia"
    SCREENING = "Triagem"
    DISCOVERY = "Descoberta"
    VALIDATION = "Validação"
    PILOT = "Piloto"
    SCALE = "Escala"
    COMPLETED = "Concluída"
    ARCHIVED = "Arquivada"


STAGE_ORDER = list(Stage)


class InitiativeStatus(StrEnum):
    ACTIVE = "Ativa"
    ON_HOLD = "Em espera"
    BLOCKED = "Bloqueada"
    COMPLETED = "Concluída"
    ARCHIVED = "Arquivada"


class EvaluationType(StrEnum):
    AUTOMATIC = "Automática"
    MANUAL = "Manual"
    APPROVAL = "Aprovação"


class FinancialStatus(StrEnum):
    ACTUAL = "Realizado"
    FORECAST = "Previsto"


class AIStatus(StrEnum):
    DRAFT = "Rascunho"
    EVALUATING = "Em avaliação"
    APPROVED = "Aprovado"
    RESTRICTED = "Aprovado com restrições"
    REJECTED = "Rejeitado"
    SUSPENDED = "Suspenso"
    REVIEW = "Em revisão"


class RiskLevel(StrEnum):
    LOW = "Baixo"
    MEDIUM = "Médio"
    HIGH = "Alto"
    CRITICAL = "Crítico"
