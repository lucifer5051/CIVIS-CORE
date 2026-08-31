from abc import ABC, abstractmethod
from typing import Any
from fastapi import FastAPI


class BaseAPIEngine(ABC):
    """
    Abstract interface for CIVIS External Integration API Gateway.
    """

    @abstractmethod
    def get_app(self) -> FastAPI:
        """Returns the configured FastAPI application instance."""
        pass

    @abstractmethod
    def start(self) -> None:
        """Starts background listeners and services."""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Stops background listeners and services."""
        pass
