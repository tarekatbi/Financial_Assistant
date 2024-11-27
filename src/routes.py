from flask import Blueprint, request, jsonify, current_app, send_from_directory
import logging
import pandas as pd
import os
from datetime import datetime
import requests

bp = Blueprint('routes', __name__)

def save_to_excel(dataframe, filename):
    output_dir = os.path.join(os.getcwd(), 'appout', 'output')
    os.makedirs(output_dir, exist_ok=True)
    file_path = os.path.join(output_dir, filename)
    dataframe.to_excel(file_path, index=False)
    return file_path

def format_amount(amount):
    if amount >= 1_000_000:
        return f"{amount / 1_000_000:.2f}M"
    elif amount >= 1_000:
        return f"{amount / 1_000:.0f}K"
    return f"{amount:.0f} €"

def transform_due_date(timestamp_ns):
    timestamp_s = timestamp_ns / 1_000_000_000
    date = datetime.utcfromtimestamp(timestamp_s)
    return date.strftime('%Y-%m-%d')

def format_percentage(percentage):
    return f"{percentage * 100:.0f}%"

####################################################################################################################################

def customized_response(row):
    sentence = (
        f"Le client {row['customer_name']} (ID : {row['customer_nbr']}) "
        f"a un score de retard de paiement de {row['score retard']:.2f}. "
        f"Le montant total facturé est de {format_amount(row['amount_invoiced'])}, "
        f"dont {format_amount(row['amount overdue'])} sont en retard. "
        f"Le délai moyen de paiement est de {int(row['avg contract payment term'])} jours. "
        f"Le retard moyen de paiement pour les factures à temps est de {int(row['avg on time payment delay'])} jours, "
        f"et le retard moyen pour les factures en retard est de {int(row['avg overdue payment delay'])} jours. "
        f"Le client est catégorisé comme : {row['seg']}."
    )
    return sentence

def customized_response_last_20_percent(row):
    sentence = (
        f"Pour les 20% dernières factures du client {row['customer_name']} (ID : {row['customer_nbr']}), "
        f"le pourcentage des paiements à temps est de {format_percentage(row['% ontime in last 20%'])}, "
        f"tandis que le pourcentage des paiements en retard est de {format_percentage(row['%overdue in last 20%'])}. "
        f"Le montant total facturé dans cette période est de {format_amount(row['amount_invoiced'])}, "
        f"dont {format_amount(row['amount overdue'])} sont encore en retard."
    )
    return sentence


@bp.route('/api/v1/download/<string:filename>', methods=['GET'])
def download_image(filename):
    output_dir = os.path.join(os.getcwd(), 'appout', 'output')
    return send_from_directory(directory=output_dir, path=filename, as_attachment=True)

# Analyse Client
@bp.route('/get_client', methods=['POST'])
def get_client():
    try:
        # Lire les données de la requête
        data = request.get_json()
        customer_name = data.get('customer_name', None)
        customer_nbr = data.get('customer_nbr', None)

        # Vérification de la configuration
        wx_utils = current_app.config['WX_UTILS']
        if not wx_utils.validate_config():
            logging.error("Invalid configuration")
            return jsonify({"error": "Invalid configuration"}), 500

        # Construire la requête SQL
        base_query = 'SELECT * FROM "lakehouse_data"."dso"."fact"'
        filters = []

        if customer_name:
            filters.append(f"customer_name = '{customer_name}'")
        if customer_nbr:
            filters.append(f"customer_nbr = '{customer_nbr}'")

        if filters:
            base_query += " WHERE " + " AND ".join(filters)

        logging.info(f"Executing query: {base_query}")
        results_df = wx_utils.executeSQL(base_query, fetch_results=True)

        if results_df is None or results_df.empty:
            logging.info("No results found for the given filters")
            return jsonify({"results": []}), 200

        response_text = ""
        client_details = []
        response_text_last_20 = ""

        for _, row in results_df.iterrows():
            response_text += customized_response(row) + "\n"
            response_text_last_20 += customized_response_last_20_percent(row) + "\n"

            client_details.append({
                "customer_name": row['customer_name'],
                "customer_nbr": row['customer_nbr'],
                "score_retard": row['score retard'],
                "%_ontime_in_last_20%": row['% ontime in last 20%'],
                "%_overdue_in_last_20%": row['%overdue in last 20%'],
                "amount_invoiced": format_amount(row['amount_invoiced']),
                "amount_overdue": format_amount(row['amount overdue']),
                "avg_contract_payment_term": row['avg contract payment term'],
                "avg_on_time_payment_delay": row['avg on time payment delay'],
                "avg_overdue_payment_delay": row['avg overdue payment delay'],
                "segmentation": row['seg']
            })

        filename = f"client_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        save_to_excel(results_df, filename)

        download_link = f"https://financialchatbot.1orl4io77158.eu-de.codeengine.appdomain.cloud/api/v1/download/{filename}"

        return jsonify({
            "response": response_text,
            "response_last20":response_text_last_20,
            "client_details": client_details,
            "message": "Excel file created successfully.",
            "download_link": download_link
        }), 200

    except Exception as e:
        logging.error(f"Error in /get_client route: {e}")
        return jsonify({"error": str(e)}), 500


####################################################################################################################################

def format_payment_statement_grouped(transaction_details):
    from collections import defaultdict

    grouped_details = defaultdict(list)
    for transaction in transaction_details:
        grouped_details[transaction['customer_name']].append(transaction)

    statements = []
    for customer_name, transactions in grouped_details.items():
        customer_id = transactions[0]['entity name']
        customer_statement = f"Client : {customer_name} (ID : {customer_id})\n"
        for transaction in transactions:
            customer_statement += (
                f"Facture #{transaction['invoice_number']} :\n"
                f"- Date de facture : {transaction['invoice_date']}\n"
                f"- Date d'échéance : {transaction['due_date']}\n"
                f"- Montant facturé : {transaction['amount_invoiced']}\n"
                f"- Montant payé : {transaction['amount_paid']}\n"
                f"- Montant dû : {transaction['amount_due']}\n"
                f"- Montant en retard : {transaction['amount_overdue']}\n"
                f"\n"
            )
        statements.append(customer_statement)

    return "\n---\n".join(statements)

@bp.route('/get_payment_statement', methods=['POST'])
def get_payment_statement():
    try:
        data = request.get_json()
        customer_name = data.get('customer_name', None)  
        customer_nbr = data.get('customer_nbr', None)    

        wx_utils = current_app.config['WX_UTILS']
        if not wx_utils.validate_config():
            logging.error("Invalid configuration")
            return jsonify({"error": "Invalid configuration"}), 500

        base_query = """
            SELECT
                f."customer_name",
                f."customer_nbr",
                f."Amount_invoiced" AS amount_invoiced,
                f."Amount overdue" AS amount_overdue,
                o."Inv. Amount" AS amount_paid,
                o."Inv. Balance" AS amount_due,
                o."Invoice #" AS invoice_nbr,
                o."Inv. Date" AS inv_date,
                o."Due Date" AS due_date
            FROM "lakehouse_data"."dso"."fact" f
            LEFT JOIN "lakehouse_data"."dso"."open_ar" o
                ON f."customer_nbr" = o."Customer #"
        """
        filters = []

        if customer_name:
            filters.append(f"f.customer_name = '{customer_name}'")
        if customer_nbr:
            filters.append(f"f.customer_nbr = '{customer_nbr}'")

        if filters:
            base_query += " WHERE " + " AND ".join(filters)

        logging.info(f"Executing query: {base_query}")
        results_df = wx_utils.executeSQL(base_query, fetch_results=True)

        filename = f"payment_statement{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        save_to_excel(results_df, filename)

        download_link = f"https://financialchatbot.1orl4io77158.eu-de.codeengine.appdomain.cloud/api/v1/download/{filename}"

        if results_df is None or results_df.empty:
            logging.info("No results found for the given filters")
            return jsonify({"results": []}), 200

        transaction_details = []
        for _, row in results_df.iterrows():
            transaction = {
                "customer_name": row['customer_name'],
                "entity name":row['customer_nbr'],
                "invoice_number": row['invoice_nbr'],
                "invoice_date": transform_due_date(row['inv_date']),
                "due_date": transform_due_date(row['due_date']),
                "amount_invoiced": format_amount(row['amount_invoiced']),
                "amount_paid": format_amount(row['amount_paid']),
                "amount_due": format_amount(row['amount_due']),
                "amount_overdue": format_amount(row['amount_overdue']),
            }
            transaction_details.append(transaction)
          
        payment_statement = format_payment_statement_grouped(transaction_details)
        return jsonify({
            "transaction_details": transaction_details,
            "download_link":download_link,
            "payment_statement":payment_statement

        }), 200

    except Exception as e:
        logging.error(f"Error in /get_payment_statement route: {e}")
        return jsonify({"error": str(e)}), 500

####################################################################################################################################

@bp.route('/get_invoice_status', methods=['POST'])
def get_invoice_status():
    try:
        data = request.get_json()
        invoice_number = data.get('Invoice #', None)

        if not invoice_number:
            return jsonify({"error": "Invoice number is required"}), 400

        # Vérification de la configuration
        wx_utils = current_app.config['WX_UTILS']
        if not wx_utils.validate_config():
            logging.error("Invalid configuration")
            return jsonify({"error": "Invalid configuration"}), 500

        base_query = f"""
            SELECT "Customer Name" AS customer_name,
            "Customer #" AS entity_name,
            "Invoice #",
            "Inv. Date" AS inv_date,
            "Due Date" AS due_date,
            "Inv. Amount" AS amount_invoiced,
            "Bill Type" AS type,
            "Last Remark" AS last_remark
            FROM "lakehouse_data"."dso"."open_ar"
            WHERE "Invoice #" = '{invoice_number}'
        """

        logging.info(f"Executing query: {base_query}")
        results_df = wx_utils.executeSQL(base_query, fetch_results=True)

        if results_df is None or results_df.empty:
            logging.info(f"No results found for invoice number: {invoice_number}")
            return jsonify({"error": f"No results found for invoice {invoice_number}"}), 404

        transaction_details = []
        for _, row in results_df.iterrows():
            transaction = {
                "customer_name": row['customer_name'],
                "entity_name": row['entity_name'],
                "invoice_number": row['Invoice #'],
                "invoice_date": transform_due_date(row['inv_date']),
                "due_date": transform_due_date(row['due_date']),
                "amount_invoiced": format_amount(row['amount_invoiced']),
                "last_remark": row['last_remark'],
                "type": row['type'],
            }
            transaction_details.append(transaction)

        payment_statement = ""
        for transaction in transaction_details:
            payment_statement += (
                f"Concernant la facture #{transaction['invoice_number']}, voici les détails : \n"
                f"la facture a été émise pour l'entité {transaction['entity_name']} du Groupe {transaction['customer_name']}.\n"
                f"la facture a été émise le {transaction['invoice_date']}, avec une date d'échéance fixée au {transaction['due_date']}.\n"
                f"Le montant total facturé est de {transaction['amount_invoiced']}.\n"
                f"Cette facture est de type {transaction['type']}, et la dernière remarque à son sujet est : '{transaction['last_remark']}'.\n\n"
            )
        return jsonify({
            "payment_statement": payment_statement
        }), 200

    except Exception as e:
        logging.error(f"Error in /get_invoice_status route: {e}")
        return jsonify({"error": str(e)}), 500
    

####################################################################################################################################

@bp.route('/generate_follow_up_email', methods=['POST'])
def generate_follow_up_email():
    try:
        data = request.json
        logging.info(f"Requête reçue: {data}")
        
        required_keys = ['customer_name', 'invoice_number', 'invoice_date', 'due_date', 'amount_due']
        if not all(key in data for key in required_keys):
            logging.error(f"Données manquantes dans la requête. Clés attendues: {required_keys}")
            return jsonify({'error': 'Données manquantes dans la requête'}), 400
        
        client = data['customer_name']
        invoice_number = data['invoice_number']
        invoice_date = data['invoice_date']
        due_date = data['due_date']
        amount_due = data['amount_due']

        # Prompt
        input_text = f"""
        Génère uniquement le contenu d'un e-mail de relance pour la facture suivante :

        - Client : {client}
        - Numéro de la facture : {invoice_number}
        - Date de la facture : {invoice_date}
        - Date d'échéance : {due_date}
        - Montant dû : {amount_due}

        L'email doit être professionnel, courtois et rappeler l'importance du paiement rapide. Ne rends rien d'autre que le texte de l'e-mail.
        """

        model_id = "meta-llama/llama-3-405b-instruct"
        parameters = {
            "decoding_method": "greedy",
            "temperature": 0.2,
            "random_seed": 33,
            "min_new_tokens": 1,
            "max_new_tokens": 300
        }

        wx_ai =  current_app.config['WXAI']
        result = wx_ai.generate_ga_batch(input_text, model_id, parameters)
        
        if 'results' in result:
            email_content = result['results'][0]
            logging.info(f"Email généré : {email_content}")
            return jsonify({'email_content': email_content}), 200
        else:
            logging.error(f"Réponse de l'API sans clé 'results': {result}")
            return jsonify({'error': 'Réponse invalide de l\'API', 'details': result}), 500
        
    except Exception as e:
        logging.error(f"Erreur lors de la génération de l'email: {str(e)}")
        return jsonify({'error': f"Erreur interne: {str(e)}"}), 500

####################################################################################################################################

@bp.route('/get_collector', methods=['POST'])
def get_collector():
    try:
        data = request.get_json()
        invoice_number = data.get('Invoice #', None)
        customer_name = data.get('customer_name', None)  
        customer_nbr = data.get('customer_nbr', None)    

        if not invoice_number:
            return jsonify({"error": "Invoice number is required"}), 400

        wx_utils = current_app.config['WX_UTILS']
        if not wx_utils.validate_config():
            logging.error("Invalid configuration")
            return jsonify({"error": "Invalid configuration"}), 500

        base_query = f"""
            SELECT "Customer Name" AS customer_name,
            "Customer #" AS entity_name,
            "Invoice #",
            "Collector" AS collector
            FROM "lakehouse_data"."dso"."open_ar"
            WHERE "Invoice #" = '{invoice_number}'
        """

        logging.info(f"Executing query: {base_query}")
        results_df = wx_utils.executeSQL(base_query, fetch_results=True)

        if results_df is None or results_df.empty:
            logging.info(f"No results found for invoice number: {invoice_number}")
            return jsonify({"error": f"No results found for invoice {invoice_number}"}), 404

        transaction_details = []
        for _, row in results_df.iterrows():
            transaction = {
                "customer_name": row['customer_name'],
                "entity_name": row['entity_name'],
                "invoice_number": row['Invoice #'],
                "collector": row['collector']
            }
            transaction_details.append(transaction)

        payment_statement = ""
        for transaction in transaction_details:
            payment_statement += (
                f"Concernant la facture #{transaction['invoice_number']}\n"
                f"la facture a été émise pour l'entité {transaction['entity_name']} du Groupe {transaction['customer_name']}.\n"
                f"le collecteur en charge de cette facture est {transaction['collector']}\n"
            )
        return jsonify({
            "payment_statement": payment_statement
        }), 200

    except Exception as e:
        logging.error(f"Error in /get_invoice_status route: {e}")
        return jsonify({"error": str(e)}), 500