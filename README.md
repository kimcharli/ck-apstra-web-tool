# ck-apstra-web-tool

# initial setup

```sh
python -m venv venv 
source venv/bin/activate
pip install -e .
deactivate 
```


# run

## Bring up the backend

```sh
source venv/bin/activate
pip install -e .
uvicorn src.app.main:app --reload --log-config=log_conf.yml --port 8001
```

## Pull down the device configuration

1. Open web http://127.0.0.1:8001/
2. Fill the server access information, or load the environment file
3. Login to the Asptra Server
4. Select the blueprint
5. click Pull Device Conifg

# Misc



