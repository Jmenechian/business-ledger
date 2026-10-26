class LedgerError(Exception):
    """A safe Spanish error that can be returned to API clients."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def not_found() -> LedgerError:
    return LedgerError("cliente o movimiento no encontrado", 404)
