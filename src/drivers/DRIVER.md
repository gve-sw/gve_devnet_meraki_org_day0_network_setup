# Excel Drivers

`Excel Drivers` are custom Python Classes functioning as Excel Parsers whose ultimate goal is to produce a valid JSON equivalent translation to feed into the primary code.

These classes afford great flexibility when reading in any number of structured Excel files and specific configurations. All developer defined drivers **MUST** be located in the `src/drivers` package.

## Class Structure
All drivers inherit from the `driver_interface.py` interface, which defines a single mandatory method: `parse_excel_to_json`

This method is where the parsing and processing of an Excel file takes place. The output **MUST** be a python dictionary representing the valid translated JSON configuration. Valid configurations follow all the rules defined in the top level README.

The contents of this method are highly variable and depend on the structure of the Excel file. The implementation is left up to the developer.

`output_results` can also be defined if you'd like to output the results of applying the configurations in a custom manner (ex: to a file, Excel sheet, etc.)
This method is optional.

## Driver Example - MinifiedMXMG

The `MinifiedMXMGDriver` is included as an example. This driver corresponds to the Excel file `configs/input_excel_example.xlsx` and focuses on constructing MX/MG Meraki networks with special attention to VLANs and DHCP.
This driver assumes we have 1 MX and 1 MG per network, and it will claim the respective devices based on the provided serial numbers.

The driver expects the field names seen in the Excel file and expects the exact structure provided. Other assumptions/considerations for its parser include:
* Assuming the Configurations are on the **First** Sheet
* Processing Configuration top down (enforcing the same dependencies as the underlying `JSON File Structure`)
* Networks are seperated by a **blank line**
* The user inputted configurations (green) follow the same rules and ideas as their `JSON File Structure` equivalent (ex: values without _ are passed in as API values, so they must conform to the API spec)
* Unnecessary values can be left blank (ex: DHCP configuration if not responding to DHCP requests)
* To add or remove VLANs, simply add or remove a VLAN row

If using the driver, it's recommend to copy and paste the provided example, then fill in the necessary values (and consult the API documentation for value restrictions).

**Note:** Anything defined after "Networks" row is processed by the script. Other "global variables" can be defined and cells can be referenced to reuse values.
