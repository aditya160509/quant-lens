"""Historical attribution using observed daily market macro series."""
from __future__ import annotations

import pandas as pd

from .data_loader import load_macro


def macro_regime_attribution(returns: pd.Series) -> pd.DataFrame:
    """Attribute realized returns to the preceding calendar day's VIX state.

    The fixed 20 threshold avoids fitting regimes on the evaluation sample.
    Quotes expire after seven calendar days; unavailable states stay explicit.
    Revised monthly economic series are deliberately excluded.
    """
    columns = ['regime', 'sessions', 'compounded_return', 'mean_daily_return']
    if returns.empty:
        return pd.DataFrame(columns=columns)
    source = load_macro()
    if 'vixcls' not in source:
        return pd.DataFrame(columns=columns)
    observations = source[['date', 'vixcls']].dropna().sort_values('date')
    observations['date'] = observations.date.astype('datetime64[ns]')
    if observations.date.duplicated().any():
        raise ValueError('Macro data contains duplicate VIX observation dates')
    daily = returns.rename('return').rename_axis('date').reset_index().sort_values('date')
    daily['date'] = daily.date.astype('datetime64[ns]')
    daily['information_date'] = daily.date - pd.Timedelta(days=1)
    joined = pd.merge_asof(daily, observations.rename(columns={'date': 'observation_date'}),
                           left_on='information_date', right_on='observation_date',
                           tolerance=pd.Timedelta(days=7), direction='backward')
    joined['regime'] = 'unavailable'
    observed = joined.vixcls.notna() & joined.vixcls.gt(0)
    joined.loc[observed & joined.vixcls.lt(20), 'regime'] = 'prior_VIX_below_20'
    joined.loc[observed & joined.vixcls.ge(20), 'regime'] = 'prior_VIX_at_least_20'
    grouped = joined.groupby('regime')['return']
    result = grouped.agg(sessions='count', mean_daily_return='mean')
    result['compounded_return'] = grouped.apply(lambda series: (1 + series).prod() - 1)
    return result.reset_index()[columns]
