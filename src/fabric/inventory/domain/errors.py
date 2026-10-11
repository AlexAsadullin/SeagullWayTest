class DomainError(Exception):
    code = "domain_error"

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class InvalidValue(DomainError):
    code = "invalid_value"


class NegativeMeters(InvalidValue):
    code = "negative_meters"


class InvalidSku(InvalidValue):
    code = "invalid_sku"


class InsufficientFabric(DomainError):
    code = "insufficient_fabric"


class InvalidOrderStatus(DomainError):
    code = "invalid_order_status"


class SkuMismatch(DomainError):
    code = "sku_mismatch"


class ReservationMismatch(DomainError):
    code = "reservation_mismatch"
