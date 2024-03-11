from dataclasses import dataclass
from typing import Any
import logging



@dataclass
class GenericSystem:
    global_store: Any
    logger: Any = logging.getLogger('GenericSystem')


