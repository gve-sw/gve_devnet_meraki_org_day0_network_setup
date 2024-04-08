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

from abc import ABC, abstractmethod


class ExcelDriverInterface(ABC):
    """
    Abstract Interface, defines structure for any custom Excel Drivers
    """

    def __init__(self, input_file):
        """
        Initialize Driver Class
        """
        self.productTypes = []
        self.input_file = input_file

    @abstractmethod
    def parse_excel_to_json(self) -> dict:
        """
        Parses an Excel file and returns a JSON-like Python dictionary. The parser must create a JSON-like Python
        Dictionary which conforms to all the established JSON structure rules in the top level README.

        Excel parsers can only support functionality mapped to the underlying JSON functionality in the core code (
        ex: defined fields). These parsers are intended to pass the JSON-like Dictionary output directly to the JSON
        processing code.

        :return: A Python dictionary representing the Excel file's contents.
        """
        pass

    def output_results(self, results: list):
        """
        Optional method, used to define writing out the results of building the networks in a custom manner
        (ex: Excel, CSv, etc.). It is up to a driver if they wish to define this method and exactly what the output of
        this method should be.

        :param results: Output Results from primary code (list of 'completions', each containing processed
        configurations and the result of processing each configuration)
        """
        pass
