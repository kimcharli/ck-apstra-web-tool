import json
import logging
import os
import uvicorn
import asyncio
from fastapi import FastAPI, Request, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from sse_starlette.sse import EventSourceResponse

from app.common import SseEvent, SseEventData, sse_logging, sse_queue, global_store, GlobalStore

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
    await SseEvent(data=SseEventData(id='connect').done()).send()
    await sse_logging(f"/connect end")
    return f"connected {version}"


@app.get("/pull-config")
async def pull_config():
    """
    login to the server and blueprints
    then sync the data
    """
    global global_store

    await sse_logging(f"/pull-config begin")
    await SseEvent(data=SseEventData(id='pull-config').loading()).send()

    await global_store.pull_config()

    # await global_store.tor_bp_selection()

    # await global_store.login_blueprint()
    await SseEvent(data=SseEventData(id='pull-config').done()).send()
    await sse_logging(f"/pull-config end")
    headers = {'Content-Disposition': f'attachment; filename="{os.path.basename(global_store.tgz_name)}"'}
    return StreamingResponse(global_store.tgz_data, media_type='application/octet-stream', headers=headers)







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
