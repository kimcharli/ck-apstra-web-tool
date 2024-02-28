
from datetime import datetime
from enum import StrEnum
import json
import logging
from dataclasses import dataclass, asdict
import asyncio
from typing import Any, Optional

from ck_apstra_api.apstra_session import CkApstraSession

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

    logger: Any = logging.getLogger("GlobalStore")  # logging.Logger

    async def post_init(self):
        self.migration_status = None

    async def sse_logging(self, text):
        await sse_logging(text, self.logger)


    async def login_server(self) -> str:
        await self.sse_logging(f"login_server() begin")
        self.apstra_server = CkApstraSession(self.apstra['host'], int(self.apstra['port']), self.apstra['username'], self.apstra['password'])
        await self.sse_logging(f"login_server(): {self.apstra_server=}")
        return self.apstra_server.version


global_store: GlobalStore = None  # initialized by main.py

