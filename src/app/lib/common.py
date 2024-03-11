
from datetime import datetime
from enum import StrEnum
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

class ButtonIdEnum(StrEnum):
    BUTTON_ENV_DIV = 'load-env-div'
    LAST_MESSAGE = 'last-message'
    BUTTON_LOGIN = 'login'
    BUTTON_PULL_CONFIG = 'pull-config'
    BUTTON_PULL_JSON = 'pull-bp-json'
    BUTTON_PUSH_JSON = 'push-bp-json'

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
    __slots__ = ['apstra', 'main_blueprint', 'blueprints', 'logger', 'tgz_name', 'tgz_data', 'json_data']
    apstra: ApstraServer

    main_blueprint: str
    blueprints: Dict[str, Any]

    logger: Any  # logging.Logger

    tgz_name: Optional[str]
    tgz_data: Optional[Any]
    json_data: Optional[Any]  # to save bp json data

    @property
    def apstra_server(self):
        return self.apstra.apstra_server

    async def post_init(self, file_dict: dict):
        await self.sse_logging(f"post_init() begin")
        self.apstra = ApstraServer(**file_dict['apstra'])
        self.logger.warning(f"post_init(): {file_dict=} {self.apstra=}")
        await SseEvent(data=SseEventData(id='apstra-host', just_value=self.apstra.host)).send()
        await SseEvent(data=SseEventData(id='apstra-port', just_value=self.apstra.port)).send()
        await SseEvent(data=SseEventData(id='apstra-username', just_value=self.apstra.username)).send()
        await SseEvent(data=SseEventData(id='apstra-password', just_value=self.apstra.password)).send()
        await self.sse_logging(f"post_init() end")

    async def sse_logging(self, text):
        await sse_logging(text, self.logger)


    async def login_server(self) -> str:
        await self.sse_logging(f"login_server() begin")        
        apstra_server = CkApstraSession(self.apstra.host, int(self.apstra.port), self.apstra.username, self.apstra.password)
        self.apstra.apstra_server = apstra_server
        await SseEvent(data=SseEventData(id='apstra-version', just_value=apstra_server.version)).send()
        await self.sse_logging(f"login_server(): {apstra_server=}")
        return apstra_server.version

    async def login_blueprint(self, bp_label: str):
        await self.sse_logging(f"login_blueprint({bp_label=})")
        bp = CkApstraBlueprint(self.apstra_server, bp_label)
        self.main_blueprint = bp_label
        self.blueprints[bp_label] = bp

        await self.sse_logging(f"login_blueprint {bp=}, {self.blueprints=}")
        return bp

    async def write_to_file(self, file_name, content):
        MIN_SIZE = 2  # might have one \n
        if len(content) > MIN_SIZE:
            with open(file_name, 'w') as f:
                f.write(content)
            await self.sse_logging(f"write_to_file(): {os.path.basename(file_name)}")

    async def pull_config(self) -> None:
        await self.sse_logging(f"pull_config() begin")

        bp_label = self.main_blueprint
        the_bp = self.blueprints[bp_label]
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

        return


    async def pull_bp_json(self) -> str:
        """
        pull the main blueprint json and store at self.json_data, return the file name
        """
        await self.sse_logging(f"pull_bp_json() begin")

        bp_label = self.main_blueprint
        # self.logger.warning(f"pull_bp_json(): {self.blueprints=}")
        the_bp = self.blueprints[bp_label]
        bp_json = the_bp.dump()
        # self.logger.warning(f"pull_bp_json(): {len(bp_json)=} {type(bp_json)=}")
        self.json_data = BytesIO(json.dumps(bp_json).encode('utf-8'))

        return f"{bp_label}.json"


    async def pull_env_json(self) -> str:
        """
        Store the same env json file at self.json_data, return the file name
        """
        await self.sse_logging(f"pull_env_json() begin")

        sample_env = """
            {
                "apstra": {
                    "host": "10.85.192.45",
                    "port": "443",
                    "username": "admin",
                    "password": "zaq1@WSXcde3$RFV",
                    "logging_level": "DEBUG"   
                }
            }"""
        filename = 'env-example.json'
        self.json_data = BytesIO(sample_env.encode('utf-8'))
        await self.sse_logging(f"pull_env_json() end {filename=}")
        return filename
    

    async def bp_selections(self):
        blueprints = self.apstra_server.get_items('blueprints')
        for bp in blueprints['items']:
            label = bp['label']
            await SseEvent(data=SseEventData(id='main_bp_select', element='option', value=label)).send()
        await SseEvent(data=SseEventData(id='main_bp_div').done()).send()
        return


    async def push_bp_json(self, file_dict: dict, new_bp_name: str) -> str:
        """
        Create a new blueprint from the json file. Return the status code
        """
        await self.sse_logging(f"push_bp_json() begin")

        node_list = []
        for node_dict in file_dict['nodes'].values():
            if node_dict['type'] == 'system' and node_dict['system_type'] == 'switch' and node_dict['role'] != 'external_router':
                node_dict['system_id'] = None
                # node_dict['deploy_mode'] = 'undeploy'
            if node_dict['type'] == 'metadata':
                node_dict['label'] = new_bp_name      
            for k, v in node_dict.items():
                if k == 'tags':
                    if v is None or v == "['null']":
                        node_dict[k] = []
                elif k == 'property_set' and v is None:
                    node_dict.update({
                        k: {}
                    })
            node_list.append(node_dict)

        file_dict['label'] = new_bp_name

        relationship_list = [ rel_dict for rel_dict in file_dict['relationships'].values() ]

        bp_spec = { 
            'design': file_dict['design'], 
            'label': file_dict['label'], 
            'init_type': 'explicit', 
            'nodes': node_list,
            'relationships': relationship_list
        }
        bp_created = self.apstra.apstra_server.post('blueprints', data=bp_spec)
        return_text = bp_created.content
        await self.sse_logging(f"push_bp_json() BP bp_created = {return_text}")
        return return_text



global_store: GlobalStore = GlobalStore(None, None, {}, logging.getLogger("GlobalStore"), None, None, None)  # initialized by main.py
