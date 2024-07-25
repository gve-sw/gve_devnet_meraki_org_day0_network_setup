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

import json
import logging
import os
import time
from logging.handlers import TimedRotatingFileHandler

import meraki_functions

# Absolute Paths
script_dir = os.path.dirname(os.path.abspath(__file__))
configs_path = os.path.join(script_dir, 'configs')
logs_path = os.path.join(script_dir, 'logs')


def set_up_logging() -> logging.Logger:
    """
    Return Main Logger Object (TimeRotatingFileHandler for Log Files)
    :return: Logger Object
    """
    # Set up logging
    logger = logging.getLogger('my_logger')
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter('%(message)s')

    # log to files (last 7 days, rotated at midnight local time each day)
    log_file = os.path.join(logs_path, 'day0_script_output.log')
    file_handler = TimedRotatingFileHandler(log_file, when="midnight", interval=1, backupCount=7)
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)

    logger.addHandler(file_handler)

    return logger


def separate_custom_fields(config: dict) -> tuple[dict, dict]:
    """
    Separate any "custom" fields ("_*") from primary dictionary for processing (and to pass remaining dict as is to Meraki SDK)
    :param config: Provided Meraki config for that setting
    :return: Custom Fields Dict ("_*") fields, Remaining Fields Dict (everything else)
    """
    # Iterate through config, remove any "custom" fields that start with "_" (method only for dictionaries)
    custom_fields = {}
    remaining_fields = {}

    for key, value in config.items():
        if key.startswith("_"):
            custom_fields[key] = value
        else:
            remaining_fields[key] = value

    return custom_fields, remaining_fields


def load_ref_config(filename: str) -> dict | None:
    """
    Load JSON config from file pointed to by "_ref". Allows referencing other json files to minimize size of master file.
    :param filename: "_ref" file name
    :return: Python dict representing referenced config
    """
    ref_json = os.path.join(configs_path, filename)

    # Attempt to read ref file (check if it exists)
    if os.path.exists(ref_json):
        # File exists, read it in
        with open(ref_json, "r") as fp:
            ref_config = json.load(fp)
        return ref_config
    else:
        return None


def apply_config_template(log_buffer: str, net_id: str, net_id_to_config_template: dict, template_name_to_id: dict,
                          config: dict) -> tuple[str, dict | str, str]:
    """
    Apply a Configuration Template to a Meraki Network
    :param log_buffer: String representing processing logs written to log file
    :param net_id: Network ID
    :param net_id_to_config_template: Mapping of Network ID to Configuration Template Names
    :param template_name_to_id: Mapping of Configuration Template Names to IDs
    :param config: Raw Configuration Template Config
    :return: Tuple of Status (Success | Failure), Result, Updated Log Buffer
    """
    log_buffer += "Apply Configuration Template:\n"

    # Check for Ref. Config, load if found
    if "_ref" in config:
        config = load_ref_config(config["_ref"])

        if not config:
            result = "Ref File not found... skipping."
            log_buffer += f"(Failure): {result}\n"
            return "Failure", result, log_buffer

    # First remove any custom fields
    custom_fields, remaining_fields = separate_custom_fields(config)

    # Check if network is already bound to template, but bound to the wrong template
    if net_id in net_id_to_config_template:
        if net_id_to_config_template[net_id] != custom_fields['_name_template']:
            # Unbind from current template
            unbind_payload = custom_fields.get("_unbind", {})
            error_code, response = meraki_functions.unbind_network(net_id, unbind_payload)

            if error_code:
                log_buffer += f"-Unbind (Failure): \n\t{response}\n"
                return "Failure", response, log_buffer
            else:
                log_buffer += f"-Unbind (Success): \n\t{response}\n"
        else:
            # Correct template already bound, return
            result = f"Template `{custom_fields['_name_template']}` Already Applied."
            log_buffer += f"-Bind (Success): \n\t{result}\n"
            return "Success", result, log_buffer

    # Check if new template name field is blank (indicates unbind only)
    if custom_fields['_name_template'] == "":
        return "Success", "Unbind Only", log_buffer

    # Check if template exists
    if custom_fields['_name_template'] not in template_name_to_id:
        result = "Template Not Found... skipping."
        log_buffer += f"-Bind (Failure): \n\t{result}\n"
        return "Failure", result, log_buffer

    # Apply Configuration Template
    remaining_fields['configTemplateId'] = template_name_to_id[custom_fields['_name_template']]
    error_code, response = meraki_functions.bind_network(net_id, remaining_fields)

    if error_code:
        log_buffer += f"-Bind (Failure): \n\t{response}\n"
        return "Failure", response, log_buffer

    log_buffer += f"-Bind (Success): \n\t{response}\n"
    return "Success", response, log_buffer


def claim_devices(log_buffer: str, net_id: str, config: dict) -> tuple[str, dict | str, str]:
    """
    Claim 1 or More Devices into Network. Devices must be unclaimed and in the inventory!
    :param log_buffer: String representing processing logs written to log file
    :param net_id: Network ID
    :param config: Raw Device Claim Config
    :return: Tuple of Status (Success | Failure), Result, Updated Log Buffer
    """
    log_buffer += "Claim Device(s) "

    # Check for Ref. Config, load if found
    if "_ref" in config:
        config = load_ref_config(config["_ref"])

        if not config:
            result = "Ref File not found... skipping."
            log_buffer += f"(Failure): \n\t{result}\n"
            return "Failure", result, log_buffer

    serials = config.get("serials", [])

    # Claim devices!
    error_code, response = meraki_functions.claim_devices(net_id, serials)

    if error_code:
        log_buffer += f"(Failure): \n\t{response}\n"
        return "Failure", response, log_buffer

    log_buffer += f"(Success): \n\t{response}\n"

    # Wait for 2 minute after claiming device, all other device updates will fail without it
    time.sleep(120)

    return "Success", response, log_buffer


def firmware_upgrade(log_buffer: str, net_id: str, config: dict) -> tuple[str, dict | list | str, str]:
    """
    Schedule Firmware upgrade for various types of devices
    :param log_buffer: String representing processing logs written to log file
    :param net_id: Network ID
    :param config: Raw Firmware Upgrade Config
    :return: Tuple of Status (Success | Failure), Result, Updated Log Buffer
    """
    log_buffer += "Firmware Upgrade "

    # Check for Ref. Config, load if found
    if "_ref" in config:
        config = load_ref_config(config["_ref"])

        if not config:
            result = "Ref File not found... skipping."
            log_buffer += f"(Failure): \n\t{result}\n"
            return "Failure", result, log_buffer

    # Get Available Firmware Upgrades
    error_code, response = meraki_functions.get_network_firmware_upgrades(net_id)

    if error_code:
        log_buffer += f"(Failure): \n\t{response}\n"
        return "Failure", response, log_buffer

    # Build small mapping dict mapping firmware name to unique id
    firmware_name_to_id = {}
    for product in response['products']:
        # Process Current Version (to prevent failure if provided upgrade version is already the current version!)
        current_version = response['products'][product]['currentVersion']
        firmware_name_to_id[current_version['shortName']] = current_version['id']

        # Process any available versions
        available_versions = response['products'][product]['availableVersions']
        for version in available_versions:
            firmware_name_to_id[version['shortName']] = version['id']

    # Convert Firmware upgrade ShortNames to proper version id (payload structure must be exact!)
    firmware_shortnames = []
    if 'products' in config:
        products = config['products']

        for product in products:
            product_upgrade = products[product]
            if 'nextUpgrade' in product_upgrade and "toVersion" in product_upgrade['nextUpgrade']:
                # Perform conversion!
                if "_name_id" in product_upgrade['nextUpgrade']['toVersion']:
                    shortname = product_upgrade['nextUpgrade']['toVersion']['_name_id']

                    if shortname in firmware_name_to_id:
                        firmware_shortnames.append(product_upgrade['nextUpgrade']['toVersion']['_name_id'])

                        del product_upgrade['nextUpgrade']['toVersion']['_name_id']
                        product_upgrade['nextUpgrade']['toVersion']['id'] = firmware_name_to_id[shortname]
                    else:
                        # Unable to find Firmware Version (but payload is correct)
                        result = f"Unable to find version `{shortname}` in available versions: {firmware_name_to_id}"
                        log_buffer += f"(Failure): \n\t{result}\n"
                        return "Failure", result, log_buffer

    # Schedule Firmware Upgrades
    error_code, response = meraki_functions.trigger_network_firmware_upgrades(net_id, config)

    if error_code:
        log_buffer += f"(Failure): \n\t{response}\n"
        return "Failure", response, log_buffer

    log_buffer += f"(Success): \n\t{response}\n"

    # Note: if we have succeeded to this point, either a firmware upgrade has been triggered successfully or we are
    # on the current version
    return "Success", firmware_shortnames, log_buffer


def site_to_site_vpn_config(log_buffer: str, net_id: str, net_name_to_id: dict, config: dict) -> tuple[
    str, dict | str, str]:
    """
    Apply Site to Site Configs to Meraki Network
    :param log_buffer: String representing processing logs written to log file
    :param net_id: Network ID
    :param net_name_to_id: Network Name to ID mapping (for spoke configurations)
    :param config: Raw Site to Site Config from JSON
    :return: Tuple of Status (Success | Failure), Result, Updated Log Buffer
    """
    log_buffer += "Site to Site VPN Config "

    # Check for Ref. Config, load if found
    if "_ref" in config:
        config = load_ref_config(config["_ref"])

        if not config:
            result = "Ref File not found... skipping."
            log_buffer += f"(Failure): \n\t{result}\n"
            return "Failure", result, log_buffer

    mode = config.get("mode", "hub")
    hubs = config.get("hubs", None)

    if mode == "spoke":
        if hubs:
            valid_hubs = []
            # Replace hub network names with ids
            for hub in hubs:
                hubId = hub.get("hubId", None)
                if hubId and hubId in net_name_to_id:
                    hub["hubId"] = net_name_to_id[hubId]
                    valid_hubs.append(hub)
        else:
            config["mode"] = "hub"

    # Update Site to Site Settings
    error_code, response = meraki_functions.update_site_to_site_vpn(net_id, config)

    if error_code:
        log_buffer += f"(Failure): \n\t{response}\n"
        return "Failure", response, log_buffer

    log_buffer += f"(Success): \n\t{response}\n"
    return "Success", response, log_buffer


def syslog_server_config(log_buffer: str, net_id: str, config: dict) -> tuple[str, dict | str, str]:
    """
    Apply Syslog Configs to Meraki Network
    :param log_buffer: String representing processing logs written to log file
    :param net_id: Network ID
    :param config: Raw Syslog Config from JSON
    :return: Tuple of Status (Success | Failure), Result, Updated Log Buffer
    """
    log_buffer += "Syslog Config "

    # Check for Ref. Config, load if found
    if "_ref" in config:
        config = load_ref_config(config["_ref"])

        if not config:
            result = "Ref File not found... skipping."
            log_buffer += f"(Failure): \n\t{result}\n"
            return "Failure", result, log_buffer

    # Update SysLog Configs
    error_code, response = meraki_functions.update_sys_log_servers(net_id, config)

    if error_code:
        log_buffer += f"(Failure): \n\t{response}\n"
        return "Failure", response, log_buffer

    log_buffer += f"(Success): \n\t{response}\n"
    return "Success", response, log_buffer


def warm_spare_config(log_buffer: str, net_id: str, config: dict) -> tuple[str, dict | str, str]:
    """
    Apply Warm Spare Configs to Meraki Network
    :param log_buffer: String representing processing logs written to log file
    :param net_id: Network ID
    :param config: Raw Warm Spare Config from JSON
    :return: Tuple of Status (Success | Failure), Result, Updated Log Buffer
    """
    log_buffer += "Warm Spare Config "

    # Check for Ref. Config, load if found
    if "_ref" in config:
        config = load_ref_config(config["_ref"])

        if not config:
            result = "Ref File not found... skipping."
            log_buffer += f"(Failure): \n\t{result}\n"
            return "Failure", result, log_buffer

    # Update SysLog Configs
    error_code, response = meraki_functions.update_warm_spare(net_id, config)

    if error_code:
        log_buffer += f"(Failure): \n\t{response}\n"
        return "Failure", response, log_buffer

    log_buffer += f"(Success): \n\t{response}\n"
    return "Success", response, log_buffer


def snmp_config(log_buffer: str, net_id: str, config: dict) -> tuple[str, dict | str, str]:
    """
    Apply SNMP Configs to Meraki Network
    :param log_buffer: String representing processing logs written to log file
    :param net_id: Network ID
    :param config: Raw SNMP Config from JSON
    :return: Tuple of Status (Success | Failure), Result, Updated Log Buffer
    """
    log_buffer += "SNMP Config "

    # Check for Ref. Config, load if found
    if "_ref" in config:
        syslog_config = load_ref_config(config["_ref"])

        if not syslog_config:
            result = "Ref File not found... skipping."
            log_buffer += f"(Failure): \n\t{result}\n"
            return "Failure", result, log_buffer

    # Update SNMP Configs
    error_code, response = meraki_functions.update_snmp(net_id, config)

    if error_code:
        log_buffer += f"(Failure): \n\t{response}\n"
        return "Failure", response, log_buffer

    log_buffer += f"(Success): \n\t{response}\n"
    return "Success", response, log_buffer


def amp_config(log_buffer: str, net_id: str, config: dict) -> tuple[str, dict | str, str]:
    """
    Apply AMP Configs to Meraki Network
    :param log_buffer: String representing processing logs written to log file
    :param net_id: Network ID
    :param config: Raw AMP Config from JSON
    :return: Tuple of Status (Success | Failure), Result, Updated Log Buffer
    """
    log_buffer += "AMP Config "

    # Check for Ref. Config, load if found
    if "_ref" in config:
        config = load_ref_config(config["_ref"])

        if not config:
            result = "Ref File not found... skipping."
            log_buffer += f"(Failure): \n\t{result}\n"
            return "Failure", result, log_buffer

    # Update AMP Configs
    error_code, response = meraki_functions.update_malware_settings(net_id, config)

    if error_code:
        log_buffer += f"(Failure): \n\t{response}\n"
        return "Failure", response, log_buffer

    log_buffer += f"(Success): \n\t{response}\n"
    return "Success", response, log_buffer


def content_filtering_config(log_buffer: str, net_id: str, config: dict) -> tuple[str, dict | str, str]:
    """
    Apply Content Filtering Configs to Meraki Network
    :param log_buffer: String representing processing logs written to log file
    :param net_id: Network ID
    :param config: Raw Content Filtering Config from JSON
    :return: Tuple of Status (Success | Failure), Result, Updated Log Buffer
    """
    log_buffer += "Content Filtering Config "

    # Check for Ref. Config, load if found
    if "_ref" in config:
        config = load_ref_config(config["_ref"])

        if not config:
            result = "Ref File not found... skipping."
            log_buffer += f"(Failure): \n\t{result}\n"
            return "Failure", result, log_buffer

    # First remove any custom fields
    custom_fields, remaining_fields = separate_custom_fields(config)

    # Get Content Categories for Name Translation
    if "_name_blockedUrlCategories" in custom_fields:
        error_code, response = meraki_functions.get_content_filtering_categories(net_id)

        if error_code:
            log_buffer += f"(Failure): Network Categories - {response}\n"
            return "Failure", response, log_buffer

        categories_map = {category['name']: category['id'] for category in response['categories']}

        # Convert Named Categories to IDs
        remaining_fields['blockedUrlCategories'] = [categories_map[name] for name in
                                                    custom_fields["_name_blockedUrlCategories"] if
                                                    name in categories_map]

    # Update Content Filtering Configs
    error_code, response = meraki_functions.update_content_filtering_settings(net_id, remaining_fields)

    if error_code:
        log_buffer += f"(Failure): \n\t{response}\n"
        return "Failure", response, log_buffer

    log_buffer += f"(Success): \n\t{response}\n"
    return "Success", response, log_buffer


def vlans_config(log_buffer: str, net_id: str, config: dict) -> tuple[str, list | str, str]:
    """
    Apply VLAN Configs to Meraki Network (including enabling VPN and DHCP settings)
    :param log_buffer: String representing processing logs written to log file
    :param net_id: Network ID
    :param config: Raw VLAN Config from JSON
    :return: Tuple of Status (Success | Failure), Result, Updated Log Buffer
    """
    log_buffer += "VLAN Config(s):\n"
    vpn_subnets = []
    status = "Success"

    # Grab Any Copied Group Policies (can be specified when creating vlans)
    error_code, net_policies = meraki_functions.get_network_group_policies(net_id)
    if error_code:
        log_buffer += f"Group Policies (Failure): {net_policies}\n"
        status = "Failure"
        return status, f"Group Policies (Failure): {net_policies}\n", log_buffer

    net_policy_groups = {policy['name']: policy['groupPolicyId'] for policy in net_policies}

    # Iterate through each VLAN, create the VLAN (perform ancillary VLAN tasks as well - DHCP config, VPN config, etc.)
    for vlan_config in config:
        # Check for Ref. Config, load if found
        if "_ref" in vlan_config:
            vlan_config = load_ref_config(vlan_config["_ref"])

            if not vlan_config:
                log_buffer += "--VLAN Creation (Failure): Ref File not found... skipping.\n"
                status = "Partial"
                continue

        # First remove any custom fields
        custom_fields, remaining_fields = separate_custom_fields(vlan_config)

        # Convert Group Policy Name to ID
        if "_name_groupPolicyId" in custom_fields and custom_fields["_name_groupPolicyId"] in net_policy_groups:
            remaining_fields['groupPolicyId'] = net_policy_groups[custom_fields["_name_groupPolicyId"]]

        # Create base vlan
        error_code, new_vlan = meraki_functions.create_vlan(net_id, remaining_fields)

        if error_code:
            if 'id' in remaining_fields:
                log_buffer += f"-VLAN Creation/Update (Failure): \n\t{new_vlan}\n"
            else:
                log_buffer += f"-VLAN Creation/Update (Failure): \n\t{new_vlan}\n"

            status = "Partial"
            continue

        log_buffer += f"-VLAN {new_vlan['id']} Creation/Update (Success): \n\t{new_vlan}\n"

        # Get VPN setting for VLAN if specified (default is false)
        if "_vpn" in custom_fields:
            vpn_config = custom_fields['_vpn']

            # Check for Ref. Config, load if found
            if "_ref" in vpn_config:
                vpn_config = load_ref_config(vpn_config["_ref"])

                if not vpn_config:
                    log_buffer += f"--VLAN {new_vlan['id']} VPN (Failure): Ref File not found... skipping.\n"
                    status = "Partial"
                    continue

            useVpn = vpn_config.get("useVpn", False)
            vpn_subnets.append({"localSubnet": new_vlan["subnet"], "useVpn": useVpn})

        # Process DHCP configs for VLAN if specified
        if "_dhcp" in custom_fields:
            dhcp_config = custom_fields['_dhcp']

            # Check for Ref. Config, load if found
            if "_ref" in dhcp_config:
                dhcp_config = load_ref_config(dhcp_config["_ref"])

                if not dhcp_config:
                    log_buffer += f"--VLAN {new_vlan['id']} DHCP (Failure): Ref File not found... skipping.\n"
                    status = "Partial"
                    continue

            # Update VLAN (sets DHCP options)
            error_code, response = meraki_functions.update_vlan(net_id, new_vlan['id'], dhcp_config)

            if error_code:
                log_buffer += f"--VLAN {new_vlan['id']} DHCP (Failure): \n\t{response}\n"
                status = "Partial"
                continue
            else:
                log_buffer += f"--VLAN {new_vlan['id']} DHCP (Success): \n\t{response}\n"

    if len(vpn_subnets) > 0:
        # Configure Site to Site VPN (if currently not enabled, error out - note readme, some settings must be
        # configured first!)
        error_code, response = meraki_functions.get_site_to_site_vpn(net_id)

        if error_code or response['mode'] == 'none':
            log_buffer += "-VLAN VPN (Failure): Unable to Retrieve Site2Site Config or Site2Site VPN not enabled... skipping.\n"
            status = "Partial"
        else:
            # Enable/Disable new VPNs!
            response['subnets'] += vpn_subnets
            error_code, response = meraki_functions.update_site_to_site_vpn(net_id, response)

            if error_code:
                log_buffer += f"-VLAN VPN (Failure): \n\t{response}\n"
                status = "Partial"
            else:
                log_buffer += f"-VLAN VPN (Success): \n\t{response}\n"

    # Get All Configured VLANS, return result
    error_code, response = meraki_functions.get_vlans(net_id)
    return status, response, log_buffer


def vlan_per_port_config(log_buffer: str, net_id: str, config: dict) -> tuple[str, list | str, str]:
    """
    Apply VLAN Per Port Configs to Meraki Network
    :param log_buffer: String representing processing logs written to log file
    :param net_id: Network ID
    :param config: Raw VLAN Per Port Config from JSON
    :return: Tuple of Status (Success | Failure), Result, Updated Log Buffer
    """
    log_buffer += "VLAN Per Port Config(s):\n"
    status = "Success"

    # Iterate through each MX Port, modify VLAN Per port settings
    for per_port_config in config:
        # Check for Ref. Config, load if found
        if "_ref" in per_port_config:
            per_port_config = load_ref_config(per_port_config["_ref"])

            if not per_port_config:
                log_buffer += "-VLAN Per Port Update (Failure): Ref File not found... skipping.\n"
                status = "Partial"
                continue

        # Update Per Port VLAN Config
        error_code, new_per_port = meraki_functions.update_network_appliance_port(net_id, per_port_config)

        if error_code:
            log_buffer += f"-VLAN Per Port Update (Failure): \n\t{new_per_port}\n"
            status = "Partial"
            continue

        log_buffer += f"-VLAN Per Port Update (Success): \n\t{new_per_port}\n"

    # Get All Per Port VLAN Settings, return result
    error_code, response = meraki_functions.get_network_appliance_ports(net_id)
    return status, response, log_buffer


def devices_config(log_buffer: str, net_id: str, config: dict) -> tuple[str, list | str, str]:
    """
    Apply Devices Configs to Meraki Devices
    :param log_buffer: String representing processing logs written to log file
    :param net_id: Network ID
    :param config: Raw Device Config from JSON
    :return: Tuple of Status (Success | Failure), Result, Updated Log Buffer
    """
    log_buffer += "Device Config(s):\n"
    status = "Success"

    # Iterate through each Device, update the device
    for device_config in config:
        # Check for Ref. Config, load if found
        if "_ref" in device_config:
            device_config = load_ref_config(device_config["_ref"])

            if not device_config:
                log_buffer += "-Device Configuration (Failure): Ref File not found... skipping.\n"
                status = "Partial"
                continue

        # Update device!
        if 'serial' not in device_config:
            log_buffer += f"-Device Configuration (Failure): \n\tNo Device Serial provided... skipping.\n"
            status = "Partial"
            continue

        serial = device_config['serial']
        del device_config['serial']

        log_buffer += f"-Device ({serial}):\n"

        # First remove any custom fields
        custom_fields, remaining_fields = separate_custom_fields(device_config)

        # Main Device Update
        error_code, device = meraki_functions.update_device(serial, remaining_fields)

        if error_code:
            log_buffer += f"--Update (Failure): \n\t{device}\n"
            status = "Partial"
            continue

        log_buffer += f"--Update (Success): \n\t{device}\n"

        # Process MX Uplink configs if specified
        if "_mx_uplinks" in custom_fields:
            mx_uplink_config = custom_fields['_mx_uplinks']

            # Check for Ref. Config, load if found
            if "_ref" in mx_uplink_config:
                mx_uplink_config = load_ref_config(mx_uplink_config["_ref"])

                if not mx_uplink_config:
                    log_buffer += f"--Uplink Configuration (Failure): Ref File not found... skipping.\n"
                    status = "Partial"
                    continue

            # Update MX Uplink Configs
            error_code, response = meraki_functions.update_mx_uplinks(serial, mx_uplink_config)

            if error_code:
                log_buffer += f"--Uplink Configuration (Failure): \n\t{response}\n"
                status = "Partial"
                continue
            else:
                log_buffer += f"--Uplink Configuration (Success): \n\t{response}\n"

    # Get Current Devices in Network
    error_code, response = meraki_functions.get_network_devices(net_id)
    return status, response, log_buffer


def traffic_shaping_config(log_buffer: str, net_id: str, config: dict) -> tuple[str, dict | str, str]:
    """
    Apply Traffic Shaping Configs to Meraki Network (including uplink bandwidth)
    :param log_buffer: String representing processing logs written to log file
    :param net_id: Network ID
    :param config: Raw Traffic Shaping Config from JSON
    :return: Tuple of Status (Success | Failure), Result, Updated Log Buffer
    """
    log_buffer += "Traffic Shaping Config(s):\n"
    status = "Success"
    traffic_config = {"uplink_bandwidth": None}

    # Check for Ref. Config, load if found
    if "_ref" in config:
        config = load_ref_config(config["_ref"])

        if not config:
            result = "Ref File not found... skipping."
            log_buffer += f"(Failure): {result}\n"
            status = "Failure"
            return status, result, log_buffer

    # First remove any custom fields
    custom_fields, remaining_fields = separate_custom_fields(config)

    # Process uplink bandwidth if specified
    if "_uplink_bandwidth" in custom_fields:
        bandwidth_config = custom_fields['_uplink_bandwidth']

        # Check for Ref. Config, load if found
        if "_ref" in bandwidth_config:
            bandwidth_config = load_ref_config(bandwidth_config["_ref"])

            if not bandwidth_config:
                log_buffer += "-Uplink Bandwidth (Failure): Ref File not found... skipping.\n"
                status = "Partial"

        # Update Traffic Shaping
        error_code, response = meraki_functions.update_traffic_shaping_uplink_bandwidth_settings(net_id,
                                                                                                 bandwidth_config)

        if error_code:
            log_buffer += f"-Uplink Bandwidth (Failure): \n\t{response}\n"
            status = "Partial"
        else:
            log_buffer += f"-Uplink Bandwidth (Success): \n\t{response}\n"

    # Get Uplink Bandwidths
    error_code, response = meraki_functions.get_uplink_bandwidth(net_id)
    traffic_config['uplink_bandwidth'] = response

    return status, traffic_config, log_buffer
