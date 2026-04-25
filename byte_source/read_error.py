# System imports

# External imports

# User imports

#########################

class ReadError(IOError):
    """Исключение, возникающее при ошибке чтения байта из источника данных.

    Является базовым для всех ошибок, связанных с чтением. Наследники могут
    добавлять специфику для разных типов источников.

    Attributes:
        original_exception (Exception | None): Исходное исключение, если ошибка
            возникла при обработке низкоуровневого ввода-вывода.
    """

    def __init__(self, message: str, original_exception: Exception = None):
        """
        Args:
            message (str): Описание ошибки.
            original_exception (Exception, optional): Исходное исключение,
                ставшее причиной ошибки. По умолчанию None.
        """
        super().__init__(message)
        self.original_exception = original_exception