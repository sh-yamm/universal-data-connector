from abc import ABC, abstractmethod
from typing import List, Dict, Any


# Every data source (CRM, support, analytics) must implement this interface.
# Keeps the router code clean — it just calls .fetch() without caring what's underneath.
class BaseConnector(ABC):

    @abstractmethod
    def fetch(self, **kwargs) -> List[Dict[str, Any]]:
        pass
