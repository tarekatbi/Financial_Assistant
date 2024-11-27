import prestodb
import ssl
from prestodb import transaction
import logging
import json
from multiprocessing import Pool
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import as_completed
from time import time
from os import path
import os
import traceback
import uuid
import pandas as pd
import pandas as pd
from sqlalchemy import create_engine
from pyhive import presto

class WxdataPrestoUtils(object):
    def __init__(self, credentials):
        self.creds = credentials
        self.conn = prestodb.dbapi.connect(
                    host=credentials['host'], #'141.125.159.58',
                    port=credentials['port'],#8443,
                    user=credentials['user'],#'ibmlhadmin',
                    auth=prestodb.auth.BasicAuthentication(credentials['user'], credentials['password']),
                    catalog=credentials['catalog'],
                    http_scheme='https',
                    isolation_level=transaction.IsolationLevel.AUTOCOMMIT
                    #schema='tiny'
                )
        self.unique_env_id = f"{credentials['host']}-{uuid.uuid4()}"
        self.conn._http_session.verify = False
        self.columns_threadpool = ThreadPoolExecutor(8)
        self.tables_threadpool = ThreadPoolExecutor(5)
        
    def __del__(self):
        self.columns_threadpool.shutdown(wait=False)
        self.tables_threadpool.shutdown(wait=False)
    
    def validate_config(self):
        res = {'status' : 'OK'}
        try: 
            conn_test = prestodb.dbapi.connect(
                                host=os.getenv('WXDATA_HOST'),
                                port=os.getenv('WXDATA_PORT'),
                                user=os.getenv('WXDATA_USER'),
                                auth=prestodb.auth.BasicAuthentication(os.getenv('WXDATA_USER'), os.getenv('WXDATA_PASSWORD')),
                                catalog=os.getenv('WXDATA_CATALOG'),
                                http_scheme='https',
                                isolation_level=transaction.IsolationLevel.AUTOCOMMIT
                                #schema='tiny'
                            )      
        except Exception as e:
            logging.error("Error while validating presto connexion")  
            res['status'] = 'KO'
        return res
    
    def show_catalogs_contents(self):
        cur = self.conn.cursor()
        cur.execute('show catalogs')
        catalogs = cur.fetchall()
        for catalog in catalogs:
            #catalog = ["tpch"] # FOR DEBUG
            cur.execute("show schemas in %s"%catalog[0])
            schemas = cur.fetchall()
            logging.debug(f"Catalog: {catalog}")
        for schema in schemas:
            logging.debug(f"Schema: {schema}")
    
    
    def executeSQL(self, sql_query, fetch_results=False):
        queryResults = None
        
        logging.info(f"Executing query: {sql_query}")
        try:
            cur = self.conn.cursor()
            cur.execute(sql_query)            
            if fetch_results:
                res = cur.fetchall()
                queryResults = pd.DataFrame.from_records(res, columns = [i[0] for i in cur.description])
            else:
                cur.fetchone()
        except Exception as e:
            logging.error(f"Error while executing SQL Query {e}")
        return queryResults

    def get_catalogs(self):
        res = []
        cur = self.conn.cursor()
        cur.execute('show catalogs')
        catalogs = cur.fetchall()
        for catalog in catalogs:        
            res.append(catalog)
        return res
    
    def get_schemas(self, catalog):   
        res = []     
        cur = self.conn.cursor()
        cur.execute("show schemas in %s"%catalog[0])
        schemas = cur.fetchall()
        logging.debug(f"Catalog: {catalog}")
        for schema in schemas:
            logging.debug(f"Schema: {schema}")        
            res.append(schema)
        return res
    

    def get_tables(self, catalog, schema):
        res = []     
        cur = self.conn.cursor()
        cur.execute(f"show tables in \"{catalog[0]}\".\"{schema[0]}\"")
        tables = cur.fetchall()
        logging.debug(f"Catalog: {catalog}")
        for table in tables:
            logging.debug(f"Table: {table}")        
            res.append(table)
        return res
    
    def is_table_exists(self, catalog, schema, table):
        search_sql = f"""
            show tables from "{catalog}"."{schema}" like '{table.lower()}'
        """
        logging.info(search_sql)
        nb_tables_found = 0
        cur = self.conn.cursor()
        cur.execute(search_sql)
        tables_found = cur.fetchall()
        for table_found in tables_found:
            nb_tables_found = nb_tables_found + 1
        return nb_tables_found > 0
    
    
    def get_table_structure(self, catalog, schema, table):
        res = []
        try:
            cur = self.conn.cursor()
            if type(catalog) == list:
                cur.execute(f'describe\"{catalog[0]}\".\"{schema[0]}\".\"{table[0]}\"')     
            else: 
                cur.execute(f'describe\"{catalog}\".\"{schema}\".\"{table}\"')     
            columns = cur.fetchall()
            for col in columns:
                logging.debug(tuple(col))   
                res.append(tuple(col))
        except Exception as e:
            logging.error(f"Error while fetching table structure from presto {e}")
        return res

    def get_table_sample_data(self, catalog, schema, table):
        res = []
        query = f'select * from  \"{catalog[0]}\".\"{schema[0]}\".\"{table[0]}\" limit 10'
        cur = self.conn.cursor()
        logging.info(f"Query {query}")
        cur.execute(query)     
        columns = cur.fetchall()
        for col in columns:
            logging.debug(col)   
            res.append(col)
        return res

    def get_cols_sample_data(self, catalog, schema, table, table_struct):
        res = []        
        for tabcol in table_struct:
            query = f'select distinct {tabcol[0]} from  \"{catalog[0]}\".\"{schema[0]}\".\"{table[0]}\" limit 10'
            cur = self.conn.cursor()
            logging.info(f"Query {query}")
            cur.execute(query)     
            columns = cur.fetchall()
            columns_dict = {
                'table' : f"\"{catalog[0]}\".\"{schema[0]}\".\"{table[0]}\"",
                'column' : tabcol[0],
                'column-values' : []
            }
            logging.info(f"Table column {table[0]}.{tabcol[0]} metadata extraction")                
            for col in columns:
                logging.debug(col)   
                columns_dict['column-values'].append(str(col[0]))
            columns_dict['column-values'] = ",".join(columns_dict['column-values'])
            #infered_pii = self.wxai_utils.call_for_inference(self.get_pii_search_prompt(columns_dict))
            #logging.info(f"Inference result: {infered_pii}")
            #columns_dict['infered_pii'] = infered_pii
            res.append(columns_dict)
        return res


    def get_cols_sample_data_threaded(self,  process_config):
#    def get_cols_sample_data_threaded(self,  catalog, schema, table, table_struct):    
        futures = []     
        if 'lakehouse_metadata' in process_config:
            logging.info('using cache data')
            table_cache = self.search_table_in_cache(process_config)
            if table_cache:
                logging.info("table found in cache")
                return table_cache
            else: 
                logging.info(f"Table exists but not cache for config")
                return None
        if 'table_struct' in process_config:
            table_struct = process_config['table_struct']
        res = [] 
        try:       
            for tabcol in table_struct:
                #FIXME try with deep copy for multi table threading fix
                logging.info(f"Submitting column sampling thread for {tabcol[0]}")
                futures.append(self.columns_threadpool.submit(self.get_col_sample_data, process_config, tabcol))
                #res.append(self.get_col_sample_data(process_config, tabcol))
                
            for future in as_completed(futures):
                logging.debug(f"Column data sampling thread result: {future.result()}")   
                res.append(future.result()) 
                
        except Exception as e:
            logging.error(f"Error while extracting columns sample data: {e}")
            logging.error(f"Full error stack trace: {traceback.format_exc()}")
                
        return res
        
    def get_col_sample_data(self, process_config , tabcol):
        catalog = process_config['catalog']
        schema = process_config['schema']
        table = process_config['table']
        query = f'select distinct \"{tabcol[0]}\" from  \"{catalog}\".\"{schema}\".\"{table}\" limit 10'
        try:
            logging.debug(f"built query: {query}")
            cur = self.conn.cursor()
            logging.debug(f"Query {query}")
            cur.execute(query)     
            columns = cur.fetchall()
            columns_dict = {
                'table' : f"\"{catalog}\".\"{schema}\".\"{table}\"",
                'column' : tabcol[0],
                'column-values' : []
            }
            logging.debug(f"Table column  {catalog}.{schema}.{table}.{tabcol[0]} metadata extraction")                
            for col in columns:
                logging.debug(col)   
                columns_dict['column-values'].append(str(col[0]))
            columns_dict['column-values'] = ",".join(columns_dict['column-values'])
        except Exception as e:
            logging.error(f"Error while executing query for sample data extraction: {query}")
            raise e
        #infered_pii = self.wxai_utils.call_for_inference(self.get_pii_search_prompt(columns_dict))
        #logging.info(f"Inference result: {infered_pii}")
        #columns_dict['infered_pii'] = infered_pii
        return columns_dict
            
    

    def get_all_lakehouse_metadata_threaded(self, exclude_catalogs=None , with_data_samples=False, cache_file=None, filter_schema=None, unique_table=None):
        discovery_data_dict = None        
        try:
            if cache_file:
                if not path.exists(cache_file):    
                    discovery_data_dict = self.perform_full_lh_discovery(exclude_catalogs, with_data_samples, filter_schema, unique_table)
                    with open(cache_file, "w") as outfile:
                        json.dump(discovery_data_dict, outfile, indent=2)                
                else: 
                    discovery_data_dict = self.load_cache_file(cache_file)
            else:
                discovery_data_dict = self.perform_full_lh_discovery(exclude_catalogs, with_data_samples, filter_schema, unique_table)
                with open(cache_file, "w") as outfile:
                    json.dump(discovery_data_dict, outfile, indent=2)
            logging.debug(discovery_data_dict)
        except Exception as e:
            logging.error(f"Fatal error While handling lakehouse metadata extraction : {str(e)}")
            logging.error(traceback.format_exc())
        return discovery_data_dict
    
    """
    The below function creates a full json format cache of a presto endpoint access for all catalogs

    "name": "hive_landing_local",
        "schemas-details": [
        {
            "schema-name": "streaming",
            "table-structs": [
                {
                "table_name": 
                "table_structure":
                },
            "columns-samples": [
            [
                {
                "table": 
                "column": 
                "column-values": 
                },
            ]
    """
    def perform_full_lh_discovery(self, exclude_catalogs=None , with_data_samples=False, filter_schema=None, unique_table=None):
        lakehouse_metadatas =  []
        catalogs = self.get_catalogs()
        for catalog in catalogs:
            logging.info(f"Extracting metadata from catalog {catalog[0]}")
            if exclude_catalogs and catalog[0] in exclude_catalogs:
                logging.info(f"Skipping Catalog {catalog[0]}")
                continue
            catalog_dict = {
                'name': catalog[0]
            }
            catalog_dict['schemas-details'] = []
            logging.info(f"Loading metadata catalog for {catalog[0]}")
            schemas = self.get_schemas(catalog)
            catalog_dict['schemas'] = schemas
            logging.info(f"Discovered schemas : {schemas}")
            for schema in schemas: #schemas
                logging.info(f"Testing {schema[0]} vs {filter_schema}" )
                if (len(schema) > 0  and schema[0] in [ filter_schema ]) or (filter_schema is None):
                    logging.info(f"Loading schema metadata for : {schema[0]}")
                    schema_dict = {
                        'schema-name': schema[0],
                        'table-structs' : [],
                        'columns-samples' : []
                    }
                    #catalog_dict['schemas-details'].append(schema)
                    tables = self.get_tables(catalog, schema)
                    schema_dict['tables'] = tables
                    futures = []
                    for table in tables:
                        logging.info(f"Testing {table} vs {unique_table}")
                        if (len(table) >0 and table[0] and unique_table and table[0] == unique_table) or (unique_table is None):
                            logging.info(f"Load table metadata for: {table[0]}")
                            #futures.append(self.tables_threadpool.submit(self.get_table_structure, catalog, schema, table))
                            table_struct = self.get_table_structure(catalog, schema, table)
                            schema_dict['table-structs'].append({ 'table_name' : table[0], 'table_structure': table_struct})
                    #for future in as_completed(futures):
                    #    schema_dict['table-structs'].append({ 'table_name' : table[0], 'table_structure': future.result()})                    
                    
                    futures = []
                    for table in schema_dict['table-structs']:
                        process_config = {}
                        process_config['catalog'] = catalog_dict['name']
                        process_config['schema'] = schema_dict['schema-name']
                        process_config['table'] = table['table_name']
                        process_config['table_struct'] = tuple(table['table_structure'])                    
                        if with_data_samples:
                            futures.append(self.tables_threadpool.submit(self.get_cols_sample_data_threaded, process_config))
                            #schema_dict['columns-samples'].append(self.get_cols_sample_data_threaded(process_config))
                    #catalog_dict['schemas-details'].append(schema_dict)                        
                    for future in as_completed(futures):
                        logging.debug(f"Table Thread completed {future.result()}")
                        schema_dict['columns-samples'].append(future.result())
                        catalog_dict['schemas-details'].append(schema_dict)  

            lakehouse_metadatas.append(catalog_dict)
        
        return lakehouse_metadatas        


    def load_cache_file(self, discovery_cache_file_path):
        with open(discovery_cache_file_path, 'r') as infile:
            discovery_cache_dict = json.load(infile)
        return discovery_cache_dict
    
    def get_tables_from_discovery_cache(self, lh_discorvery_dict):
        res = []
        for catalog in lh_discorvery_dict:
            for schema in catalog['schemas-details']:
                for table in schema['tables']:                    
                    res.append(f"{catalog['name']}.{schema['schema-name']}.{table[0]}")
        return res

    def search_table_in_cache(self, runconfig):
        catalog_searched = runconfig['catalog']
        schema_searched = runconfig['schema']
        table_searched = f"\"{catalog_searched}\".\"{schema_searched}\".\"{runconfig['table'].lower()}\""
        lh_discovery_dict = runconfig['lakehouse_metadata']
        res = []
        logging.debug(f"Search into lh cache data: {lh_discovery_dict}")
        for catalog in lh_discovery_dict:
            logging.info(f"Catalog: {catalog['name']}")
            if catalog['name'] == catalog_searched:              
                for schema in catalog['schemas-details']:
                    logging.info(f"schema: {schema['schema-name']}")
                    if schema_searched == schema['schema-name']:
                        for tables_array in schema['columns-samples']:  
                            for table in tables_array:
                                logging.debug(f"table: {table}")
                                if table['table'] == table_searched:
                                    return tables_array                         
                    else:
                        pass
            else: 
                pass
        return None

     

    def move_route_hive_to_iceberg(self, config):
        landing_table = config['hive_table']
        gold_table = config['iceberg_table']
        logging.info('Sending incremental binance prices to target iceberg table')
        binance_incremental_query = f"""
        INSERT INTO {gold_table} SELECT UPDATE_DATE, UPDATE_TS, symbol, CAST(prices AS DOUBLE) FROM {landing_table} a where a.UPDATE_TS > (SELECT CASE WHEN MAX(UPDATE_TS)  IS NULL THEN 1 ELSE MAX(UPDATE_TS) END FROM {gold_table} ) """    
        cur = self.conn.cursor()
        logging.debug('Incremental insert')
        try:
            cur.execute(binance_incremental_query)
            cur.fetchone()
        except Exception as e:
            logging.debug(f'Error while executing incremental insert: {e}')
        logging.info("Incremental transfer ended successfully")

    def load_dataframe_to_presto(self, df, catalog, schema, table_name):
        """
        Load a pandas DataFrame to a Presto table in bulk.
        """
        presto_host = self.creds['host']
        presto_port =  self.creds['port']
        presto_catalog = catalog
        presto_schema = schema
        username =  self.creds['user']
        password =  self.creds['password']
        # Create a connection string
        conn_str = f'presto://{username}:{password}@{presto_host}:{presto_port}/{presto_catalog}/{presto_schema}'
        # Create an SQLAlchemy engine
        engine = create_engine(conn_str, connect_args={'protocol': 'https', 'requests_kwargs': {'verify': False}} )
        # Create a SQL insert statement
        columns = ', '.join(df.columns)
        placeholders = ', '.join(['%s'] * len(df.columns))
        insert_stmt = f'INSERT INTO {table_name} ({columns}) VALUES ({placeholders})'#
        
        df.to_sql(table_name, engine, index=False, if_exists="append", schema=presto_schema)
        # Connect to Presto and execute the insert statement in bulk
        #with engine.connect() as connection:
        #    connection.execute(insert_stmt, data_tuples)
        
        print(f"Data loaded successfully into {table_name}.")         

#credentials = {
#    "host" : 'ibm-lh-lakehouse-presto815-presto-svc-cpd.cpd481-us-south-1-mx2-16x-f9a4ba6392eef8fabc137c724dfd7712-0000.us-south.containers.appdomain.cloud',
#    "port"  : 443,
#    "user" : 'cpadmin',
#    "password" : 'xxx',
#    "catalog" : 'catalog'                    
#}

#wx_utils = WxdataPrestoUtils(credentials)
#wx_utils.get_all_lakehouse_metadata_threaded(['singlestore_remote', 'iceberg_local', 'jmx', 'system', 'tpcds' , 'tpch'], True, "./lakehouse_cache_data.json")