import json
import logging
import os
import uvicorn
import asyncio
from fastapi import FastAPI, Request, UploadFile
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
    # logger.info(f"/upload-env-ini begin")
    file_content = await file.read()
    file_dict = json.loads(file_content)
    # file_dict = yaml.safe_load(file_content)

    global_store = GlobalStore(**file_dict)
    await global_store.post_init()
    
    # await SseEvent(data=SseEventData(id='apstra-host', value=global_store.apstra['host'])).send()
    # await SseEvent(data=SseEventData(id='apstra-port', value=global_store.apstra['port'])).send()
    # await SseEvent(data=SseEventData(id='apstra-username', value=global_store.apstra['username'])).send()
    # # await SseEvent(data=SseEventData(id='apstra-password', value=global_store.apstra['password'])).send()

    # await SseEvent(data=SseEventData(id='main_bp', value=global_store.target['main_bp'])).send()
    # await SseEvent(data=SseEventData(id='tor_bp', value=global_store.target['tor_bp'])).send()

    await SseEvent(data=SseEventData(id='load-env-div').done()).send()

    await sse_logging(f"/upload-env-json end")
    return await connect()


@app.get("/connect")
async def connect():
    """
    login to the server and blueprints
    then sync the data
    """
    global global_store

    await sse_logging(f"/connect begin")
    await SseEvent(data=SseEventData(id='connect').loading()).send()

    version = await global_store.login_server()

    # await global_store.tor_bp_selection()

    # await global_store.login_blueprint()
    await SseEvent(data=SseEventData(id=ButtonIdEnum.BUTTON_CONNECT).done()).send()
    await SseEvent(data=SseEventData(id=ButtonIdEnum.BUTTON_PULL_CONFIG).enable()).send()
    await SseEvent(data=SseEventData(id=ButtonIdEnum.BUTTON_PULL_JSON).enable()).send()

    await global_store.bp_selections()

    await sse_logging(f"/connect end")
    return f"connected {version}"


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


@app.get("/login-main-bp")
async def login_main_bp(request: Request):
    """
    login to the server and blueprints
    then sync the data
    """
    global global_store

    # body = await request.body()  # main-bp=richmond
    # logging.warning(f"login-main-bp begin, {request.headers=}, {request.query_params=}, {body=}")
    # async with request.form() as form:
    #     for key, value in form.items():
    #         logging.warning(f"login-main-bp form: {key=} {value=}")   
    #     bp_name = form["main-bp"]
    #     logging.warning(f"login-main-bp form: {bp_name=}")     
    new_bp = request.query_params.get("main-bp")
    await global_store.login_a_blueprint(new_bp)

    # await sse_logging(f"/login-main-bp begin")
    # await SseEvent(data=SseEventData(id='login-main-bp').loading()).send()

    # await global_store.login_main_bp()

    # await SseEvent(data=SseEventData(id='login-main-bp').done()).send()
    await sse_logging(f"/login-main-bp end")
    return "login-main-bp"




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


async def main():
    # dotenv.load_dotenv()
    # app_host = os.getenv("app_host") or "127.0.0.1"
    # app_port = int(os.getenv("app_port")) or 8000
    app_host = "127.0.0.1"
    app_port = 8000
    uvicorn.run(app, host=app_host, port=app_port, log_level="debug")


def start():
    app_host = "127.0.0.1"
    app_port = 8000
    uvicorn.run("src.main:app", host=app_host, port=app_port, log_level="debug")

if __name__ == "__main__":
    asyncio.run(main())
