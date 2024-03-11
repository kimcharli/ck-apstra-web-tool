from dataclasses import dataclass
from typing import Any
import logging



@dataclass
class GenericSystemWorker:
    global_store: Any
    logger: Any = logging.getLogger('GenericSystemWorker')

    generic_systems: Any = None  # Dict[str, GenericSystem]


    async def pull_generic_systems(self):
        return
        for server_link in self.tor_bp.get_switch_interface_nodes():
            switch_label = server_link[CkEnum.MEMBER_SWITCH]['label']  # tor switch which will be access switch
            switch_intf = server_link[CkEnum.MEMBER_INTERFACE]['if_name']
            switch_id = server_link[CkEnum.MEMBER_SWITCH]['id']
            if tor_gs is None:

                tor_gs = global_store.tor_gs = await make_tor_gs_data(switch_label)
                # tor_gs.label = cls.guess_tor_gs_label(switch_label)
                if tor_gs.label is None:
                    self.logger.error(f"sync_tor_generic_systems() irregular label: {switch_label=}")
                    return
            access_switches.setdefault(switch_label, AccessSwitch(label=switch_label, tor_id=switch_id))
            old_server_label = server_link[CkEnum.GENERIC_SYSTEM]['label']
            new_label = self.make_new_label(old_server_label)
            tbody_id = f"gs-{new_label}"
            # link_id = server_link[CkEnum.LINK]['id']
            old_switch_intf_id = server_link[CkEnum.MEMBER_INTERFACE]['id']
            old_ae_name = server_link[CkEnum.AE_INTERFACE]['if_name'] if server_link[CkEnum.AE_INTERFACE] else ''
            old_ae_id = server_link[CkEnum.EVPN_INTERFACE]['id'] if server_link[CkEnum.EVPN_INTERFACE] else old_switch_intf_id
            speed = server_link[CkEnum.LINK]['speed']
            old_server_intf = server_link[CkEnum.GENERIC_SYSTEM_INTERFACE]['if_name'] or ''
            tag = server_link[CkEnum.TAG]['label'] if server_link[CkEnum.TAG] != None else None

            server_data = generic_systems.setdefault(tbody_id, _GenericSystem(old_label=old_server_label, new_label=new_label, group_links={}))
            # check if leaf_gs
            if switch_intf in ['et-0/0/48', 'et-0/0/49']:
                server_data.is_leaf_gs = True
                leaf_gs_label = old_server_label
            ae_data = server_data.group_links.setdefault(old_ae_id, _GroupLink(old_ae_name=old_ae_name, old_ae_id=old_ae_id, speed=speed, old_tagged_vlans={}, old_untagged_vlan={}, links={}))
            link_data = ae_data.links.setdefault(old_switch_intf_id, _Memberlink(switch=switch_label, switch_intf=switch_intf, old_server_intf=old_server_intf, old_tags=[], new_tags=[]))
            if tag:
                link_data.add_old_tag(tag)
                # await self.sse_logging(f"sync_tor_generic_systems {tag=} {server_label=} {tbody_id=}")            
        # set index number for each generic system
        for index, v in enumerate(generic_systems.values()):
            v.index = index + 1

        # render leaf_gs
        await SseEvent(data=SseEventData(id='leaf-gs-label', value=leaf_gs_label)).send()

        await SseEvent(data=SseEventData(id='tor1-label', value=global_store.access_switch_pair[0])).send()
        await SseEvent(data=SseEventData(id='tor2-label', value=global_store.access_switch_pair[1])).send()
        await SseEvent(data=SseEventData(id='tor1-box').done()).send()
        await SseEvent(data=SseEventData(id='tor2-box').done()).send()

        await self.sse_logging(f"sync_tor_generic_systems end {len(generic_systems)=}")
    
        return
