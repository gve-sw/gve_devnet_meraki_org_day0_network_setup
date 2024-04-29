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

import datetime
import importlib
import json
import os
import pkgutil
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress
from rich.prompt import Prompt
from rich.table import Table

import config
import meraki_functions
import utils
from drivers.driver_interface import ExcelDriverInterface

# Absolute Paths
script_dir = os.path.dirname(os.path.abspath(__file__))
configs_path = os.path.join(script_dir, 'configs')
drivers_path = os.path.join(script_dir, 'drivers')
logs_path = os.path.join(script_dir, 'logs')

# Set up file and console logging
logger = utils.set_up_logging()

# Rich console instance
console = Console()

# Get global network name to ID mapping table
net_name_to_id = meraki_functions.network_name_to_id()


def discover_and_load_drivers() -> dict:
    """
    Dynamically import driver classes, create mapping of class name to Class Instantiation instance
    :return: Drivers dictionary, mapping class name to Class Instantiation instance
    """
    drivers = {}
    for loader, module_name, is_pkg in pkgutil.iter_modules([str(drivers_path)]):
        if not is_pkg:
            # Dynamically import the module
            module = importlib.import_module(f'drivers.{module_name}')
            for attribute_name in dir(module):
                attribute = getattr(module, attribute_name)
                # Check if the attribute is a class and is a subclass of ExcelDriverInterface (excluding the
                # interface itself)
                if isinstance(attribute, type) and issubclass(attribute,
                                                              ExcelDriverInterface) and attribute is not ExcelDriverInterface:
                    drivers[attribute.__name__] = attribute
    return drivers


def load_day0_config(filename: str) -> dict | None:
    """
    Load Master Day 0 Config (top level config - can contain one or more refs to other JSON files)
    :param filename: Day 0 Config filename
    :return: Python Dict representing toplevel config
    """
    network_json = os.path.join(configs_path, filename)

    # Read in JSON file (check if it exists first)
    if os.path.exists(network_json):
        console.print(f"[green]File `{filename}` found![/]")
        # File exists, read it in
        with open(network_json, "r") as fp:
            day0_config = json.load(fp)
        return day0_config
    else:
        console.print(f"[red]Error: The file '{network_json}' does not exist. Please check the name.[/]")
        return None


def copy_from_net_exists(net_name: str) -> str | None:
    """
    Check if provided "Copy From Network Name" is valid and return ID
    :param net_name: "Copy From Network" name
    :return: "Copy From Network" ID
    """
    # Sanity check if Copy From Network Exists
    if net_name in net_name_to_id:
        copy_from_id = net_name_to_id[net_name]
        console.print(f"Found ID for COPY_FROM network: [blue]{copy_from_id}[/]")
        return copy_from_id
    else:
        console.print(
            f"[red]Error, {net_name} ID not found in Org... Please check the Copy From Network Name.[/]")
        return None


def build_new_network(progress: Progress, copy_from_id: str, network_config: dict) -> dict:
    """
    Main processing method for each network, construct network using provided day 0 configs. Add new settings handling here!
    :param progress: Progress bar for display
    :param copy_from_id: "Copy From Network" ID (if provided)
    :param network_config: Dict representing network config
    :return: Completion Table (with SUCCESS/FAILURE for each setting) - processing details in the logs
    """
    # Create Log buffer, capture results of network processing to be written to log file
    log_buffer = ""
    completion_status = {"_name": "N/A", "settings": {"creation": {"status": "Failure", "output": None}}}

    # Create network (metadata field must be present, error if unable to create, continue if network already exists)
    metadata = network_config.get("metadata", None)
    required_fields = ["name", "productTypes"]

    if not metadata or not all(field in metadata for field in required_fields):
        # Minimum metadata fields not present, unable to create network
        log_buffer += "Metadata not present, unable to create network..."
        logger.info(log_buffer)

        return completion_status

    log_buffer += f"Network: {metadata['name']}\n"
    log_buffer += "--------------------------------\n"

    if copy_from_id:
        metadata['copyFromNetworkId'] = copy_from_id

    error_code, response = meraki_functions.create_network(metadata, net_name_to_id)

    if error_code:
        # Network Creation failed, stop processing other settings
        log_buffer += f"Network Creation (Failure): \n\t{response}"
        logger.info(log_buffer)

        completion_status["_name"] = metadata['name']
        completion_status['settings']['creation']['output'] = response

        return completion_status

    log_buffer += f"Network Creation/Update (Success): \n\t{response}\n"
    completion_status['settings']['creation']['status'] = "Success"
    completion_status['settings']['creation']['output'] = response

    # Newly Created Net ID
    net_id = response['id']

    # Iterate through remaining keys, pass off work to respective methods
    del network_config['metadata']
    remaining_settings = list(network_config.keys())

    # Track completion status of each setting for table display
    completion_status["_name"] = response['name']
    for setting in remaining_settings:
        completion_status["settings"][setting] = {"status": "Skipped", "output": None}

    # Add Intermediate Progress Bar
    task = progress.add_task(f"Processing [green]{metadata['name']}[/]....", total=len(remaining_settings),
                             transient=True)

    for setting in remaining_settings:
        if setting == "claim":
            # Claim Devices into Network
            status, output, log_buffer = utils.claim_devices(log_buffer, net_id, network_config[setting])
            completion_status["settings"][setting]['status'] = status
            completion_status["settings"][setting]['output'] = output
        elif setting == "firmware":
            # Schedule Firmware upgrades
            status, output, log_buffer = utils.firmware_upgrade(log_buffer, net_id, network_config[setting])
            completion_status["settings"][setting]['status'] = status
            completion_status["settings"][setting]['output'] = output
        elif setting == "siteToSiteVPN":
            # Configure "global" site to site settings - mode and possible hubs
            status, output, log_buffer = utils.site_to_site_vpn_config(log_buffer, net_id, net_name_to_id,
                                                                       network_config[setting])
            completion_status["settings"][setting]['status'] = status
            completion_status["settings"][setting]['output'] = output
        elif setting == "amp":
            # Network AMP Settings
            status, output, log_buffer = utils.amp_config(log_buffer, net_id, network_config[setting])
            completion_status["settings"][setting]['status'] = status
            completion_status["settings"][setting]['output'] = output
        elif setting == "content_filtering":
            # Network Content Filtering Settings
            status, output, log_buffer = utils.content_filtering_config(log_buffer, net_id, network_config[setting])
            completion_status["settings"][setting]['status'] = status
            completion_status["settings"][setting]['output'] = output
        elif setting == "syslog":
            # Network SysLog Servers Settings
            status, output, log_buffer = utils.syslog_server_config(log_buffer, net_id, network_config[setting])
            completion_status["settings"][setting]['status'] = status
            completion_status["settings"][setting]['output'] = output
        elif setting == "snmp":
            # Network SNMP Settings
            status, output, log_buffer = utils.snmp_config(log_buffer, net_id, network_config[setting])
            completion_status["settings"][setting]['status'] = status
            completion_status["settings"][setting]['output'] = output
        elif setting == "vlans":
            # Process VLAN List (triggers processing for DHCP and VPN config as well)
            status, output, log_buffer = utils.vlans_config(log_buffer, net_id, network_config[setting])
            completion_status["settings"][setting]['status'] = status
            completion_status["settings"][setting]['output'] = output
        elif setting == "vlan_per_port":
            # Process VLAN Per Port List
            status, output, log_buffer = utils.vlan_per_port_config(log_buffer, net_id, network_config[setting])
            completion_status["settings"][setting]['status'] = status
            completion_status["settings"][setting]['output'] = output
        elif setting == "devices":
            # Process Device List (modifies attributes about device, NOT claiming - devices should be claimed)
            status, output, log_buffer = utils.devices_config(log_buffer, net_id, network_config[setting])
            completion_status["settings"][setting]['status'] = status
            completion_status["settings"][setting]['output'] = output
        elif setting == "traffic_shaping":
            # Process VLAN List (triggers processing for DHCP and VPN config as well)
            status, output, log_buffer = utils.traffic_shaping_config(log_buffer, net_id, network_config[setting])
            completion_status["settings"][setting]['status'] = status
            completion_status["settings"][setting]['output'] = output
        else:
            log_buffer += f"Unknown options: {setting}. Not supported at this time.\n"

        progress.update(task, advance=1)

    # Write everything to log file
    logger.info(log_buffer)

    # Remove intermediate task
    progress.remove_task(task)

    return completion_status


def main():
    """
    Main method, process all networks on day 0 config, apply various configured settings
    """
    console.print(Panel.fit("Meraki Day 0 Network Configuration"))
    input_filename = config.NETWORKS_FILE_NAME
    driver_instance = None

    if input_filename.endswith('.json'):
        # JSON Input
        console.print(Panel.fit(f"Read in JSON Day 0 Config", title="Step 1"))

        # Load Master level JSON config
        day0_config = load_day0_config(input_filename)
        if not day0_config:
            # File not found
            sys.exit(-1)

        # Extract Copy From Network name if provided
        copy_from_net_name = day0_config.get("_name_copyFromNetworkId", "N/A")

    elif input_filename.endswith('.xlsx'):
        # Excel Input
        console.print(Panel.fit(f"Read in Excel Day 0 Config", title="Step 1"))

        # Check if Excel File Exists
        file_path = os.path.join(configs_path, input_filename)
        if os.path.exists(file_path):
            console.print(f"[green]File `{input_filename}`found![/]")
        else:
            console.print(f"[red]Error: The file '{input_filename}' does not exist. Please check the name.[/]")
            sys.exit(-1)

        # Discover and Load Defined Excel Drivers
        available_drivers = discover_and_load_drivers()

        # Select Driver
        console.print("Available Excel Drivers:")
        for idx, driver_name in enumerate(available_drivers.keys(), start=1):
            console.print(f"{idx}. {driver_name}")
        selected_driver_index = Prompt.ask("Select an Excel Driver",
                                           choices=[str(i) for i in range(1, len(available_drivers) + 1)])
        selected_driver_name = list(available_drivers.keys())[int(selected_driver_index) - 1]

        # Instantiate the selected driver
        selected_driver_class = available_drivers[selected_driver_name]
        driver_instance = selected_driver_class(file_path, console)

        # Parse Excel file into compatible day0_config JSON structure, remainder of the code stays the same!
        day0_config = driver_instance.parse_excel_to_json()

        # Write driver output to json file in logs (for reference)
        json_conversion_file = 'excel_driver_output.json'
        driver_output = os.path.join(logs_path, json_conversion_file)
        with open(driver_output, "w") as fp:
            json.dump(day0_config, fp)

        console.print(
            f"[green]Excel file successfully parsed![/] Refer to JSON conversion file: [yellow]logs/{json_conversion_file}[/]")

        # Get Copy From Network Source Name
        copy_from_net_name = Prompt.ask("\n(Optional) Enter Copy-From Network Name", default="N/A")
    else:
        console.log(f"[red]Error: Unsupported File Type '{config.NETWORKS_FILE_NAME}'.[/]")
        sys.exit(-1)

    console.print("\n")
    console.print(Panel.fit(f"Create Networks", title="Step 2"))

    # Sanity check if Copy From Network Exists
    copy_from_id = None
    if copy_from_net_name != "N/A":
        copy_from_id = copy_from_net_exists(copy_from_net_name)

        if not copy_from_id:
            # Copy From Network not found
            sys.exit(-1)

    logger.info(f"-----------------------------New Run: {datetime.datetime.now()}-----------------------------")

    # Create a Rich Table showing processing results
    completions = []
    unique_settings = set()
    table = Table(title="Creation Summary")
    table.add_column("Network Name", style="cyan", justify="left")

    # Iterate through networks and create them (apply various configs based on fields)!
    networks = day0_config.get('networks', [])
    with Progress() as progress:
        overall_progress = progress.add_task("Overall Progress", total=len(networks))
        counter = 1

        # Using ThreadPoolExecutor to process networks concurrently
        max_workers = 5
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []

            for network in networks:
                # Submit networks for parallel processing
                future = executor.submit(build_new_network, progress, copy_from_id, network)
                futures.append(future)

            # Wait for all tasks to complete
            for future in as_completed(futures):
                completion_result = future.result()

                if completion_result["_name"] != "N/A":
                    progress.console.print(
                        f"Processed: [green]{completion_result['_name']}[/] ({counter} of {len(networks)})")

                # Append result to list, use it to build summary table
                completions.append(completion_result)

                # Append unique settings
                unique_settings.update(completion_result['settings'].keys())

                counter += 1
                progress.update(overall_progress, advance=1)

    console.print("\n")
    console.print(Panel.fit(f"Output Results", title="Step 3"))

    # Build Unique Columns only for summary table
    unique_settings_sorted = sorted(unique_settings)
    for setting in unique_settings_sorted:
        table.add_column(setting, style="magenta", justify="left")

    # Add rows to the table
    for completion in completions:
        row_values = [completion["_name"]]
        for column in table.columns[1:]:
            key = column.header
            if key in completion["settings"]:
                value = completion["settings"][key]['status']
                if value == "Success":
                    value_style = "green"
                elif value == "Partial":
                    value_style = "yellow"
                else:
                    value_style = "red"
                row_values.append(f"[{value_style}]{value}[/{value_style}]")
            else:
                row_values.append("")
        table.add_row(*row_values)

    console.print(table)

    # if driver instance is not none, then we used an Excel Driver, call custom output method (if defined - default =
    # pass)
    if driver_instance:
        driver_instance.output_results(completions)


if __name__ == '__main__':
    main()
