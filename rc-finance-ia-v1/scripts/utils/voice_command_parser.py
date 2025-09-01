# PATH BOOTSTRAP
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from datetime import date, timedelta
import re
from typing import Any, Dict, Tuple

class Intent:
    def __init__(self, name: str, data: Dict[str, Any]):
        self.name = name
        self.data = data

    def __repr__(self):
        return f"Intent(name='{self.name}', data={self.data})"

def parse_command(text: str, hoje: date) -> Tuple[str, Dict[str, Any]]:
    text = text.lower()

    # Mapeamento de categorias e sinônimos
    categorias = {
        "alimentacao": ["alimentacao", "alimentação", "comida", "restaurante", "mercado", "supermercado"],
        "transporte": ["transporte", "gasolina", "onibus", "metro", "uber"],
        "aluguel": ["aluguel", "moradia"],
        "salario": ["salario", "pagamento", "recebimento"],
        "bonus": ["bonus"],
        "lazer": ["lazer", "entretenimento", "cinema", "viagem"],
        "saude": ["saude", "medico", "farmacia"],
        "educacao": ["educacao", "escola", "curso"],
        "contas": ["contas", "luz", "agua", "internet", "telefone"],
        "outros": ["outros", "diversos"]
    }

    # Mapeamento de tipos de transação
    tipos_transacao = {
        "despesa": ["gastei", "paguei", "despesa", "tirei"],
        "receita": ["recebi", "caiu", "receita", "coloquei"]
    }

    # Mapeamento de datas
    datas_relativas = {
        "hoje": hoje,
        "ontem": hoje - timedelta(days=1),
        "amanha": hoje + timedelta(days=1),
        "anteontem": hoje - timedelta(days=2),
        "depois de amanha": hoje + timedelta(days=2)
    }

    # Regex para valores monetários (R$ 1.234,56 ou 1234,56 ou 5000)
    valor_regex = r"(?:r\$\s*)?(\d+(?:\.\d{3})*(?:,\d{2})?|\d+(?:,\d{2})?|\d+)"

    # Regex para datas no formato DD/MM/YYYY ou DD de Mes
    data_regex = r"(\d{1,2}/\d{1,2}(?:/\d{2,4})?)|(\d{1,2}\sde\s(?:janeiro|fevereiro|marco|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro))"

    # Funções auxiliares para extração
    def extract_value(text_to_parse: str) -> float | None:
        match = re.search(valor_regex, text_to_parse)
        if match:
            value_str = match.group(1)
            # Remove ponto de milhar e troca vírgula por ponto para converter para float
            # Verifica se o valor tem vírgula como separador decimal
            if ',' in value_str and '.' in value_str:
                # Se tiver ambos, assume que o ponto é separador de milhar e a vírgula é decimal
                return float(value_str.replace(".", "").replace(",", "."))
            elif ',' in value_str:
                # Se tiver apenas vírgula, assume que é o separador decimal
                return float(value_str.replace(",", "."))
            else:
                # Se não tiver vírgula, assume que é ponto decimal ou inteiro
                return float(value_str)
        return None

    def extract_category(text_to_parse: str) -> str | None:
        for cat, synonyms in categorias.items():
            for syn in synonyms:
                if syn in text_to_parse:
                    return cat
        return "outros"

    def extract_type(text_to_parse: str) -> str | None:
        for tipo, synonyms in tipos_transacao.items():
            for syn in synonyms:
                if syn in text_to_parse:
                    return tipo
        return None

    def extract_date(text_to_parse: str, base_date: date) -> date | None:
        for rel_date_str, rel_date_obj in datas_relativas.items():
            if rel_date_str in text_to_parse:
                return rel_date_obj
        
        # Tentar parsing de datas absolutas (DD/MM/YYYY ou DD de Mes)
        match = re.search(data_regex, text_to_parse)
        if match:
            date_str = match.group(0)
            try:
                if '/' in date_str:
                    parts = date_str.split('/')
                    day = int(parts[0])
                    month = int(parts[1])
                    year = int(parts[2]) if len(parts) > 2 else base_date.year
                    return date(year, month, day)
                elif 'de' in date_str:
                    parts = date_str.split(' de ')
                    day = int(parts[0])
                    month_name = parts[1]
                    month_map = {
                        "janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5, "junho": 6,
                        "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12
                    }
                    month = month_map.get(month_name)
                    if month:
                        return date(base_date.year, month, day)
            except ValueError:
                pass
        
        # Dias da semana próximos
        dias_semana = {
            "segunda": 0, "terca": 1, "quarta": 2, "quinta": 3, "sexta": 4, "sabado": 5, "domingo": 6
        }
        for dia_str, dia_num in dias_semana.items():
            if dia_str in text_to_parse:
                # Encontrar o próximo dia da semana
                days_ahead = (dia_num - base_date.weekday() + 7) % 7
                if days_ahead == 0: # Se for o mesmo dia da semana, assume a próxima ocorrência
                    days_ahead = 7
                return base_date + timedelta(days=days_ahead)

        return None

    # Intenção: AddTransaction
    if any(word in text for word in ["gastei", "paguei", "recebi", "caiu", "adicionar", "lancar", "registrar"]):
        amount = extract_value(text)
        category = extract_category(text)
        transaction_date = extract_date(text, hoje)
        transaction_type = extract_type(text)
        description = text # Por simplicidade, a descrição é o texto completo por enquanto

        return "AddTransaction", {
            "amount": amount,
            "category": category,
            "date": transaction_date.isoformat() if transaction_date else None,
            "description": description,
            "type": transaction_type
        }

    # Intenção: ExportReport
    if any(word in text for word in ["exportar", "relatorio", "baixar"]):
        start_date = None
        end_date = None
        categories = []
        report_format = "csv" # Padrão

        # Extrair datas
        match_periodo = re.search(r"de (.+?) ate (.+)", text)
        if match_periodo:
            start_date = extract_date(match_periodo.group(1), hoje)
            end_date = extract_date(match_periodo.group(2), hoje)
        else:
            # Tentar extrair mês/ano ou período padrão
            match_mes_ano = re.search(r"(janeiro|fevereiro|marco|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)(?: de (\d{4}))?", text)
            if match_mes_ano:
                month_name = match_mes_ano.group(1)
                year = int(match_mes_ano.group(2)) if match_mes_ano.group(2) else hoje.year
                month_map = {
                    "janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5, "junho": 6,
                    "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12
                }
                month = month_map.get(month_name)
                if month:
                    start_date = date(year, month, 1)
                    # Último dia do mês
                    if month == 12:
                        end_date = date(year, month, 31)
                    else:
                        end_date = date(year, month + 1, 1) - timedelta(days=1)
            else:
                # Padrão: mês atual
                start_date = date(hoje.year, hoje.month, 1)
                end_date = hoje

        # Extrair categorias
        for cat_canonical, cat_synonyms in categorias.items():
            for syn in cat_synonyms:
                if syn in text:
                    categories.append(cat_canonical)
        categories = list(set(categories)) # Remover duplicatas

        # Extrair formato
        if "excel" in text or "xlsx" in text:
            report_format = "xlsx"
        elif "csv" in text:
            report_format = "csv"

        return "ExportReport", {
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
            "categories": categories,
            "format": report_format
        }

    # Intenção: CreateGoal
    if any(word in text for word in ["criar meta", "definir meta"]):
        name_match = re.search(r"meta (.+?) de (.+?)(?: ate (.+)|$)", text)
        if name_match:
            name = name_match.group(1).strip()
            target_amount = extract_value(name_match.group(2))
            due_date = extract_date(name_match.group(3), hoje) if name_match.group(3) else None

            return "CreateGoal", {
                "name": name,
                "target_amount": target_amount,
                "due_date": due_date.isoformat() if due_date else None
            }

    # Intenção: EditTransaction (simplificado para o prompt)
    if any(word in text for word in ["editar transacao", "alterar transacao"]):
        # Para simplificar, vamos apenas extrair um ID ou uma descrição para seleção
        # Em um cenário real, precisaríamos de mais lógica para identificar a transação
        selector = {"description": text} # Placeholder
        changes = {"amount": extract_value(text)} # Placeholder

        return "EditTransaction", {
            "selector": selector,
            "changes": changes,
            "needs_disambiguation": False # Por enquanto, assumimos que não precisa
        }

    return "Unknown", {}


if __name__ == "__main__":
    today = date(2025, 8, 29) # Data fixa para testes

    print("--- Testes AddTransaction ---")
    print(parse_command("gastei 25,50 em alimentação hoje, almoço.", today))
    print(parse_command("recebi 1200 de salario ontem", today))
    print(parse_command("paguei 50 reais de transporte na terca", today))

    print("\n--- Testes ExportReport ---")
    print(parse_command("Exportar relatório de julho em excel, apenas despesas de transporte.", today))
    print(parse_command("Baixar relatório de 01/08/2025 ate 29/08/2025, categorias alimentacao e transporte, em csv", today))
    print(parse_command("Exportar relatório", today))

    print("\n--- Testes CreateGoal ---")
    print(parse_command("criar meta viagem de 5000 ate 31/12/2025", today))
    print(parse_command("definir meta carro de 20000", today))

    print("\n--- Testes EditTransaction ---")
    print(parse_command("editar transacao de ontem em mercado para 30 reais", today))




