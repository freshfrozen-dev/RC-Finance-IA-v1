# scripts/utils/projections_simple.py
# Versão simplificada sem statsmodels

import pandas as pd
from datetime import datetime, timedelta

def monthly_aggregate(df: pd.DataFrame) -> pd.DataFrame:
    """
    Agrega transações por mês.
    """
    if df.empty:
        return pd.DataFrame()
    
    # Garantir que a coluna date é datetime
    df = df.copy()
    df['date'] = pd.to_datetime(df['date'])
    
    # Agrupar por mês
    df['month'] = df['date'].dt.to_period('M')
    
    monthly = df.groupby(['month', 'type'])['amount'].sum().unstack(fill_value=0)
    
    # Garantir que temos as colunas income e expense
    if 'income' not in monthly.columns:
        monthly['income'] = 0
    if 'expense' not in monthly.columns:
        monthly['expense'] = 0
    
    monthly['balance'] = monthly['income'] - monthly['expense']
    
    return monthly

def forecast_balance(monthly_df: pd.DataFrame) -> pd.DataFrame:
    """
    Projeção simples de saldo baseada na média dos últimos meses.
    """
    if monthly_df.empty or len(monthly_df) < 2:
        return pd.DataFrame()
    
    # Calcular média dos últimos 3 meses (ou todos se menos de 3)
    last_months = min(3, len(monthly_df))
    avg_income = monthly_df['income'].tail(last_months).mean()
    avg_expense = monthly_df['expense'].tail(last_months).mean()
    avg_balance = avg_income - avg_expense
    
    # Projetar próximos 6 meses
    last_date = monthly_df.index[-1]
    forecast_dates = []
    for i in range(1, 7):
        next_month = last_date + i
        forecast_dates.append(next_month)
    
    # Calcular saldo acumulado
    current_balance = monthly_df['balance'].cumsum().iloc[-1]
    forecast_data = []
    
    for i, date in enumerate(forecast_dates):
        projected_balance = current_balance + (avg_balance * (i + 1))
        forecast_data.append({
            'month': date,
            'balance_forecast': projected_balance
        })
    
    forecast_df = pd.DataFrame(forecast_data)
    forecast_df.set_index('month', inplace=True)
    
    return forecast_df

