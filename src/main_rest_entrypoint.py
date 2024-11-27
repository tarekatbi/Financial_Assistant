from apiflask import APIFlask
from flask_cors import CORS
from logging.config import dictConfig
import logging
import os
from helpers.utils import init_env_from_yaml
from helpers.wxdata_presto_utils import WxdataPrestoUtils
from helpers.watsonx_caller import WxaiWrapper
from flask import jsonify

# Initialiser l'environnement à partir d'un fichier YAML
init_env_from_yaml()

app_loglevel = logging.INFO

dictconfig = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {
            "format": "%(asctime)s - %(name)s - {%(filename)s:%(lineno)d}: %(levelname)s - %(message)s"
        }
    },
    "handlers": {
        "file_handler": {
            "class": "logging.FileHandler",
            "level": app_loglevel,
            "formatter": "simple",
            "filename": "./ragapp.log",
            "encoding": "utf8"
        },
        "console_handler": {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
            'level': app_loglevel
        }
    },
    "root": {
        "level": app_loglevel,
        "handlers": ["file_handler", "console_handler"]
    }
}
dictConfig(dictconfig)
logging.info("Logging configured ... Starting Flask rest endpoint")

credentials = {
    "host": os.getenv('WXDATA_HOST'),
    "port": int(os.getenv('WXDATA_PORT')),
    "user": os.getenv('WXDATA_USER'),
    "password": os.getenv('WXDATA_PASSWORD'),
    "catalog": os.getenv('WXDATA_CATALOG'),
}

wx_utils = WxdataPrestoUtils(credentials)

service_config = {
    "service_endpoint": os.getenv('WXAI_INFER_ENDPOINT'),
    "api_key": os.getenv('WXAI_ACCESS_KEY'),
    "project_id": os.getenv('WXAI_PROJECT_ID')
}
wx_ai = WxaiWrapper(service_config)

app = APIFlask(__name__, title='My API', version='1.0')
app.config['SECRET_KEY'] = 'your secret key'
cors = CORS(app)

# Stocker wx_utils dans la configuration de l'application
app.config['WX_UTILS'] = wx_utils
app.config['WXAI'] = wx_ai

@app.get('/ping')
def ping_route():
    return "pong"

@app.get('/openapi.json')
def get_openapi_spec():
    return jsonify(app.spec)

# Importer et enregistrer les routes
from routes import bp as routes_bp
app.register_blueprint(routes_bp)

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=3333)