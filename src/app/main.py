import json
import logging
import os
import uvicorn
import asyncio
from typing import Annotated
from fastapi import FastAPI, Request, UploadFile, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from sse_starlette.sse import EventSourceResponse

from app.lib.common import SseEvent, SseEventData, sse_logging, sse_queue, global_store, GlobalStore, ButtonIdEnum

logger = logging.getLogger(__name__)
app = FastAPI()

app.mount("/static", StaticFiles(directory="src/app/static"), name="static")
app.mount("/js", StaticFiles(directory="src/app/static/js"), name="js")
app.mount("/css", StaticFiles(directory="src/app/static/css"), name="css")
app.mount("/images", StaticFiles(directory="src/app/static/images"), name="images")



@app.post("/upload-env-json")
async def upload_env_ini(request: Request, file: UploadFile):
    """
    take environment yaml file to init global_store
    """
    global global_store

    await sse_logging(f"/upload-env-json begin")
    file_content = await file.read()
    file_dict = json.loads(file_content)
    await global_store.post_init(file_dict)
    
    await SseEvent(data=SseEventData(id=ButtonIdEnum.BUTTON_ENV_DIV).done()).send()
    await SseEvent(data=SseEventData(id=ButtonIdEnum.BUTTON_LOGIN).init().enable()).send()
    await SseEvent(data=SseEventData(id=ButtonIdEnum.LAST_MESSAGE, value=f"Uploaded {file.filename}")).send()

    await sse_logging(f"/upload-env-json end")
    return


@app.post("/login")
async def login(host: Annotated[str, Form()], port: Annotated[str, Form()], username: Annotated[str, Form()], password: Annotated[str, Form()]):
    """
    login to the server
    """
    global global_store

    logging.warning(f"login {host=} {port=} {username=} {password=}")

    await sse_logging(f"/login begin")
    await SseEvent(data=SseEventData(id='connect').loading()).send()

    version = await global_store.login_server(host, port, username, password)

    await SseEvent(data=SseEventData(id=ButtonIdEnum.BUTTON_LOGIN).done()).send()

    await global_store.bp_selections()

    await SseEvent(data=SseEventData(id=ButtonIdEnum.BUTTON_PUSH_JSON).init().enable()).send()
    await SseEvent(data=SseEventData(id=ButtonIdEnum.LAST_MESSAGE, value=f"connected {version}")).send()

    await sse_logging(f"/login end")

    return


@app.get("/pull-config")
async def pull_config():
    """
    download device configuration
    """
    global global_store

    await sse_logging(f"/pull-config begin")
    await SseEvent(data=SseEventData(id=ButtonIdEnum.BUTTON_PULL_CONFIG).loading()).send()

    await global_store.pull_config()
    tgz_name = os.path.basename(global_store.tgz_name)

    await SseEvent(data=SseEventData(id=ButtonIdEnum.BUTTON_PULL_CONFIG).done()).send()
    await sse_logging(f"/pull-config end")
    await SseEvent(data=SseEventData(id=ButtonIdEnum.LAST_MESSAGE, value=f"{tgz_name} downloaded")).send()
    headers = {'Content-Disposition': f'attachment; filename="{tgz_name}"'}
    return StreamingResponse(global_store.tgz_data, media_type='application/octet-stream', headers=headers)


@app.get("/pull-bp-json")
async def pull_bp_json():
    """
    download blueprint in json
    """
    global global_store

    await sse_logging(f"/pull-bp-json begin")
    await SseEvent(data=SseEventData(id=ButtonIdEnum.BUTTON_PULL_JSON).loading()).send()

    json_name = await global_store.pull_bp_json()

    await SseEvent(data=SseEventData(id=ButtonIdEnum.BUTTON_PULL_JSON).done()).send()
    await sse_logging(f"/pull-bp-json end")
    await SseEvent(data=SseEventData(id=ButtonIdEnum.LAST_MESSAGE, value=f"{json_name} downloaded")).send()
    headers = {'Content-Disposition': f'attachment; filename="{json_name}"'}
    return StreamingResponse(global_store.json_data, media_type='application/octet-stream', headers=headers)


@app.get("/login-main-bp", response_class=HTMLResponse)
async def login_main_bp(request: Request):
    """
    login to the server and blueprints
    then sync the data
    """
    global global_store

    logging.warning(f"login-main-bp {request=} {request.query_params=} {request.headers=}")
    # logging.warning(f"login-main-bp {request=} {request.query_params=}")

    new_bp = request.query_params.get("main-bp")
    await global_store.login_blueprint(new_bp)

    await SseEvent(data=SseEventData(id=ButtonIdEnum.BUTTON_PULL_CONFIG).enable()).send()
    await SseEvent(data=SseEventData(id=ButtonIdEnum.BUTTON_PULL_JSON).enable()).send()
    await sse_logging(f"/login-main-bp end")

    return f"login bp {new_bp}"




@app.get("/get-env-example")
async def get_env_example():
    """
    download sample env file in json
    """
    global global_store

    await sse_logging(f"/get_env_example begin")

    json_name = await global_store.pull_env_json()

    await sse_logging(f"/get_env_example end")
    await SseEvent(data=SseEventData(id=ButtonIdEnum.LAST_MESSAGE, value=f"{json_name} downloaded")).send()
    headers = {'Content-Disposition': f'attachment; filename="{json_name}"'}
    return StreamingResponse(global_store.json_data, media_type='application/octet-stream', headers=headers)




@app.post("/push-bp-json")
async def push_bp_json(request: Request, file: UploadFile):
    """
    take environment yaml file to init global_store
    """
    global global_store

    await sse_logging(f"/push-bp-json begin")
    file_content = await file.read()
    file_dict = json.loads(file_content)
    bp_name = file.filename.split(".json")[0]
    return_text = await global_store.push_bp_json(file_dict, bp_name)
    # logging.warning(f"push_bp_json {request=} {request.query_params=} {request.headers=} {file.filename=} {file.content_type=} {file.file=}")

    await sse_logging(f"/push-bp-json end")
    await SseEvent(data=SseEventData(id=ButtonIdEnum.BUTTON_PUSH_JSON).done()).send()
    await SseEvent(data=SseEventData(id=ButtonIdEnum.LAST_MESSAGE, value=return_text)).send()

    return


@app.get("/", response_class=HTMLResponse)
async def get_index_html(request: Request):
    return FileResponse("src/app/static/index.html")


@app.get('/sse')
async def sse(request: Request):
    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
            item = await sse_queue.get()
            # logging.info(f"######## event_generator get {sse_queue.qsize()=} {item=}")          
            yield item
            sse_queue.task_done()
            # set 0.05 to produce progressing
            await asyncio.sleep(0.05)
    return EventSourceResponse(event_generator())


def main():
    app_host = "127.0.0.1"
    app_port = 8001
    uvicorn.run(app, host=app_host, port=app_port, log_level="debug")

if __name__ == "__main__":
    main()
