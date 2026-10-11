class ApplicationError(Exception):
    code = "application_error"

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class OrderNotFound(ApplicationError):
    code = "order_not_found"
