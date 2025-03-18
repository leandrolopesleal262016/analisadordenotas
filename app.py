from flask import Flask, render_template, request
import pandas as pd
import logging
import os
from math import ceil

app = Flask(__name__)

# Configuração do logger
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[
                        logging.FileHandler("app.log", mode='w'),
                        logging.StreamHandler()
                    ])

# Função para formatar números com separadores de milhares e vírgula como separador decimal
def format_currency(value):
    try:
        return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return value

def get_month_name(date_str):
    """Converte a data no formato DD/MM/YYYY para nome do mês e ano"""
    try:
        month_names = {
            '01': 'Janeiro', '02': 'Fevereiro', '03': 'Março',
            '04': 'Abril', '05': 'Maio', '06': 'Junho',
            '07': 'Julho', '08': 'Agosto', '09': 'Setembro',
            '10': 'Outubro', '11': 'Novembro', '12': 'Dezembro'
        }
        _, month, year = date_str.split('/')
        return f"{month_names[month]} {year}"
    except:
        return "Data inválida"

# Registro do filtro personalizado
app.jinja_env.filters['format_currency'] = format_currency

# Variáveis globais
global_summary = []
ranking = []
monthly_totals = {}
total_pages = 1

@app.route('/', methods=['GET', 'POST'])
def index():
    global global_summary, ranking, monthly_totals, total_pages

    error_message = None
    search_query = request.args.get('search', '').lower()
    page = int(request.args.get('page', 1))
    per_page = 50

    logging.info(f"Página atual: {page}, Itens por página: {per_page}")

    if request.method == 'POST' and 'csvFiles' in request.files:
        try:
            csv_files = request.files.getlist('csvFiles')
            if not csv_files:
                error_message = "Nenhum arquivo CSV foi carregado."
                logging.error(error_message)
                return render_template('index.html', summary=[], ranking=ranking, monthly_totals={}, error_message=error_message, search_query=search_query, page=page, total_pages=total_pages)

            df_list = []
            for file in csv_files:
                try:
                    # Leitura do arquivo com a codificação UTF-16
                    df = pd.read_csv(file, encoding='utf-16le', delimiter='\t', quoting=1)
                    
                    # Remover caracteres especiais dos nomes das colunas
                    df.columns = df.columns.str.strip().str.replace('"', '')
                    
                    df_list.append(df)
                    logging.info(f"Arquivo {file.filename} lido com sucesso")
                except Exception as e:
                    error_message = f"Erro ao ler o arquivo {file.filename}: {e}"
                    logging.error(error_message)
                    return render_template('index.html', summary=[], ranking=ranking, monthly_totals={}, error_message=error_message, search_query=search_query, page=page, total_pages=total_pages)

            if df_list:
                try:
                    df = pd.concat(df_list)
                    logging.info("DataFrames concatenados com sucesso.")
                except Exception as e:
                    error_message = f"Erro ao concatenar os dados: {e}"
                    logging.error(error_message)
                    return render_template('index.html', summary=[], ranking=ranking, monthly_totals={}, error_message=error_message, search_query=search_query, page=page, total_pages=total_pages)

                try:
                    # Limpeza e conversão das colunas numéricas
                    df['Valor NF'] = df['Valor NF'].str.strip().str.replace('"', '').str.replace(',', '.').astype(float)
                    df['Créditos'] = df['Créditos'].str.strip().str.replace('"', '').str.replace(',', '.').astype(float)
                    logging.info("Colunas numéricas convertidas com sucesso.")
                except Exception as e:
                    error_message = f"Erro ao converter colunas numéricas: {e}"
                    logging.error(f"Erro detalhado na conversão: {str(e)}")
                    return render_template('index.html', summary=[], ranking=ranking, monthly_totals={}, error_message=error_message, search_query=search_query, page=page, total_pages=total_pages)

                try:
                    # Calcular totais por mês
                    df['Mês'] = df['Data Emissão'].apply(get_month_name)
                    monthly_totals = df.groupby('Mês')['Créditos'].sum().to_dict()
                    monthly_totals = dict(sorted(monthly_totals.items()))

                    # Agrupamento e cálculos
                    summary = df.groupby(['Emitente', 'CNPJ emit.', 'Situação do Crédito']).agg({
                        'Valor NF': 'sum',
                        'Créditos': 'sum',
                        'No.': 'count'
                    }).reset_index()
                    
                    # Cálculo do ticket médio (usando créditos)
                    summary['Ticket Médio'] = summary['Créditos'] / summary['No.']
                    
                    # Ordenar por total de créditos
                    summary = summary.sort_values(by='Créditos', ascending=False)
                    summary['ranking'] = range(1, len(summary) + 1)
                    
                    # Preparar dados para exibição
                    summary['Total Valor NF'] = summary['Valor NF']
                    summary['Total Créditos'] = summary['Créditos']
                    summary['Situação'] = summary['Situação do Crédito']
                    
                    # Criar ranking dos top 10
                    ranking = summary[['Emitente', 'CNPJ emit.', 'Total Créditos', 'Ticket Médio', 'ranking', 'Situação']].head(10).to_dict(orient='records')
                    global_summary = summary.to_dict(orient='records')
                    
                    logging.info("Dados processados e agrupados com sucesso.")
                except Exception as e:
                    error_message = f"Erro ao processar os dados: {e}"
                    logging.error(error_message)
                    return render_template('index.html', summary=[], ranking=ranking, monthly_totals={}, error_message=error_message, search_query=search_query, page=page, total_pages=total_pages)

        except Exception as e:
            error_message = f"Erro inesperado: {e}"
            logging.error(f"Erro inesperado durante o processamento: {e}")
            return render_template('index.html', summary=[], ranking=ranking, monthly_totals={}, error_message=error_message, search_query=search_query, page=page, total_pages=total_pages)

    summary = global_summary

    if search_query:
        search_terms = [term.strip() for term in search_query.split(',')]
        summary = [item for item in summary if any(
            term in item['Emitente'].lower() or term in item['CNPJ emit.'] for term in search_terms
        )]

    total_pages = max(1, ceil(len(summary) / per_page))
    summary_paginated = summary[(page-1)*per_page:page*per_page]

    return render_template('index.html', 
                         summary=summary_paginated, 
                         ranking=ranking, 
                         monthly_totals=monthly_totals,
                         error_message=error_message, 
                         search_query=search_query, 
                         page=page, 
                         total_pages=total_pages)

@app.route('/consulta_cnpj', methods=['POST'])
def consulta_cnpj():
    global global_summary, ranking, monthly_totals, total_pages
    per_page = 50
    
    try:
        # Obter a lista de CNPJs do formulário
        cnpj_list = request.form.get('cnpjList', '').strip()
        if not cnpj_list:
            return render_template('index.html', 
                                 error_message="Nenhum CNPJ informado",
                                 summary=global_summary[:per_page],
                                 ranking=ranking,
                                 monthly_totals=monthly_totals,
                                 page=1,
                                 total_pages=total_pages)

        # Converter o texto em uma lista de CNPJs
        cnpjs = [cnpj.strip().replace('.', '').replace('/', '').replace('-', '') 
                 for cnpj in cnpj_list.split('\n') if cnpj.strip()]

        # Filtrar dados globais para os CNPJs especificados
        results = []
        total_creditos = 0
        total_notas = 0

        for item in global_summary:
            cnpj_limpo = item['CNPJ emit.'].replace('.', '').replace('/', '').replace('-', '')
            if cnpj_limpo in cnpjs:
                result = {
                    'cnpj': item['CNPJ emit.'],
                    'emitente': item['Emitente'],
                    'total_creditos': item['Total Créditos'],
                    'qtd_notas': item['No.']
                }
                results.append(result)
                total_creditos += item['Total Créditos']
                total_notas += item['No.']

        # Retornar a página com os resultados
        return render_template('index.html', 
                             cnpj_results=results,
                             total_creditos_cnpjs=total_creditos,
                             total_notas_cnpjs=total_notas,
                             summary=global_summary[:per_page],
                             ranking=ranking,
                             monthly_totals=monthly_totals,
                             page=1,
                             total_pages=total_pages)

    except Exception as e:
        logging.error(f"Erro na consulta de CNPJs: {e}")
        return render_template('index.html', 
                             error_message=f"Erro ao processar consulta: {str(e)}",
                             summary=global_summary[:per_page],
                             ranking=ranking,
                             monthly_totals=monthly_totals,
                             page=1,
                             total_pages=total_pages)

@app.route('/shutdown', methods=['POST'])
def shutdown():
    try:
        os._exit(0)
    except Exception as e:
        logging.error(f"Error shutting down server: {e}")
        return "An error occurred while trying to shut down the server.", 500

if __name__ == "__main__":
    app.run()