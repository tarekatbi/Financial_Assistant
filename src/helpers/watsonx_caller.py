import logging
import requests
from ratelimit import limits, sleep_and_retry
import os
from ibm_cloud_sdk_core import IAMTokenManager
from ibm_cloud_sdk_core.authenticators import IAMAuthenticator, BearerTokenAuthenticator
import traceback
import json

"""
This class expects a service config dictionnary (json) that looks like this :
{
    'service_endpoint' : 
    'api_key'  : 
    'project_id' :     
}
Class example usages:
#initialize
service_config = {
    'service_endpoint' : os.getenv('WXAI_INFER_ENDPOINT'),
    'api_key'  : os.getenv('WXAI_ACCESS_KEY'),
    'project_id' : os.getenv('WXAI_PROJECT_ID'),
}
wx_wrapper_test = WxaiWrapper(service_config)
llm_params = {
            "decoding_method": "greedy",
            "temperature": 0.4,
            #"top_p": 1,
            # "top_k": 50,
                "random_seed": 33,
            #"repetition_penalty": 2,
            "min_new_tokens": 1,
            "max_new_tokens": 800
}
#Batch mode
print(wx_wrapper_test.generate_ga_batch('Hello what is your name', "ibm-mistralai/mixtral-8x7b-instruct-v01-q", llm_params))
#Streaming mode
print('Stream mode test')
for chunk in wx_wrapper_test.generate_ga_stream('Hello what is your name', "ibm-mistralai/mixtral-8x7b-instruct-v01-q", llm_params):
    print(f'Chunk {chunk}')
    
"""
class WxaiWrapper(object):
    def __init__(self, service_config):
        if 'service_endpoint' not in service_config or 'api_key' not in service_config or 'project_id' not in service_config:
            raise Exception("No watsonx.ai API keys configured, please review conf/real.yaml env file ")
        self.wxai_conf_url_endpoint = service_config['service_endpoint']
        self.wxai_conf_apikey = service_config['api_key']
        self.wxai_conf_project_id = service_config['project_id']
        self.initalize_waxiapi_ga()
        self.default_llm_params =  {
                    #"decoding_method": os.getenv('WXAI_CONF_DECODING_METHOD'),
                    #"temperature": float(os.getenv('WXAI_CONF_TEMPERATURE')),
                    #"top_p": 1,
                    # "top_k": 50,
                     #"random_seed": 33,
                    #"repetition_penalty": 2,
                    #"min_new_tokens": int(os.getenv('WXAI_CONF_MIN_TOKEN')),
                    #"max_new_tokens": int(os.getenv('WXAI_CONF_MAX_TOKEN'))
                    }    

    def validate_config(self):
        res = {'status' : 'OK'}
        try: 
            self.access_token = IAMTokenManager(apikey = self.wxai_conf_apikey,url = "https://iam.cloud.ibm.com/identity/token").get_token()
            if self.access_token is None:
               res['status'] = 'KO' 
        except Exception as e:
            logging.error("Error while validating presto connexion")  
            res['status'] = 'KO'
        return res    
       
    def initalize_waxiapi_ga(self):
        self.access_token = IAMTokenManager(apikey = self.wxai_conf_apikey,url = "https://iam.cloud.ibm.com/identity/token").get_token()
        self.project_id = self.wxai_conf_project_id
        models_json = requests.get(self.wxai_conf_url_endpoint + '/ml/v1-beta/foundation_model_specs?version=2022-08-01&limit=50',
                                headers={
                                            'Authorization': f'Bearer {self.access_token}',
                                            'Content-Type': 'application/json',
                                            'Accept': 'application/json'
                                    }).json()
        self.model_ids = (m['model_id'] for m in models_json['resources'])
        logging.debug(f"Available models {models_json}")

 
    @sleep_and_retry
    @limits(calls=1, period=1)   
    def generate_ga_batch(self, input, model_id, parameters):
        self.initalize_waxiapi_ga()
        logging.info(f"Calling {model_id} for inference")
        wml_url = f"{self.wxai_conf_url_endpoint}/ml/v1-beta/generation/text?version=2023-05-28"
        Headers = {
            "Authorization": "Bearer " + self.access_token,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        data = {
            "model_id": model_id,
            "input": input,
            "parameters": parameters,
            "project_id": self.wxai_conf_project_id
        }
        logging.info(f"headers {Headers}, data {data}")
        try:
            response = requests.post(wml_url, json=data, headers=Headers)
            if response.status_code == 200:
                return response.json()#["results"][0]
            else:
                return response.text
        except Exception as e:
            logging.error(f"Error while performance REST API call for inference {str(e)}")
            return {'fail_reason': f'inference api error {str(e)}'}        


    def generate_ga_stream(self, input, model_id, parameters):
        logging.info(f"Calling {model_id} for inference")
        self.initalize_waxiapi_ga()
        wml_url = f"{self.wxai_conf_url_endpoint}/ml/v1-beta/generation/text_stream?version=2023-05-28"
        Headers = {
            "Authorization": "Bearer " + self.access_token,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        data = {
            "model_id": model_id,
            "input": input,
            "parameters": parameters,
            "project_id": self.wxai_conf_project_id
        }
        try:
            response = requests.post(wml_url, json=data, headers=Headers, stream=True)
            if response and response.status_code == 200:
                for chunk in response.iter_content(chunk_size=1024):
                    logging.debug(f">>>>>>>>>>>>>>> Sending chunk to stream : {type(chunk)} {chunk}")
                    chunk_json = chunk.decode('utf8')
                    yield chunk_json
            else:
                raise Exception(f"Failed to fetch data from API. Status code: {response.status_code}")
        except Exception as e:
            logging.error(f"Error while performance REST API call for inference: {str(e)}")
            return {'fail_reason': f'inference api error, reason: {str(e)}'}        


    def create_embeddings(self, sentences_array):     
        res = []
        self.initalize_waxiapi_ga()   
        logging.info(f"Calling {os.getenv('HF_EMBEDING_MODEL_ID')} for embddings inference")
        url = f'{self.wxai_conf_url_endpoint}/ml/v1/text/embeddings?version=2024-05-02'
        print(url)
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Authorization': "Bearer " + self.access_token
        }
        data = {
            "inputs": sentences_array,
            "parameters": {
               # "truncate_input_tokens": 256,
                "return_options": {
                    "input_text": True
                }
            },
            "model_id": os.getenv("HF_EMBEDING_MODEL_ID"),
            "project_id": self.wxai_conf_project_id
        }
        print(data['model_id'])
        try:
            response = requests.post(url, headers=headers, json=data)
            if 'input_token_count'  in response.json():
                logging.info(f"input tokens used: {response.json()['input_token_count']}") 
            if 'results' in response.json():
                for embed in  response.json()['results']:
                    res.append(embed['embedding'])  
                return res
            else:
                logging.error(f"No results found in {response.json()}")
                logging.error(f"Linked input chunks ({len(sentences_array)}): {sentences_array}")
        except Exception as e:
            logging.error(f"Error while calling embeddings service: {str(e)}")
            logging.error(traceback.format_exc())
    

    

"""
service_config = {
    'service_endpoint' : os.getenv('WXAI_INFER_ENDPOINT'),
    'api_key'  : os.getenv('WXAI_ACCESS_KEY'),
    'project_id' : os.getenv('WXAI_PROJECT_ID'),
}
wx_wrapper_test = WxaiWrapper(service_config)
llm_params = {
            "decoding_method": "greedy",
            "temperature": 0.4,
            #"top_p": 1,
            # "top_k": 50,
                "random_seed": 33,
            #"repetition_penalty": 2,
            "min_new_tokens": 1,
            "max_new_tokens": 800
}
sentences = [
        "A foundation model is a large-scale generative AI model that can be adapted to a wide range of downstream tasks.",
        "Generative AI a class of AI algorithms that can produce various types of content including text, source code, imagery, audio, and synthetic data.",
        "A foundation model is a large-scale generative AI model that can be adapted to a wide range of downstream tasks."
    ]
print(type(sentences))
#Batch mode
#print(wx_wrapper_test.generate_ga_batch('Hello what is your name', "ibm-mistralai/mixtral-8x7b-instruct-v01-q", llm_params))
embeddings = wx_wrapper_test.create_embeddings(sentences)
#print(f"Result contains {embeddings}")
print(f"Result contains {len(embeddings)}")
"""