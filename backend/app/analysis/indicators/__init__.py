# Import all indicator modules to trigger @register_indicator decorators
from app.analysis.indicators import trend  # noqa: F401
from app.analysis.indicators import momentum  # noqa: F401
from app.analysis.indicators import volatility  # noqa: F401
from app.analysis.indicators import volume  # noqa: F401
from app.analysis.indicators import composite  # noqa: F401
