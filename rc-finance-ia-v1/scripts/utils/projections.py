
import pandas as pd
import numpy as np
import logging
from statsmodels.tsa.holtwinters import ExponentialSmoothing

# Configurar logging básico
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def monthly_aggregate(df: pd.DataFrame, date_col: str = 'date') -> pd.DataFrame:
    """Agrega transações mensalmente para calcular receita, despesa e saldo."""
    logger.info(f"Agregando dados mensalmente usando a coluna de data: {date_col}")
    
    if df.empty:
        logger.warning("DataFrame de entrada vazio para agregação mensal.")
        return pd.DataFrame(columns=['income', 'expense', 'balance'])

    # Garante que a coluna de data é datetime
    df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
    df = df.dropna(subset=[date_col])

    if df.empty:
        logger.warning("DataFrame vazio após conversão de data e remoção de NaNs.")
        return pd.DataFrame(columns=['income', 'expense', 'balance'])

    # Define o mês como o índice
    df['month'] = df[date_col].dt.to_period('M')
    
    # Calcula receita e despesa
    df_income = df[df['type'] == 'income'].groupby('month')['amount'].sum()
    df_expense = df[df['type'] == 'expense'].groupby('month')['amount'].sum()

    # Combina em um único DataFrame
    monthly_df = pd.DataFrame({
        'income': df_income,
        'expense': df_expense
    }).fillna(0)

    # Calcula o saldo
    monthly_df['balance'] = monthly_df['income'] - monthly_df['expense']

    # Garante índice mensal contínuo
    if not monthly_df.empty:
        min_month = monthly_df.index.min()
        max_month = monthly_df.index.max()
        full_month_range = pd.period_range(start=min_month, end=max_month, freq='M')
        monthly_df = monthly_df.reindex(full_month_range, fill_value=0)

    logger.info("Agregação mensal concluída com sucesso.")
    return monthly_df

def forecast_balance(monthly: pd.DataFrame, horizon: int = 3) -> pd.DataFrame:
    """Projeta o saldo futuro usando Exponential Smoothing ou regressão linear como fallback."""
    logger.info(f"Iniciando projeção de saldo para {horizon} meses.")

    if monthly.empty or len(monthly) < 2: # Mínimo de 2 pontos para regressão linear
        logger.warning("Dados insuficientes para projeção. Retornando DataFrame vazio.")
        return pd.DataFrame(columns=['balance_forecast'])

    # Converte o índice PeriodIndex para DatetimeIndex para statsmodels
    monthly_dt_index = monthly.index.to_timestamp()
    monthly_series = pd.Series(monthly['balance'].values, index=monthly_dt_index)

    # Tenta Exponential Smoothing
    try:
        if len(monthly_series) >= 4: # Mínimo de 4 pontos para Exponential Smoothing
            logger.info("Tentando projeção com Exponential Smoothing.")
            model = ExponentialSmoothing(monthly_series, trend='add', seasonal=None, initialization_method="estimated").fit()
            forecast = model.forecast(horizon)
            logger.info("Projeção com Exponential Smoothing concluída com sucesso.")
        else:
            raise ValueError("Dados insuficientes para Exponential Smoothing, usando fallback.")
    except Exception as e:
        logger.warning(f"Erro ao usar Exponential Smoothing ({e}). Usando regressão linear como fallback.")
        # Fallback para regressão linear
        x = np.arange(len(monthly_series))
        y = monthly_series.values
        
        # Adiciona um pequeno valor para evitar problemas com log de zero ou valores muito pequenos
        # Isso é mais uma precaução geral, mas para regressão linear não é estritamente necessário
        # No entanto, se os dados forem muito pequenos, pode causar problemas de precisão
        # Não é aplicável aqui, mas mantido como um lembrete de boas práticas para outros modelos

        # Regressão linear
        try:
            coeffs = np.polyfit(x, y, 1) # Polinômio de grau 1 (linear)
            linear_model = np.poly1d(coeffs)
            
            # Gera os pontos futuros para a projeção
            future_x = np.arange(len(monthly_series), len(monthly_series) + horizon)
            forecast = pd.Series(linear_model(future_x), index=pd.date_range(start=monthly_dt_index.max() + pd.DateOffset(months=1), periods=horizon, freq='MS'))
            logger.info("Projeção com regressão linear concluída com sucesso.")
        except Exception as e_linear:
            logger.error(f"Erro ao usar regressão linear como fallback: {e_linear}")
            return pd.DataFrame(columns=['balance_forecast'])

    # Cria DataFrame de projeção
    forecast_df = pd.DataFrame(forecast, columns=['balance_forecast'])
    forecast_df.index = forecast_df.index.to_period('M')
    logger.info("Projeção de saldo concluída.")
    return forecast_df


