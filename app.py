from flask import Flask, render_template, request, redirect, url_for
import pandas as pd
import logging
import os
import json
import hashlib
from math import ceil
from datetime import datetime
import tempfile
import shutil

app = Flask(__name__)

# Aumentar limite de upload para permitir arquivos maiores
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500 MB

# Configuração do logger
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[
                        logging.FileHandler("app.log", mode='w'),
                        logging.StreamHandler()
                    ])

# Carregar CNPJs cadastrados por robô
ROBOTIC_CNPJS_FILE = 'robotic_cnpjs.json'

def load_robotic_cnpjs():
    try:
        if os.path.exists(ROBOTIC_CNPJS_FILE):
            with open(ROBOTIC_CNPJS_FILE, 'r') as f:
                data = json.load(f)
                # Limpar os CNPJs (remover formatação)
                return [cnpj.replace('.', '').replace('/', '').replace('-', '') for cnpj in data['robotic_cnpjs']]
        else:
            # Se não existir, criar o arquivo com os CNPJs informados
            default_cnpjs = [
                "57528746000190", "41963634000127", "68905603000257", "36535529000157",
                "34124712000134", "23747241000102", "13878933000128", "10657359000190",
                "07029999000140", "05627892000179", "68905603000176", "41231162000118",
                "50959760000107", "51580540000122", "58642901000167"
            ]
            with open(ROBOTIC_CNPJS_FILE, 'w') as f:
                json.dump({"robotic_cnpjs": default_cnpjs}, f, indent=2)
            return default_cnpjs
    except Exception as e:
        logging.error(f"Erro ao carregar CNPJs de robôs: {e}")
        # Retornar lista padrão em caso de erro
        return [
            "57528746000190", "41963634000127", "68905603000257", "36535529000157",
            "34124712000134", "23747241000102", "13878933000128", "10657359000190",
            "07029999000140", "05627892000179", "68905603000176", "41231162000118",
            "50959760000107", "51580540000122", "58642901000167"
        ]

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
        parts = date_str.split('/')
        if len(parts) == 3:
            day, month, year = parts
            return f"{month_names[month]} {year}"
        return "Data inválida"
    except Exception as e:
        logging.error(f"Erro ao converter data '{date_str}': {e}")
        return "Data inválida"

def get_month_sort_key(month_name):
    """Retorna uma chave de ordenação para os meses no formato 'Nome Ano'"""
    try:
        month_order = {
            'Janeiro': '01', 'Fevereiro': '02', 'Março': '03',
            'Abril': '04', 'Maio': '05', 'Junho': '06',
            'Julho': '07', 'Agosto': '08', 'Setembro': '09',
            'Outubro': '10', 'Novembro': '11', 'Dezembro': '12'
        }
        month, year = month_name.rsplit(' ', 1)
        return f"{year}{month_order.get(month, '13')}"  # 13 para meses inválidos (ficarão no final)
    except:
        return "999999"  # Valor alto para itens inválidos ficarem no final

# Função para calcular o hash de um arquivo
def calculate_file_hash(file_data):
    """Calcula um hash MD5 dos dados do arquivo para identificar duplicatas"""
    return hashlib.md5(file_data).hexdigest()

# Registro do filtro personalizado
app.jinja_env.filters['format_currency'] = format_currency

# Variáveis globais
global_summary = []
ranking = []
monthly_totals = {}
monthly_robotic_totals = {}
total_pages = 1
robotic_cnpjs = load_robotic_cnpjs()

@app.route('/', methods=['GET', 'POST'])
def index():
    global global_summary, ranking, monthly_totals, monthly_robotic_totals, total_pages, robotic_cnpjs

    error_message = None
    search_query = request.args.get('search', '').strip()
    page = int(request.args.get('page', 1))
    per_page = 50
    search_results = []
    total_creditos_pesquisa = 0
    total_notas_pesquisa = 0
    processed_files = 0
    total_creditos = 0
    total_notas = 0
    
    # Flag para verificar se temos dados antes de tentar paginá-los
    has_data = len(global_summary) > 0

    logging.info(f"Página atual: {page}, Itens por página: {per_page}")

    if request.method == 'POST' and 'csvFiles' in request.files:
        try:
            csv_files = request.files.getlist('csvFiles')
            if not csv_files or all(file.filename == '' for file in csv_files):
                error_message = "Nenhum arquivo CSV foi carregado."
                logging.error(error_message)
                return render_template('index.html', 
                                      summary=global_summary[:per_page] if has_data else [], 
                                      ranking=ranking, 
                                      monthly_totals=monthly_totals, 
                                      monthly_robotic_totals=monthly_robotic_totals,
                                      error_message=error_message, 
                                      search_query=search_query, 
                                      page=page, 
                                      total_pages=total_pages)

            # Recarregar CNPJs de robôs
            robotic_cnpjs = load_robotic_cnpjs()
            logging.info(f"CNPJs de robôs carregados: {len(robotic_cnpjs)} encontrados")

            # Criar diretório temporário para armazenar os arquivos
            temp_dir = tempfile.mkdtemp()
            try:
                # Dicionário para evitar processamento de arquivos duplicados
                processed_file_hashes = {}
                
                df_list = []
                for file in csv_files:
                    if file.filename == '':
                        continue
                    
                    try:
                        # Obter dados e calcular o hash para verificar duplicatas
                        file_data = file.read()
                        file_hash = calculate_file_hash(file_data)
                        
                        # Verificar se este arquivo já foi processado
                        if file_hash in processed_file_hashes:
                            logging.info(f"Arquivo duplicado ignorado: {file.filename}")
                            continue
                        
                        # Salvar arquivo temporariamente e processar
                        processed_file_hashes[file_hash] = True
                        
                        # Voltar o ponteiro para o início do arquivo para processamento
                        file.seek(0)
                        
                        # Salvar no diretório temporário
                        temp_file_path = os.path.join(temp_dir, os.path.basename(file.filename))
                        with open(temp_file_path, 'wb') as f:
                            f.write(file_data)
                        
                        # Leitura do arquivo com a codificação UTF-16
                        df = pd.read_csv(temp_file_path, encoding='utf-16le', delimiter='\t', quoting=1)
                        
                        # Remover caracteres especiais dos nomes das colunas
                        df.columns = df.columns.str.strip().str.replace('"', '')
                        
                        df_list.append(df)
                        processed_files += 1
                        logging.info(f"Arquivo {file.filename} lido com sucesso")
                    except Exception as e:
                        error_message = f"Erro ao ler o arquivo {file.filename}: {e}"
                        logging.error(error_message)
                        continue  # Continuar com próximo arquivo em vez de abortar

                if not df_list:
                    error_message = "Nenhum arquivo CSV válido foi processado."
                    logging.error(error_message)
                    return render_template('index.html', 
                                         summary=global_summary[:per_page] if has_data else [], 
                                         ranking=ranking, 
                                         monthly_totals=monthly_totals, 
                                         monthly_robotic_totals=monthly_robotic_totals,
                                         error_message=error_message, 
                                         search_query=search_query, 
                                         page=page, 
                                         total_pages=total_pages)

                try:
                    df = pd.concat(df_list)
                    logging.info(f"DataFrames concatenados com sucesso. Total de {processed_files} arquivos processados.")
                    processed_files = len(processed_file_hashes)
                except Exception as e:
                    error_message = f"Erro ao concatenar os dados: {e}"
                    logging.error(error_message)
                    return render_template('index.html', 
                                         summary=global_summary[:per_page] if has_data else [], 
                                         ranking=ranking, 
                                         monthly_totals=monthly_totals, 
                                         monthly_robotic_totals=monthly_robotic_totals,
                                         error_message=error_message, 
                                         search_query=search_query, 
                                         page=page, 
                                         total_pages=total_pages)

                try:
                    # Limpeza e conversão das colunas numéricas
                    df['Valor NF'] = df['Valor NF'].str.strip().str.replace('"', '').str.replace(',', '.').astype(float)
                    df['Créditos'] = df['Créditos'].str.strip().str.replace('"', '').str.replace(',', '.').astype(float)
                    logging.info("Colunas numéricas convertidas com sucesso.")
                except Exception as e:
                    error_message = f"Erro ao converter colunas numéricas: {e}"
                    logging.error(f"Erro detalhado na conversão: {str(e)}")
                    return render_template('index.html', 
                                         summary=global_summary[:per_page] if has_data else [], 
                                         ranking=ranking, 
                                         monthly_totals=monthly_totals, 
                                         monthly_robotic_totals=monthly_robotic_totals,
                                         error_message=error_message, 
                                         search_query=search_query, 
                                         page=page, 
                                         total_pages=total_pages)

                try:
                    # Adicionar coluna para identificar CNPJs de robôs
                    df['CNPJ Limpo'] = df['CNPJ emit.'].str.replace('.', '').str.replace('/', '').str.replace('-', '')
                    df['É Robô'] = df['CNPJ Limpo'].isin(robotic_cnpjs)
                    
                    # Calcular totais por mês
                    df['Mês'] = df['Data Emissão'].apply(get_month_name)
                    
                    # Total geral por mês
                    monthly_totals = df.groupby('Mês')['Créditos'].sum().to_dict()
                    
                    # Total de robôs por mês
                    monthly_robotic_totals = df[df['É Robô']].groupby('Mês')['Créditos'].sum().to_dict()
                    
                    # Ordenar os meses cronologicamente (para todos os meses, incluindo os que não têm robôs)
                    sorted_months = sorted(monthly_totals.keys(), key=get_month_sort_key)
                    
                    # Criar dicionários ordenados
                    ordered_monthly_totals = {month: monthly_totals[month] for month in sorted_months}
                    ordered_monthly_robotic_totals = {}
                    
                    for month in sorted_months:
                        if month in monthly_robotic_totals:
                            ordered_monthly_robotic_totals[month] = monthly_robotic_totals[month]
                        else:
                            ordered_monthly_robotic_totals[month] = 0.0
                    
                    monthly_totals = ordered_monthly_totals
                    monthly_robotic_totals = ordered_monthly_robotic_totals

                    # Agrupamento e cálculos
                    summary = df.groupby(['Emitente', 'CNPJ emit.', 'Situação do Crédito', 'É Robô']).agg({
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
                    ranking = summary[['Emitente', 'CNPJ emit.', 'Total Créditos', 'Ticket Médio', 'ranking', 'Situação', 'É Robô']].head(10).to_dict(orient='records')
                    global_summary = summary.to_dict(orient='records')
                    
                    logging.info(f"Dados processados e agrupados com sucesso. Total de {len(global_summary)} registros gerados.")
                except Exception as e:
                    error_message = f"Erro ao processar os dados: {e}"
                    logging.error(error_message)
                    return render_template('index.html', 
                                         summary=global_summary[:per_page] if has_data else [], 
                                         ranking=ranking, 
                                         monthly_totals=monthly_totals, 
                                         monthly_robotic_totals=monthly_robotic_totals,
                                         error_message=error_message, 
                                         search_query=search_query, 
                                         page=page, 
                                         total_pages=total_pages)
            finally:
                # Limpar diretório temporário
                shutil.rmtree(temp_dir, ignore_errors=True)

        except Exception as e:
            error_message = f"Erro inesperado: {e}"
            logging.error(f"Erro inesperado durante o processamento: {e}")
            return render_template('index.html', 
                                 summary=global_summary[:per_page] if has_data else [], 
                                 ranking=ranking, 
                                 monthly_totals=monthly_totals, 
                                 monthly_robotic_totals=monthly_robotic_totals,
                                 error_message=error_message, 
                                 search_query=search_query, 
                                 page=page, 
                                 total_pages=total_pages)

    summary = global_summary

    # Processar pesquisa unificada (se houver)
    if search_query:
        # Dividir a consulta em termos separados por vírgula
        search_terms = [term.strip().lower() for term in search_query.split(',') if term.strip()]
        
        if search_terms:
            # Verificar se é uma consulta específica por CNPJs ou uma pesquisa geral
            is_cnpj_search = all(term.replace('.', '').replace('/', '').replace('-', '').isdigit() for term in search_terms)
            
            if is_cnpj_search:
                # Limpar formatação dos CNPJs da pesquisa
                clean_search_cnpjs = [term.replace('.', '').replace('/', '').replace('-', '') for term in search_terms]
                
                # Filtrar resultados específicos para os CNPJs
                search_results = [item for item in global_summary if item['CNPJ emit.'].replace('.', '').replace('/', '').replace('-', '') in clean_search_cnpjs]
                
                # Calcular totais para os resultados da pesquisa
                total_creditos_pesquisa = sum(item['Total Créditos'] for item in search_results)
                total_notas_pesquisa = sum(item['No.'] for item in search_results)
            else:
                # Pesquisa por texto (nome ou parte do CNPJ)
                search_results = [
                    item for item in global_summary 
                    if any(
                        term in item['Emitente'].lower() or 
                        term in item['CNPJ emit.'].lower() 
                        for term in search_terms
                    )
                ]
                
                # Calcular totais para os resultados da pesquisa
                total_creditos_pesquisa = sum(item['Total Créditos'] for item in search_results)
                total_notas_pesquisa = sum(item['No.'] for item in search_results)
        
        # Para visualização paginada, também filtrar os dados gerais
        summary = [
            item for item in summary 
            if any(
                term in item['Emitente'].lower() or 
                term in item['CNPJ emit.'].lower() 
                for term in search_terms
            )
        ]

    total_pages = max(1, ceil(len(summary) / per_page))
    summary_paginated = summary[(page-1)*per_page:page*per_page]

    return render_template('index.html', 
                         summary=summary_paginated, 
                         ranking=ranking, 
                         monthly_totals=monthly_totals,
                         monthly_robotic_totals=monthly_robotic_totals,
                         error_message=error_message, 
                         search_query=search_query,
                         search_results=search_results,
                         total_creditos_pesquisa=total_creditos_pesquisa,
                         total_notas_pesquisa=total_notas_pesquisa,
                         processed_files=processed_files,  # ← Adicionado
                         total_creditos=sum(monthly_totals.values()) if monthly_totals else 0,  # ← Adicionado
                         total_notas=sum(item['No.'] for item in global_summary) if global_summary else 0,  # ← Adicionado
                         page=page, 
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