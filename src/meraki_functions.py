#!/usr/bin/env python3
"""
Copyright (c) 2024 Cisco and/or its affiliates.
This software is licensed to you under the terms of the Cisco Sample
Code License, Version 1.1 (the "License"). You may obtain a copy of the
License at
https://developer.cisco.com/docs/licenses
All use of the material herein must be in accordance with the terms of
the License. All rights not expressly granted by the License are
reserved. Unless required by applicable law or agreed to separately in
writing, software distributed under the License is distributed on an "AS
IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
or implied.
"""

__author__ = "Trevor Maco <tmaco@cisco.com>"
__copyright__ = "Copyright (c) 2024 Cisco and/or its affiliates."
__license__ = "Cisco Sample Code License, Version 1.1"

import os

import meraki
from dotenv import load_dotenv

# Load ENV Variable
load_dotenv()
MERAKI_API_KEY = os.getenv("MERAKI_API_KEY")
ORG_ID = os.getenv("ORG_ID")

# Meraki Dashboard Instance
dashboard = meraki.DashboardAPI(api_key=MERAKI_API_KEY, suppress_logging=True,
                                caller="Day0 Network Setup CiscoGVEDevNet", maximum_retries=25)


def network_name_to_id() -> dict:
    """
    Return dict of Network Names to ID (useful for translation of raw config to IDs)
    :return: Dict mapping of network name to network id
    """
    # Get Org Networks
    networks = dashboard.organizations.getOrganizationNetworks(ORG_ID, total_pages='all')

    net_name_to_id = {}
    for network in networks:
        net_name_to_id[network['name']] = network['id']

    return net_name_to_id


def org_config_templates() -> tuple[dict, dict]:
    """
    Get Meraki Org Config Templates, return mapping of config template name to id, and id to name
    https://developer.cisco.com/meraki/api-v1/get-organization-config-templates/
    :return: Dict mapping of config template name to id, and id to name
    """
    # Get Org Config Templates
    templates = dashboard.organizations.getOrganizationConfigTemplates(ORG_ID)

    config_template_name_to_id = {}
    config_template_id_to_name = {}
    for template in templates:
        config_template_name_to_id[template['name']] = template['id']
        config_template_id_to_name[template['id']] = template['name']

    return config_template_name_to_id, config_template_id_to_name


def network_to_config_templates(template_id_to_name: dict) -> dict:
    """
    Return dict of Network Names bound to config templates, to config template id
    :param template_id_to_name: Config Template ID to Name mapping
    :return: Dict mapping of network name to associated config template id
    """
    # Get Org Networks
    networks = dashboard.organizations.getOrganizationNetworks(ORG_ID, isBoundToConfigTemplate=True, total_pages='all')

    net_name_to_template_name = {}
    for network in networks:
        net_name_to_template_name[network['id']] = template_id_to_name[network['configTemplateId']]

    return net_name_to_template_name


def unbind_network(network_id: str, unbind_config: dict) -> tuple[str | None, dict | str]:
    """
    Unbind Meraki Network from Template, return response or (error code, error message)
    https://developer.cisco.com/meraki/api-v1/unbind-network/
    :param network_id: Network ID
    :param unbind_config: Unbind config payload
    :return: Error Code (if relevant), Response (or Error Message)
    """
    try:
        response = dashboard.networks.unbindNetwork(network_id, **unbind_config)
        return None, response
    except meraki.APIError as e:
        return e.status, str(e)
    except Exception as e:
        # SDK Error
        return "500", str(e)


def bind_network(network_id: str, bind_config: dict) -> tuple[str | None, dict | str]:
    """
    Bind Meraki Network from Template, return response or (error code, error message)
    https://developer.cisco.com/meraki/api-v1/bind-network/
    :param network_id: Network ID
    :param bind_config: Bind config payload
    :return: Error Code (if relevant), Response (or Error Message)
    """
    try:
        response = dashboard.networks.bindNetwork(network_id, **bind_config)
        return None, response
    except meraki.APIError as e:
        return e.status, str(e)
    except Exception as e:
        # SDK Error
        return "500", str(e)


def update_network(network_id: str, network_config: dict) -> tuple[str | None, dict | str]:
    """
    Update Meraki Network, return response or (error code, error message)
    https://developer.cisco.com/meraki/api-v1/update-network/
    :param network_id: Network ID
    :param network_config: Update Network payload
    :return: Error Code (if relevant), Response (or Error Message)
    """
    try:
        response = dashboard.networks.updateNetwork(network_id, **network_config)
        return None, response
    except meraki.APIError as e:
        return e.status, str(e)
    except Exception as e:
        # SDK Error
        return "500", str(e)


def create_network(network_config: dict, net_name_to_id: dict) -> tuple[
    str | None, dict | str]:
    """
    Create Meraki Network (or update existing network!), return response or (error code, error message)
    https://developer.cisco.com/meraki/api-v1/create-organization-network/
    :param network_config: Create Network payload
    :param net_name_to_id: Network Name to ID mapping (useful if network creation fails due to network already existing)
    :return: Error Code (if relevant), Response (or Error Message)
    """
    try:
        response = dashboard.organizations.createOrganizationNetwork(ORG_ID, **network_config)
        return None, response
    except meraki.APIError as e:
        # Special processing if network exists, update!
        if 'taken' in e.message['errors'][0]:
            # Safe assumptions network name must be in name_to_id mapping dictionary
            network_id = net_name_to_id[network_config['name']]
            return update_network(network_id, network_config)

        return e.status, str(e)
    except Exception as e:
        # SDK Error
        return "500", str(e)


def get_network_group_policies(network_id: str) -> tuple[str | None, dict | str]:
    """
    Get Meraki Network Group Policies, return response or (error code, error message)
    https://developer.cisco.com/meraki/api-v1/create-network-group-policy/
    :param network_id: Network ID
    :return: Error Code (if relevant), Response (or Error Message)
    """
    try:
        response = dashboard.networks.getNetworkGroupPolicies(network_id)
        return None, response
    except meraki.APIError as e:
        return e.status, str(e)
    except Exception as e:
        # SDK Error
        return "500", str(e)


def get_content_filtering_categories(network_id: str) -> tuple[str | None, dict | str]:
    """
    Get Meraki Content Filtering Categories, return response or (error code, error message)
    https://developer.cisco.com/meraki/api-v1/get-network-appliance-content-filtering-categories/
    :param network_id: Network ID
    :return: Error Code (if relevant), Response (or Error Message)
    """
    try:
        response = dashboard.appliance.getNetworkApplianceContentFilteringCategories(network_id)
        return None, response
    except meraki.APIError as e:
        return e.status, str(e)
    except Exception as e:
        # SDK Error
        return "500", str(e)


def get_vlans(network_id: str) -> tuple[str | None, list | str]:
    """
    Get Appliance VLANs, return response or (error code, error message)
    https://developer.cisco.com/meraki/api/get-network-appliance-vlans/
    :param network_id: Network ID
    :return: Error Code (if relevant), Response (or Error Message)
    """
    try:
        response = dashboard.appliance.getNetworkApplianceVlans(network_id)
        return None, response
    except meraki.APIError as e:
        return e.status, str(e)
    except Exception as e:
        # SDK Error
        return "500", str(e)


def create_vlan(network_id: str, vlan_config: dict) -> tuple[str | None, dict | str]:
    """
    Create VLANS on Meraki Appliance Network (or update existing VLAN), return response or (error code, error message)
    https://developer.cisco.com/meraki/api-v1/create-network-appliance-vlan/
    :param network_id: Network ID
    :param vlan_config: VLAN Creation Payload
    :return: Error Code (if relevant), Response (or Error Message)
    """
    try:
        # Enable VLANs (if not enabled - avoids error - safe assumption if you have vlans in the settings)
        response = dashboard.appliance.updateNetworkApplianceVlansSettings(network_id, vlansEnabled=True)

        # Create VLANs
        response = dashboard.appliance.createNetworkApplianceVlan(network_id, **vlan_config)
        return None, response

    except meraki.APIError as e:
        # Special processing if vlan exists (or we are modifying vlans on a template bound network), update!
        if 'taken' in e.message['errors'][0] or 'bound' in e.message['errors'][0]:
            # Safe assumptions config is correct and minimum fields present (otherwise different error)
            vlan_id = vlan_config['id']
            del vlan_config['id']

            return update_vlan(network_id, vlan_id, vlan_config)

        return e.status, str(e)
    except Exception as e:
        # SDK Error
        return "500", str(e)


def update_vlan(network_id: str, vlan_id: str, vlan_config: dict) -> tuple[
    str | None, dict | str]:
    """
    Update VLAN on Meraki Appliance Network, return response or (error code, error message)
    https://developer.cisco.com/meraki/api-v1/update-network-appliance-vlan/
    :param network_id: Network ID
    :param vlan_id: VLAN Number
    :param vlan_config: VLAN Update Payload
    :return: Error Code (if relevant), Response (or Error Message)
    """
    try:
        response = dashboard.appliance.updateNetworkApplianceVlan(networkId=network_id, vlanId=vlan_id, **vlan_config)
        return None, response
    except meraki.APIError as e:
        return e.status, str(e)
    except Exception as e:
        # SDK Error
        return "500", str(e)


def get_network_devices(network_id: str) -> tuple[str | None, list | str]:
    """
    Get Network Devices, return response or (error code, error message)
    https://developer.cisco.com/meraki/api/get-network-devices/
    :param network_id: Network ID
    :return: Error Code (if relevant), Response (or Error Message)
    """
    try:
        response = dashboard.networks.getNetworkDevices(network_id)
        return None, response
    except meraki.APIError as e:
        return e.status, str(e)
    except Exception as e:
        # SDK Error
        return "500", str(e)


def update_device(serial: str, device_config: dict) -> tuple[
    str | None, dict | str]:
    """
    Update Device attributes, return response or (error code, error message)
    https://developer.cisco.com/meraki/api-v1/update-device/
    :param serial: Device serial
    :param device_config: Device Update Payload
    :return: Error Code (if relevant), Response (or Error Message)
    """
    try:
        response = dashboard.devices.updateDevice(serial, **device_config)
        return None, response
    except meraki.APIError as e:
        return e.status, str(e)
    except Exception as e:
        # SDK Error
        return "500", str(e)


def update_site_to_site_vpn(network_id: str, site2site_configs: dict) -> tuple[
    str | None, dict | str]:
    """
    Update Site to Site VPN on Meraki Appliance Network, return response or (error code, error message)
    https://developer.cisco.com/meraki/api-v1/update-network-appliance-vpn-site-to-site-vpn/
    :param network_id: Network ID
    :param site2site_configs: Site to Site VPN Update Payload
    :return: Error Code (if relevant), Response (or Error Message)
    """
    try:
        response = dashboard.appliance.updateNetworkApplianceVpnSiteToSiteVpn(
            network_id, **site2site_configs)
        return None, response
    except meraki.APIError as e:
        return e.status, str(e)
    except Exception as e:
        # SDK Error
        return "500", str(e)


def get_site_to_site_vpn(network_id: str) -> tuple[str | None, dict | str]:
    """
    Get Site to Site VPN Network configs, return response or (error code, error message)
    https://developer.cisco.com/meraki/api-v1/get-network-appliance-vpn-site-to-site-vpn/
    :param network_id: Network ID
    :return: Error Code (if relevant), Response (or Error Message)
    """
    try:
        response = dashboard.appliance.getNetworkApplianceVpnSiteToSiteVpn(network_id)
        return None, response
    except meraki.APIError as e:
        return e.status, str(e)
    except Exception as e:
        # SDK Error
        return "500", str(e)


def update_sys_log_servers(network_id: str, syslog_config: dict) -> tuple[str | None, dict | str]:
    """
    Update Syslog Network configs, return response or (error code, error message)
    https://developer.cisco.com/meraki/api-v1/update-network-syslog-servers/
    :param network_id: Network ID
    :param syslog_config: Syslog Update Payload
    :return: Error Code (if relevant), Response (or Error Message)
    """
    try:
        response = dashboard.networks.updateNetworkSyslogServers(network_id, **syslog_config)
        return None, response
    except meraki.APIError as e:
        return e.status, str(e)
    except Exception as e:
        # SDK Error
        return "500", str(e)


def update_snmp(network_id: str, snmp_config: dict) -> tuple[str | None, dict | str]:
    """
    Update SNMP Network configs, return response or (error code, error message)
    https://developer.cisco.com/meraki/api-v1/update-network-snmp/
    :param network_id: Network ID
    :param snmp_config: SNMP Update Payload
    :return: Error Code (if relevant), Response (or Error Message)
    """
    try:
        response = dashboard.networks.updateNetworkSnmp(network_id, **snmp_config)
        return None, response
    except meraki.APIError as e:
        return e.status, str(e)
    except Exception as e:
        # SDK Error
        return "500", str(e)


def update_malware_settings(network_id: str, amp_config: dict) -> tuple[str | None, dict | str]:
    """
    Update AMP Network configs, return response or (error code, error message)
    https://developer.cisco.com/meraki/api-v1/update-network-appliance-security-malware/
    :param network_id: Network ID
    :param amp_config: AMP Update Payload
    :return: Error Code (if relevant), Response (or Error Message)
    """
    try:
        response = dashboard.appliance.updateNetworkApplianceSecurityMalware(network_id, **amp_config)
        return None, response
    except meraki.APIError as e:
        return e.status, str(e)
    except Exception as e:
        # SDK Error
        return "500", str(e)


def update_content_filtering_settings(network_id: str, content_filtering_config: dict) -> tuple[
    str | None, dict | str]:
    """
    Update Content Filtering Network configs, return response or (error code, error message)
    https://developer.cisco.com/meraki/api-v1/update-network-appliance-content-filtering/
    :param network_id: Network ID
    :param content_filtering_config: Content Filtering Update Payload
    :return: Error Code (if relevant), Response (or Error Message)
    """
    try:
        response = dashboard.appliance.updateNetworkApplianceContentFiltering(network_id, **content_filtering_config)
        return None, response
    except meraki.APIError as e:
        return e.status, str(e)
    except Exception as e:
        # SDK Error
        return "500", str(e)


def get_uplink_bandwidth(network_id: str) -> tuple[str | None, list | str]:
    """
    Get Uplink Bandwidth Settings, return response or (error code, error message)
    https://developer.cisco.com/meraki/api/get-network-appliance-traffic-shaping-uplink-bandwidth/
    :param network_id: Network ID
    :return: Error Code (if relevant), Response (or Error Message)
    """
    try:
        response = dashboard.appliance.getNetworkApplianceTrafficShapingUplinkBandwidth(network_id)
        return None, response
    except meraki.APIError as e:
        return e.status, str(e)
    except Exception as e:
        # SDK Error
        return "500", str(e)


def update_traffic_shaping_uplink_bandwidth_settings(network_id: str, traffic_shaping_uplink_bandwidth_config: dict) -> \
        tuple[str | None, dict | str]:
    """
    Update Traffic Shaping Uplink Bandwidth Network configs, return response or (error code, error message)
    https://developer.cisco.com/meraki/api-v1/update-network-appliance-traffic-shaping-uplink-bandwidth/
    :param network_id: Network ID
    :param traffic_shaping_uplink_bandwidth_config: Traffic Shaping Uplink Bandwidth Update Payload
    :return: Error Code (if relevant), Response (or Error Message)
    """
    try:
        response = dashboard.appliance.updateNetworkApplianceTrafficShapingUplinkBandwidth(network_id,
                                                                                           **traffic_shaping_uplink_bandwidth_config)
        return None, response
    except meraki.APIError as e:
        return e.status, str(e)
    except Exception as e:
        # SDK Error
        return "500", str(e)


def claim_devices(network_id: str, serials: list[str]) -> tuple[str | None, dict | str]:
    """
    Claim devices into Network, return response or (error code, error message)
    https://developer.cisco.com/meraki/api-v1/claim-network-devices/
    :param network_id: Network ID
    :param serials: list of Device Serials to claim into Network
    :return: Error Code (if relevant), Response (or Error Message)
    """
    try:
        response = dashboard.networks.claimNetworkDevices(network_id, serials)
        return None, response
    except meraki.APIError as e:
        return e.status, str(e)
    except Exception as e:
        # SDK Error
        return "500", str(e)


def get_network_firmware_upgrades(network_id: str) -> tuple[str | None, dict | str]:
    """
    Get firmware upgrade information for network, return response or (error code, error message)
    https://developer.cisco.com/meraki/api-v1/get-network-firmware-upgrades/
    :param network_id: Network ID
    :return: Error Code (if relevant), Response (or Error Message)
    """
    try:
        response = dashboard.networks.getNetworkFirmwareUpgrades(network_id)
        return None, response
    except meraki.APIError as e:
        return e.status, str(e)
    except Exception as e:
        # SDK Error
        return "500", str(e)


def trigger_network_firmware_upgrades(network_id: str, firmware_upgrade_config: dict) -> tuple[
    str | None, str | dict | str]:
    """
    Upgrade firmware of devices in network, return response or (error code, error message)
    https://developer.cisco.com/meraki/api-v1/update-network-firmware-upgrades/
    :param network_id: Network ID
    :param firmware_upgrade_config: Firmware Upgrade Payload
    :return: Error Code (if relevant), Response (or Error Message)
    """
    try:
        response = dashboard.networks.updateNetworkFirmwareUpgrades(network_id, **firmware_upgrade_config)
        return None, response
    except meraki.APIError as e:
        # Special processing if already on this current version
        if 'already on this version' in e.message['errors'][0]:
            return None, "Firmware is up to date with specified version already. Skipping."
        return e.status, str(e)
    except Exception as e:
        # SDK Error
        return "500", str(e)


def get_network_appliance_ports(network_id: str) -> tuple[
    str | None, dict | str]:
    """
    Get Network Appliance Port configs, return response or (error code, error message)
    https://developer.cisco.com/meraki/api-v1/get-network-appliance-ports/
    :param network_id: Network ID
    :return: Error Code (if relevant), Response (or Error Message)
    """
    try:
        response = dashboard.appliance.getNetworkAppliancePorts(network_id)
        return None, response
    except meraki.APIError as e:
        return e.status, str(e)
    except Exception as e:
        # SDK Error
        return "500", str(e)


def update_network_appliance_port(network_id: str, appliance_port_config: dict) -> tuple[
    str | None, dict | str]:
    """
    Update Network Appliance Port configs, return response or (error code, error message)
    https://developer.cisco.com/meraki/api-v1/update-network-appliance-port/
    :param network_id: Network ID
    :param appliance_port_config: Appliance Port Update Payload
    :return: Error Code (if relevant), Response (or Error Message)
    """
    try:
        response = dashboard.appliance.updateNetworkAppliancePort(network_id, **appliance_port_config)
        return None, response
    except meraki.APIError as e:
        return e.status, str(e)
    except Exception as e:
        # SDK Error
        return "500", str(e)


def update_warm_spare(network_id: str, warm_spare_config: dict) -> tuple[
    str | None, dict | str]:
    """
    Update Network Appliance Port configs, return response or (error code, error message)
    https://developer.cisco.com/meraki/api-v1/update-network-appliance-warm-spare/
    :param network_id: Network ID
    :param warm_spare_config: Warm Spare Update Payload
    :return: Error Code (if relevant), Response (or Error Message)
    """
    try:
        response = dashboard.appliance.updateNetworkApplianceWarmSpare(network_id, **warm_spare_config)
        return None, response
    except meraki.APIError as e:
        return e.status, str(e)
    except Exception as e:
        # SDK Error
        return "500", str(e)


def update_mx_uplinks(serial: str, uplink_config: dict) -> tuple[
    str | None, dict | str]:
    """
    Update MX Appliance Uplink configs, return response or (error code, error message)
    https://developer.cisco.com/meraki/api-v1/update-device-appliance-uplinks-settings/
    :param serial: MX Serial
    :param uplink_config: MX Uplinks Update Payload
    :return: Error Code (if relevant), Response (or Error Message)
    """
    try:
        response = dashboard.appliance.updateDeviceApplianceUplinksSettings(serial, **uplink_config)
        return None, response
    except meraki.APIError as e:
        return e.status, str(e)
    except Exception as e:
        # SDK Error
        return "500", str(e)
