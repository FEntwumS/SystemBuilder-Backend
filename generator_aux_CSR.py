#!/usr/bin/env python3

#
# This file is not part of LiteX.
# Copyright (?) 2025 Sven Krause <sven.krause@fh-dortmund.de> 
#
# SPDX-License-Identifier: BSD-2-Clause

import pdb  #TODO:      REMOVE when no longer necessary!
import shutil
import yaml
import sys
import os

from litex.soc.interconnect.csr import * 

#TODO: Add check to prevent issue due to duplicated port names?
#That should not happen, but it would be nice opportunity to alert users to design errors...
class GenericCSR (Module, AutoCSR):
    """
    I would like to support more dynamic interfaces anyway and a good generic interface generation
    combined with some additional tool/component, might be a nice way to do it. I don't have to
    use litex for everything after all.
    Having implemented this, I could potentially develop a workflow based on Verilog wrappers. These
    could potentially be automatically generated.
    """
    def __init__(self, ports, parameters):
        for k in ports:
            #"in" and "out" refers to the ports at the Verilog Module
            #so "in" means data is written from CPU to Module
            reg_name = ports[k]['name']
            connector = "con_"+ reg_name
            direction = ports[k]['direction']
            reg_width = ports[k]['size']
            #if reg_name in ["clk", "clock"]:
                #TODO: Add special handling of clock ports?
            if direction == "in":
                setattr(self, reg_name, CSRStorage(reg_width, name=reg_name))
                setattr(self, connector, Signal(reg_width, name=connector))
                self.comb += getattr(self, connector).eq(getattr(self, reg_name).storage)
            elif direction == "out":
                setattr(self, reg_name, CSRStatus(reg_width, name=reg_name))
                setattr(self, connector, Signal(reg_width, name=connector))
                self.sync += getattr(self, reg_name).status.eq(getattr(self, connector)) 
            else:
                print("Missing directions for external ports!")

class GenericVlogModuleCSR (Module, AutoCSR):
    def __init__(self, parameters, ports, platform, module_name, instance_name, vlog_src):
        modports = dict()
        if parameters is not None:
            modparams = parameters.items() #make list of key value pairs
            for k in modparams: #read parameters and prepare argument for instance class
                param_name ="p_"+k[0]
                modports[param_name] = k[1]
        for k in ports:
            reg_name = ports[k]['name']
            direction = ports[k]['direction']
            reg_width = ports[k]['size']

            csr_name = "csr_of_"+ reg_name
            #check direction of every port, create appropriate CSR and prefixed name for instance class
            if direction == "in":
                if reg_name == "clk" or reg_name == "clock": #this is quite rudimentary, but good enough for now
                    setattr(self, reg_name, ClockSignal())
                    inst_port_name = "i_"+reg_name
                    modports[inst_port_name] = getattr(self, reg_name)
                elif reg_name == "rst" or reg_name == "reset":
                    setattr(self, reg_name, ResetSignal())
                    inst_port_name = "i_"+reg_name
                    modports[inst_port_name] = getattr(self, reg_name)
                else:
                    setattr(self, reg_name, CSRStorage(reg_width, name=csr_name)) 
                    inst_port_name = "i_"+reg_name
                    modports[inst_port_name] = getattr(self, reg_name).storage
            elif direction == "out":
                setattr(self, reg_name, CSRStatus(reg_width, name=csr_name))
                inst_port_name = "o_"+reg_name
                modports[inst_port_name] = getattr(self, reg_name).status
            else:
                print("ERROR IN THE CSR INTERFACE GENERATION!")

        # Instantiate the Verilog module        
        self.specials += Instance(module_name,
            name = instance_name,
            **modports
        )

"""
Old method.
#"Parser" mehtod for port sizes.
#TODO: Update this method to be able to handle more complex expressions!
     
def parse_port_size (ports, parameters):
    if parameters is not None:
        modparams = parameters.items() #make list of key value pairs
    for k in ports:
        port_width = ports[k]['size']
        if not isinstance(port_width, str):
            raise TypeError('Port size must be string! Should look like: "size" : "1" in config file.')
        #Simple handling for size 1 ports
        if port_width == "1":
            port_width = int(port_width); 
            ports[k]['size'] = port_width
        else:
        #For larger ports, split string at ':' and remove brackets
            if port_width.startswith('[') and port_width.endswith(']'):
                #remove brackets and split
                port_width = port_width.lstrip('[')   
                port_width = port_width.rstrip(']')
                parts = port_width.rsplit(':')
                #remove leading and trailing spaces
                parts[0] = parts[0].strip()
                parts[1] = parts[1].strip()
                #Check if left side is number only. If so, convert to int.
                if parts[0].isdigit():      
                    parts[0] = int(parts[0])
                    #handle tedious case of parameterized size (usually PARAM-1, but not always)
                    #For now, - and + shall be supported, anything beyond that is witchcraft anyway ;-)
                else:
                    for i in parts[0]:
                        if i == '-':
                            subparts = parts[0].rsplit('-')
                            subparts[0]=subparts[0].strip() #remove spaces
                            subparts[1]=subparts[1].strip()
                            for i in modparams:
                                if subparts[0] == i[0]:
                                    subparts[0] = i[1]
                                    parts[0] = int(subparts[0]) - int(subparts[1])
                                    break
                        if i == '+':
                            subparts = parts[0].rsplit('+')
                            subparts[0]=subparts[0].strip() #remove spaces
                            subparts[1]=subparts[1].strip()
                            for i in modparams:
                                if subparts[0] == i[0]:
                                    subparts[0] = i[1]
                                    parts[0] = int(subparts[0]) + int(subparts[1])
                                    break                                
                #Now we get to the other side of the separator
                #This assumes that there is always just a number after the ':'.
                #TODO: Add support for parameters here? Does anyone need that? 
                parts[1] = int(parts[1])
                port_width = parts[0] + 1 - parts[1];
                #write port size as integer into collection
                ports[k]['size'] = port_width
            else:
                raise ValueError("Port size should be formatted '[x:y]' or '1'")
    return ports
"""