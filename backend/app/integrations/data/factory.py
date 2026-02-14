"""Data provider factory."""

from app.integrations.data.base import DataProvider


def get_data_provider(
    source: str = "yahoo",
    app_key: str = "",
    app_secret: str = "",
    account_number: str = "",
    is_paper: bool = True,
) -> DataProvider:
    """Create a data provider instance.

    Args:
        source: Provider name ("yahoo" or "kis")
        app_key: KIS API key (only for KIS provider)
        app_secret: KIS API secret (only for KIS provider)
        account_number: KIS account number (only for KIS provider)
        is_paper: Paper trading mode (only for KIS provider)

    Returns:
        DataProvider instance
    """
    if source == "kis":
        from app.integrations.data.kis_provider import KISDataProvider
        return KISDataProvider(
            app_key=app_key,
            app_secret=app_secret,
            account_number=account_number,
            is_paper=is_paper,
        )
    elif source == "yahoo":
        from app.integrations.data.yahoo_provider import YahooDataProvider
        return YahooDataProvider()
    else:
        raise ValueError(f"Unknown data source: {source}. Supported: 'yahoo', 'kis'")
