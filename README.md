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

## work on GUI

1. Open web http://127.0.0.1:8001/
2. Download the Sample env file.
3. Update the env file, and save it.
4. Load the env file
5. Login
6. Select the blueprint
7. click Pull Device Conifg

# Misc



