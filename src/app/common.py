
from datetime import datetime
from enum import StrEnum
import glob
from io import BytesIO
import json
import logging
from dataclasses import dataclass, asdict, field
import asyncio
import os
import tarfile
from typing import Any, Dict, Optional
import tempfile

from ck_apstra_api.apstra_session import CkApstraSession
from ck_apstra_api.apstra_blueprint import CkApstraBlueprint

sse_queue = asyncio.Queue()

async def sse_logging(text, logger=None):
    if logger:
        logger.info(text)
    else:
        logging.info(text)
    await SseEvent(data=SseEventData(id='event-box-text', add_text=f"{datetime.now():%H:%M:%S:%f} {text}\n")).send()

class DataStateEnum(StrEnum):
    LOADED = 'done'
    INIT = 'init'
    LOADING = 'loading'
    DONE = 'done'
    ERROR = 'error'
    NONE = 'none'
    DISABLED = 'disabled'
    DATA_STATE = 'data-state'

@dataclass
class SseEventData:
    id: str
    state: Optional[str] = None
    value: Optional[str] = None
    disabled: Optional[bool] = None  # for disable button
    visibility: Optional[bool] = None # for visable button
    href: Optional[str] = None
    target: Optional[str] = None
    element: Optional[str] = None
    selected: Optional[bool] = None
    do_remove: Optional[bool] = None
    just_value: Optional[bool] = None  # to reset file upload
    add_text: str = '' # to add text to the value

    def visible(self):
        self.visibility = 'visible'
        return self
    
    def hidden(self):
        self.visibility = 'hidden'
        return self

    def loading(self):
        self.state = DataStateEnum.LOADING
        return self    

    def done(self):
        self.disabled = False
        self.state = DataStateEnum.DONE
        return self

    def init(self):
        self.state = DataStateEnum.INIT
        return self

    def error(self):
        self.state = DataStateEnum.ERROR
        return self

    def disable(self):
        self.disabled = True
        self.state = DataStateEnum.DISABLED
        # logging.info(f"SseEventData.disable() ######## {self=}")
        return self
    
    def enable(self):
        self.disabled = False
        return self
    
    def set_href(self, href):
        self.href = href
        return self
    
    def set_target(self, target='_blank'):
        self.target = target
        return self

    def remove(self):
        self.do_remove = True
        return self
  

@dataclass
class SseEvent:
    data: SseEventData
    # event: str = field(default_factory=SseEventEnum.DATA_STATE)     # SseEventEnum.DATA_STATE, SseEventEnum.TBODY_GS, SseEventEnum.BUTTION_DISABLE
    event: str = 'data-state'    # SseEventEnum.DATA_STATE, SseEventEnum.TBODY_GS, SseEventEnum.BUTTION_DISABLE

    async def send(self):
        await asyncio.sleep(0.05)
        try:
            sse_dict = {'event': self.event, 'data': json.dumps(asdict(self.data))}
        except Exception as e:
            logging.error(f"SseEvent.send() {e=} {self}")
            return
        # logging.info(f"######## SseEvent put {sse_queue.qsize()=} {self=}")        
        await sse_queue.put(sse_dict)



@dataclass
class ApstraServer:
    host: str
    port: str
    username: str
    password: str
    logging_level: str = 'DEBUG'
    apstra_server: Any = None  # CkApstraSession

@dataclass
class BpTarget:
    tor_bp: str
    main_bp: str = 'ATLANTA-Master'
    tor_im_new: str = '_ATL-AS-5120-48T'
    cabling_maps_yaml_file: str = 'tests/fixtures/sample-cabling-maps.yaml'


@dataclass
class GlobalStore:
    apstra: ApstraServer
    target: BpTarget

    bp: Dict[str, Any] = field(default_factory=dict)  # main_bp, tor_bp (CkApstraBlueprint)

    logger: Any = logging.getLogger("GlobalStore")  # logging.Logger

    tgz_name: Optional[str] = None
    tgz_data: Optional[Any] = None

    async def post_init(self):
        self.migration_status = None

    async def sse_logging(self, text):
        await sse_logging(text, self.logger)


    async def login_server(self) -> str:
        await self.sse_logging(f"login_server() begin")
        self.apstra_server = CkApstraSession(self.apstra['host'], int(self.apstra['port']), self.apstra['username'], self.apstra['password'])
        await self.sse_logging(f"login_server(): {self.apstra_server=}")
        return self.apstra_server.version

    async def login_blueprint(self) -> None:
        await self.sse_logging(f"login_blueprint")
        for role in ['main_bp']:
            label = self.target[role]
            bp = CkApstraBlueprint(self.apstra_server, label)
            self.bp[role] = bp
            await self.sse_logging(f"login_blueprint {bp=}")
            id = bp.id
            # value = f'<a href="{self.apstra_url}/#/blueprints/{id}/staged" target="_blank">{label}</a>'
            await self.sse_logging(f"login_blueprint() end")
        return

    async def write_to_file(self, file_name, content):
        MIN_SIZE = 2  # might have one \n
        if len(content) > MIN_SIZE:
            with open(file_name, 'w') as f:
                f.write(content)
            await self.sse_logging(f"write_to_file(): {os.path.basename(file_name)}")

    async def pull_config(self) -> str:
        await self.sse_logging(f"pull_config() begin")

        await self.login_blueprint()

        bp_label = self.target['main_bp']
        the_bp = self.bp['main_bp']
        self.tgz_name = f"/tmp/{bp_label}.tgz"        

        with tempfile.TemporaryDirectory() as tmpdirname:
            # await self.sse_logging(f"pull_config(): {tmpdirname=}")
            top_dir = f"{tmpdirname}/{bp_label}"
            os.mkdir(top_dir)

            for switch in [x['switch'] for x in the_bp.query("node('system', system_type='switch', name='switch')")]:
                system_label = switch['label']
                system_id = switch['id']
                system_serial = switch['system_id']
                system_dir = f"{top_dir}/{system_label}"
                os.mkdir(system_dir)
                await self.sse_logging(f"pull_config(): {system_label=}")

                if system_serial:
                    pristine_config = self.apstra_server.get_items(f"systems/{system_serial}/pristine-config")['pristine_data'][0]['content']
                    await self.write_to_file(f"{system_dir}/pristine.txt", pristine_config)

                rendered_confg = the_bp.get_item(f"nodes/{system_id}/config-rendering")['config']
                self.write_to_file(f"{system_dir}/rendered.txt", rendered_confg)

                begin_configlet = '------BEGIN SECTION CONFIGLETS------'
                begin_set = '------BEGIN SECTION SET AND DELETE BASED CONFIGLETS------'

                config_string = rendered_confg.split(begin_configlet)
                await self.write_to_file(f"{system_dir}/intended.txt", config_string[0])
                if len(config_string) < 2:
                    # no configlet. skip
                    continue

                configlet_string = config_string[1].split(begin_set)
                await self.write_to_file(f"{system_dir}/configlet.txt", configlet_string[0])
                if len(configlet_string) < 2:
                    # no configlet in set type. skip
                    continue

                await self.write_to_file(f"{system_dir}/configlet-set.txt", configlet_string[1])

            with tarfile.open(self.tgz_name, "w:gz") as archive:
                archive.add(top_dir, recursive=True, arcname=bp_label)

            with open(self.tgz_name, 'rb') as f:
                self.tgz_data = BytesIO(f.read())

            await self.sse_logging(f"pull_config(): {self.tgz_name=} {type(self.tgz_data)=}")
        # await self.sse_logging(f"pull_config(): {self.apstra_server=}")
        return


global_store: GlobalStore = None  # initialized by main.py

