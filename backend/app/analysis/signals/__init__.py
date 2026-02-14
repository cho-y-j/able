# Import all signal modules to trigger @register_signal decorators
from app.analysis.signals import trend_signals  # noqa: F401
from app.analysis.signals import momentum_signals  # noqa: F401
from app.analysis.signals import volatility_signals  # noqa: F401
from app.analysis.signals import composite_signals  # noqa: F401

from app.analysis.signals.registry import (  # noqa: F401
    get_signal_generator,
    get_signal_param_space,
    list_signal_generators,
    list_signal_generators_by_category,
)
