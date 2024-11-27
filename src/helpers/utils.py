import yaml 
import os 
import logging 
import sys
import os
import yaml 
from unidecode import unidecode
import re
from logging.config import dictConfig
import yaml 
from yaml.loader import SafeLoader
import logging
import os
from os import path
import datetime 
import glob
import shutil
import zipfile
import mimetypes
import shutil
import zipfile
import uuid 
import traceback
import multiprocessing
from multiprocessing import Pool
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock


def list_folder_files(folderpath, extension=None):
    res = []
    logging.debug(f"listing folder {folderpath}")
    for root, dirs, files in os.walk(folderpath):
        for name in files:
            logging.debug(os.path.join(root, name))
            if extension and name.endswith(extension):
                res.append(os.path.join(root, name))
            elif extension is None:
                res.append(os.path.join(root, name))
    #for file in os.listdir(folderpath):
    #    print(f'Found file {file}')
    #    res.append(file)
    return res



def openDocumentsZipArchive(archivepath, unzip_location):  
    res = []
    if os.path.exists(archivepath):
        # Open a ZIP file in read mode
        with zipfile.ZipFile(archivepath, 'r') as zip_ref:
            # Get a list of all files in the ZIP file
            file_list = zip_ref.namelist()
            
            # Loop through each file
            for file_name in file_list:
                mime_type, encoding = mimetypes.guess_type(file_name)
                logging.info(f"""file: {file_name}
mime type {mime_type}
encoding= {encoding}""")
                # Read the contents of the file
                with zip_ref.open(file_name) as file:
                    contents = file.read()
                    outpath = f'{unzip_location}/{get_file_name_from_path(file_name)}{get_file_ext_from_path(file_name)}'
                    res.append(outpath)
                    with open(outpath, 'wb') as outfile:
                        outfile.write(contents)
                    #print(f'Contents of {file_name} to {outpath}')
            #shutil.rmtree('/path/to/your/dir/')
    else:
        logging.warning(f"archive file does not exists : {archivepath}")
    logging.info(f"{len(res)} files found in zip file")
    return res 



def split_zip_into_chunks(zip_path, unzip_location, chunk_size_mb):
    if not os.path.exists(zip_path):
        logging.error(f"{zip_path} not found cannot unzip")
        return 
    files_lists = []
    current_chunk_files_list = []
    chunk_size_bytes = chunk_size_mb * 1024 * 1024  # Convert MB to bytes
    current_chunk_size = 0
    chunk_number = 1
    current_chunk_dir = f"{unzip_location}/{get_file_name_from_path(zip_path)}-chunk_{chunk_number}"
    os.makedirs(current_chunk_dir, exist_ok=True)

    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        curfile = 0
        for file_info in zip_ref.infolist():
            curfile += 1
            logging.info(f"Processing file {curfile}/{len(zip_ref.infolist())}")
            if file_info.is_dir():
                continue  # Skip directories
            
            # Extract the file to the current chunk directory
            zip_ref.extract(file_info, current_chunk_dir)
            current_chunk_files_list.append(f"{unzip_location}/{get_file_name_from_path(zip_path)}-chunk_{chunk_number}/{file_info.filename}")
            current_chunk_size += file_info.file_size

            # If the current chunk size exceeds the desired chunk size, start a new chunk
            if current_chunk_size >= chunk_size_bytes:
                chunk_number += 1
                current_chunk_dir = f"{unzip_location}/{get_file_name_from_path(zip_path)}-chunk_{chunk_number}"
                os.makedirs(current_chunk_dir, exist_ok=True)
                current_chunk_size = 0
                files_lists.append(current_chunk_files_list)
                current_chunk_files_list = []
    if current_chunk_size > 0:
        files_lists.append(current_chunk_files_list)
    logging.info(f"Split into {chunk_number} chunks. {len(files_lists)} files list found")
    return chunk_number, files_lists
    
def zipfolder(zipname, source_dir):  
    logging.info(f"Creating zip file {zipname} from folder {source_dir}, {os.getcwd()}")     
    shutil.make_archive(zipname, format='zip', root_dir=source_dir)   

def merge_files_by_pattern(files_glob_pattern, target_file_path=None):
    logging.info(f"Searching file with pattern:  {files_glob_pattern}, output path provided: {target_file_path}")
    files_glob_pattern = files_glob_pattern.replace("'", "")
    if target_file_path: 
        target_path_out = target_file_path
    else:
        target_path_out = "./out_all_merge_todo_add_ts"
    files = glob.glob(files_glob_pattern)
    #create output file
    logging.info(f"files found {files}")
    with open(target_path_out, 'w') as outfile:
        for input_file_path in files:
            logging.info(f"merging file  {input_file_path}")
            with open(input_file_path) as infile:
                data = infile.read()
                logging.debug(f"Data to be merged: {data}")
                outfile.write(data)
    
            #merge content into output file
            
def get_current_timestamp():
    return datetime.datetime.now()
    

    
def clean_str_for_tablename( value):
    res = value.lower().strip().replace(' ', '_').replace('.', '').replace("-",'_').replace('(','_').replace(')','_').replace('%','PCT')
    res_ascii =  unidecode(res)
    final_result = re.sub(r'\W+', '', res_ascii)
    return final_result

def get_file_name_from_path(file_full_path):
    return os.path.splitext(os.path.basename(file_full_path))[0]

def get_file_ext_from_path(file_full_path):
    return os.path.splitext(os.path.basename(file_full_path))[1]


def list_folder_file(folder_path):
    files = os.listdir(folder_path)
    return files

def load_yaml_file(filepath):
    res = None  
    with open(filepath) as infile:
        res = yaml.load(infile, Loader=SafeLoader)
    return res


def dict_to_yaml_file(python_dict, filepath):
    with open(filepath, 'w') as outfile: 
        yaml.dump(python_dict, outfile)


def create_folder(folder_fullpath):
    if path.exists(folder_fullpath):
        logging.info(f'Path {folder_fullpath} already exists, skipping')
    else:
        os.makedirs(folder_fullpath) 

def create_file(filepath, content=None):
    if path.exists(filepath):
        logging.info("File already exists")
    else:
        with open(filepath, 'w') as creating_new_csv_file: 
            if content is None:
                logging.debug(f"Empty File {filepath} Created Successfully") 
            else:
                creating_new_csv_file.write(content)
                logging.debug(f"File {filepath} Created with content Successfully")


def get_file_content(filepath, binary=False):
    if binary:
        open_flag = 'rb'
    else:
        open_flag = 'r'
    with open(filepath, open_flag) as input_file:   
        return input_file.read()
    

def write_content_to_file(filepath, content):
    logging.debug(f"Writing content to {filepath}")
    with open(filepath, 'w') as outfile:
        outfile.write(content)


def path_exists(filepath):
    return path.exists(filepath)


def init_configuration_env():
    os.environ['HF_EMBEDING_MODEL_ID'] = "BAAI/bge-base-en-v1.5" # "sentence-transformers/all-MiniLM-L6-v2" "mixedbread-ai/mxbai-embed-large-v1" "mixedbread-ai/mxbai-embed-large-v1""BAAI/bge-base-en-v1.5" #"mixedbread-ai/mxbai-embed-large-v1"  "dangvantuan/sentence-camembert-large"# "sentence-transformers/all-MiniLM-L6-v2"        
    os.environ['MILVUS_SERVICE_TYPE'] = 'saas'
    os.environ['MILVUS_ALIAS'] = 'techzone_milvus_env'
    os.environ['MILVUS_HOST'] = '141.125.110.252'
    os.environ['MILVUS_PORT'] = '19530'
    os.environ['MILVUS_USER'] = 'cpadmin'
    os.environ['MILVUS_CERTPATH'] = 'C:/Users/109394706/Downloads/milvus_grpc.cert'
    os.environ['MILVUS_PASSWORD'] = 'LzCoe-HXIwV-dTSVd-NftIJ'

    os.environ['WXAI_INFER_ENDPOINT'] =  "https://us-south.ml.cloud.ibm.com"
    os.environ['WXAI_ACCESS_KEY'] =  "Zu-jHs83kXStcKu14PnPTOSdrPbKEwAHJOnw1wK2P5sH"
    os.environ['WXAI_PROJECT_ID'] = "9946968d-6dae-4bda-b4d5-a306cb6b7005"

    os.environ['TEXT_VECTORS_COLLECTION'] = 'pdf_rag'


    os.environ['MILVUS_SERVICE_TYPE'] = 'managed_oss'
    os.environ['MILVUS_HOST'] = '141.125.110.252'
    os.environ['MILVUS_PORT'] = '19530'



def init_logging():
    logging.basicConfig(stream=sys.stdout, level=logging.INFO)
    #logging.getLogger().addHandler(logging.StreamHandler(stream=sys.stdout))

def init_env_from_yaml():    
    try:     
        # Construire le chemin absolu vers le fichier YAML
        yaml_path = './conf/real.yaml'  # Chemin correct du fichier YAML

        # Charger le fichier YAML
        with open(yaml_path, 'r') as f:
            env_vars = yaml.safe_load(f)
        
        # Ajouter les variables d'environnement
        for key, value in env_vars['all_configs'][0]['config'].items():
            logging.info(f"Setting environment variable: {key} = {value}")
            os.environ[key] = str(value)
    except Exception as e:
        print(f"Error while loading configuration: {str(e)}")


        
        
def set_yaml_env_param(param_name, param_value):
    try:
        with open('./conf/real.yaml', 'r') as f:
            env_vars = yaml.safe_load(f)   
            env_vars['all_configs'][0]['config'][param_name] = param_value
        with open('./conf/real.yaml', 'w') as f:
            yaml.dump(env_vars, f)
    except Exception as e:
        logging.error(f"Error while setting yaml conf file: {str(e)}")
        
def check_env_from_yaml():
    try:     
        with open('./conf/real.yaml', 'r') as f:
            env_vars = yaml.safe_load(f)         
        if 'all_configs' in env_vars and len(env_vars['all_configs']) > 0 and 'config' in env_vars['all_configs'][0]:
            for key, value in env_vars['all_configs'][0]['config'].items():
                logging.info(f"Check variable : {key} = {value}")
                if key in os.environ:
                    logging.info(f"[OK] - {key}: {os.environ[key]}")
                else: 
                    raise Exception("./conf/real.yaml configuration file initial check failed")
    except Exception as e:
        print(f"Error while loading configuration: {str(e)}")    

def get_root_directory():
    """
    Returns the root directory of the current drive on a Windows system.
    """
    # Get the current working directory
    current_directory = os.getcwd()
    
    # Extract the drive letter and form the root directory path
    drive, _ = os.path.splitdrive(current_directory)
    root_directory = f"{drive}\\"
    
    return root_directory


def get_file_list(root_dir, file_extensions):
    """
    Crawls the given directory and returns a list of files with the specified extensions.

    Parameters:
    root_dir (str): The root directory to start crawling from.
    file_extensions (tuple): A tuple of file extensions to look for.

    Returns:
    list: A list of file paths.
    """
    file_list = []
    for foldername, subfolders, filenames in os.walk(root_dir):
        if not 'python' in foldername and not 'node_modules' in foldername:
            for filename in filenames:
                if filename.lower().endswith(file_extensions):
                    print(f"File discovered {os.path.join(foldername, filename)}")
                    file_list.append(os.path.join(foldername, filename))
        else:
            print(f"skipping {filename} in {foldername}")
    return file_list

def add_to_zip(lock, zip_filename, file_path, root_dir):
    """
    Adds a file to the zip archive in a thread-safe manner.

    Parameters:
    lock (Lock): A threading lock to ensure thread safety.
    zip_filename (str): The name of the zip file.
    file_path (str): The path of the file to add.
    root_dir (str): The root directory to maintain relative paths.
    """
    with lock:
        try:
            with zipfile.ZipFile(zip_filename, 'a', zipfile.ZIP_DEFLATED) as zipf:
                zipf.write(file_path, os.path.relpath(file_path, root_dir))
                print(f"Added {file_path} to {zip_filename}")
        except Exception as e:
            print(f"Error while adding file {file_path}: {str(e)}")
            print(traceback.format_exc())
            
def crawl_and_zip(root_dir, zip_filename):
    """
    Crawls the given directory and creates a zip file containing all .ppt, .pdf, .docx, and .txt files.

    Parameters:
    root_dir (str): The root directory to start crawling from.
    zip_filename (str): The name of the output zip file.
    """
    file_extensions = ('.ppt', '.pdf', '.docx', '.txt')
    file_list = get_file_list(root_dir, file_extensions)
    print(f" {len(file_list)} files discovered")
    # Create a lock for thread safety
    lock = Lock()
    # Create a ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
        futures = [executor.submit(add_to_zip, lock, zip_filename, file_path, root_dir) for file_path in file_list]
        
        # Wait for all threads to complete
        for future in as_completed(futures):
            future.result()
    print(f"Zip file created: {zip_filename}")
    return zip_filename

def discover_all_local_documents():
    outzipfile_path = f"./data/uploads/zip/discovery/local_documents_{uuid.uuid4()}.zip"
    return crawl_and_zip(get_root_directory(), outzipfile_path) #"C:/work/graphs/advanced_rag_experiments/rest_backend/data/pdf"