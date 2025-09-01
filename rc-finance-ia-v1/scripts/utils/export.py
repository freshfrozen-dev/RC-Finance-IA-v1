
import sys
from pathlib import Path

# PATH BOOTSTRAP
# Adiciona o diretório raiz do projeto ao sys.path para que os módulos possam ser encontrados
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))

import pandas as pd
from io import BytesIO
import logging
from datetime import datetime

# Configurar logging básico
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def export_df_csv(df: pd.DataFrame) -> tuple[str, bytes, str]:
    """Exporta um DataFrame para CSV com codificação UTF-8 com BOM e sem índice."""
    logger.info("Exportando DataFrame para CSV.")
    try:
        # Lidar com DF vazio: retornar arquivo válido com apenas cabeçalhos.
        if df.empty:
            output = BytesIO()
            # Criar um DataFrame com as colunas esperadas para o cabeçalho
            empty_df_with_cols = pd.DataFrame(columns=["date", "description", "category", "type", "amount"])
            empty_df_with_cols.to_csv(output, index=False, sep=",", encoding="utf-8-sig")
            logger.info("DataFrame vazio exportado para CSV com cabeçalhos.")
            filename = f"relatorio_{datetime.now().strftime('%Y%m%d')}.csv"
            return filename, output.getvalue(), "text/csv"

        output = BytesIO()
        df.to_csv(output, index=False, sep=",", encoding="utf-8-sig")
        logger.info("DataFrame exportado para CSV com sucesso.")
        filename = f"relatorio_{datetime.now().strftime('%Y%m%d')}.csv"
        return filename, output.getvalue(), "text/csv"
    except Exception as e:
        logger.error(f"Erro ao exportar DataFrame para CSV: {e}")
        raise

def export_df_excel(df: pd.DataFrame) -> tuple[str, bytes, str]:
    """Exporta um DataFrame para um arquivo Excel com uma aba."""
    logger.info("Exportando DataFrame para Excel.")
    try:
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            # Para garantir que colunas com None sejam tratadas como object e não float64
            # Convertendo colunas com todos os valores None/NaN para o tipo object
            for col in df.columns:
                if df[col].isnull().all():
                    df[col] = df[col].astype(object)

            # Lidar com DF vazio: retornar arquivo válido com apenas cabeçalhos.
            if df.empty:
                empty_df_with_cols = pd.DataFrame(columns=["date", "description", "category", "type", "amount"])
                empty_df_with_cols.to_excel(writer, sheet_name="Sheet1", index=False)
                logger.info(f"DataFrame vazio exportado para Excel com cabeçalhos.")
            else:
                df.to_excel(writer, sheet_name="Sheet1", index=False)
                logger.info(f"DataFrame exportado para Excel com sucesso.")
        logger.info("DataFrame exportado para Excel com sucesso.")
        filename = f"relatorio_{datetime.now().strftime('%Y%m%d')}.xlsx"
        return filename, output.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    except Exception as e:
        logger.error(f"Erro ao exportar DataFrame para Excel: {e}")
        raise


