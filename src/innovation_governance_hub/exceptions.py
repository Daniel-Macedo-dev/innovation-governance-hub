class DomainError(Exception):
    """Erro de regra de negócio apresentável ao usuário."""


class GateBlockedError(DomainError):
    def __init__(self, missing: list[str]) -> None:
        self.missing = missing
        super().__init__("Critérios pendentes: " + ", ".join(missing))


class ValidationError(DomainError):
    pass
