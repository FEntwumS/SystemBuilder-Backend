#!/usr/bin/env python3

#
# This file is based on a file that is part of LiteX.
#
# Copyright (c) 2022 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (?) 2025 Sven Krause <sven.krause@fh-dortmund.de> 
#
# SPDX-License-Identifier: BSD-2-Clause

import pdb  #TODO:      REMOVE when no longer necessary!
import shutil
import yaml
import sys
import os

#from migen import *

from litex.build.generic_platform import *
from litex.soc.integration.soc_core import *
from litex.soc.integration.soc import SoCRegion
from litex.soc.integration.builder import *
from litex.soc.interconnect import wishbone
from litex.soc.interconnect import axi

from generator_aux_CSR import *
from generator_aux_CRG import *         

# IOs/Interfaces -----------------------------------------------------------------------------------

def make_io(inst_name, ports):
    _ios = []
    for j in ports:
        """
        This is an older version where the naming depends on direction
        if ports[j]['direction'] == "in":   #input of ext. module is output of SoC
            name = "foo_"+ports[j]['name']
        elif ports[j]['direction'] == "out":
            name = "bar_"+ports[j]['name']
        else:
            print("Missing directions for external ports!")
            return _ios
        """
        name = inst_name + "_" + ports[j]['name']
        size = ports[j]['size']
        element = (name, 0, Pins(size))
        _ios.append(element)
    return _ios    

def get_common_ios():
    return [
        # Clk/Rst.
        ("clk", 0, Pins(1)),
        ("rst", 0, Pins(1)),
    ]

def get_uart_ios():
    return [
        # Serial
        ("uart", 0,
            Subsignal("tx",  Pins(1)),
            Subsignal("rx", Pins(1)),
        )
    ]
    
#more dummy IO ressources for testing use of the ecosystem cores
def get_i2c_io():
    return [
        ("i2cmaster", 0,
            Subsignal("scl", Pins(1)),
            Subsignal("sda", Pins(1)),
        )
    ]
def get_spi_master_io():
    return [
        ("spimaster", 0,
            Subsignal("clk", Pins(1)),
            Subsignal("cs_n", Pins(1)),
            Subsignal("mosi", Pins(1)),
            Subsignal("miso", Pins(1)),
        )
    ] 

def get_SDcard_io():
    return [
        ("sdcard", 0,
            Subsignal("data", Pins(4)),
            Subsignal("cmd", Pins(1)),
            Subsignal("clk", Pins(1)),
            Subsignal("cd", Pins(1)),
        )
    ]

def get_spiSDcard_io():
    return [
        ("spisdcard", 0,
            Subsignal("clk",  Pins(f"{pmod}:3")),
            Subsignal("mosi", Pins(f"{pmod}:1"), Misc("PULLUP=true")),
            Subsignal("cs_n", Pins(f"{pmod}:0"), Misc("PULLUP=true")),
            Subsignal("miso", Pins(f"{pmod}:2"), Misc("PULLUP=true")),
        )
    ]

def get_debug_ios(debug_width=8):
    return [
        ("debug", 0, Pins(debug_width)),
    ]

# Platform -----------------------------------------------------------------------------------------

class Platform(GenericPlatform):
    def build(self, fragment, build_dir, build_name, **kwargs):
        os.makedirs(build_dir, exist_ok=True)
        os.chdir(build_dir)
        conv_output = self.get_verilog(fragment, name=build_name)
        conv_output.write(f"{build_name}.v")
        
# LiteX SoC Generator ------------------------------------------------------------------------------
#added some arguments to the SoCGenerator Class
class LiteXSoCGenerator(SoCMini):
    def __init__(self, **kwargs):
        #provide default value for name and clock frequency if not available
        name = "litex_soc" if kwargs['name'] is None else kwargs['name']   
        sys_clk_freq = int(50e6) if kwargs['sys_clk_freq'] is None else int(kwargs['sys_clk_freq'])
        base_io=get_common_ios()     #start with minimal io for all platforms
        
        # Platform and CRG ---------------------------------------------------------------------------------     
        #Use generic platform unless specified. For now, platform only required for CRG.
        #TODO: REMOVE THESE LINES UP TO THE COMMENT WHEN REACTIVATING AUTO_PLL STUFF!
        platform = Platform(device="", io=base_io)
        platform.name = name
        #Use dummy CRG for generic platform. User must take care of clocking.
        self.submodules.crg = CRG( 
            clk = platform.request("clk"), 
            rst = platform.request("rst"),
        )
        """
        if kwargs['auto_pll'] is False:
            platform = Platform(device="", io=base_io)
            platform.name = name
            #Use dummy CRG for generic platform. User must take care of clocking.
            self.submodules.crg = CRG( 
                clk = platform.request("clk"), 
                rst = platform.request("rst"),
            )
        else:
            ref_clk_freq = int(kwargs['ref_clk_freq'])
            if kwargs['device'] is None:
                raise ValueError(
                    "No device selected. This shouldn't happen. Did someone edit the config by hand?")
            else:
                device = kwargs['device']
                #TODO: Maybe add more specific device options; may be relevant e.g. for iCE40 devices
                match (device):
                    case "Altera":
                        print("THIS IS JUST A DUMMY FOR NOW!")
                    case "Gatemate":
                        from litex.build.colognechip.platform import CologneChipPlatform
                        platform = CologneChipPlatform(device="CCGM1A1", io=base_io, toolchain="peppercorn")
                        self.crg = _CRG_CCGM(platform, sys_clk_freq, ref_clk_freq)
                    case "LatticeECP5":
                        from litex.build.lattice import LatticeECP5Platform
                        platform = LatticeECP5Platform(device="DUMMY", io=base_io, toolchain="diamond")
                        #note: I put the "diamond" toolchain so that litex shuts up
                        #TODO: Check if that means missing some key generated files...
                        self.crg = _CRG_LatticeECP5(platform, sys_clk_freq, ref_clk_freq)
                    case "iCE40":
                        from litex.build.lattice import LatticeiCE40Platform
                        platform = LatticeiCE40Platform(device="DUMMY", io=base_io, toolchain="icestorm")
                        self.crg = _CRGLatticeiCE40(platform, sys_clk_freq, ref_clk_freq)
                    case "XilinxS7":
                        from litex.build.xilinx import Xilinx7SeriesPlatform
                        platform = Xilinx7SeriesPlatform(device="DUMMY", io=base_io, toolchain="vivado")
                        self.crg = _CRG_Xilinx7Series(platform, sys_clk_freq, ref_clk_freq)
                    case "XilinxS6":
                        from litex.build.xilinx import XilinxSpartan6Platform
                        platform = XilinxSpartan6Platform(device="DUMMY", io=base_io, toolchain="vivado")
                        self.crg = _CRG_XilinxSpartan6(platform, sys_clk_freq, ref_clk_freq)
                    case "XilinxUS":
                        from litex.build.xilinx import XilinxUSPlatform
                        platform = XilinxUSPlatform(device="DUMMY", io=base_io, toolchain="vivado")
                        self.crg = _CRG_XilinxUltrascale(platform, sys_clk_freq, ref_clk_freq)
                    case "XilinxUSP":
                        from litex.build.xilinx import XilinxUSPPlatform
                        platform = XilinxUSPPlatform(device="DUMMY", io=base_io, toolchain="vivado")
                        self.crg = _CRG_XilinxUltrascalePlus(platform, sys_clk_freq, ref_clk_freq)
                    case _:
                        print("It ... it can't be. This shouldn't be possible! How did we get here without specifying a device?")
                        raise ValueError("{} is not a recognized device type.".format(device))
        """             
        # SoC --------------------------------------------------------------------------------------
        platform.add_extension(get_uart_ios())
        
        if kwargs["uart_name"] == "serial":
            kwargs["uart_name"] = "uart"
        #TODO: Check for useful UART options
           
        SoCCore.__init__(self, platform, clk_freq=sys_clk_freq, ident=f"LiteX standalone SoC - {name}", **kwargs)
# Start of my additions to the generator___________________________________________________________________________________________________________
        """
        Here comes the part that handles optional additions to the base-SoC,
        such as I2C-Master (bitbanged/soft or in hardware), spi_master,  
        
        Currently the implementation is minimalistic. It may make sense to make
        the whole thing more dynamic, however that will require more complex 
        inputs as well.
        For now, this serves mostly to experiment with this and give the base-SoC 
        more functionality of its own.
        As the designs are usually flattened into a single verilog file, it may
        be best to limit the base-SoC functionality and keep complex parts,
        which may require later editing in Verilog, separate.
        """        
        if kwargs['soft_i2c']:
            platform.add_extension(get_i2c_io())
            from litex.soc.cores.bitbang import I2CMaster
            self.add_module(name="i2c", module=I2CMaster(platform.request("i2cmaster")))
        
        if kwargs['hard_i2c']:
            platform.add_extension(get_i2c_io())
            self.add_i2c_master()
        #TODO: improve litei2c support 
            """
            option for interrupt, needs additional field in GUI
            if kwargs['i2c_interrupt']:
                platform.add_extension(get_i2c_io())
                self.add_i2c_master(with_irq=True) #sends interrupt when rx_ready
            else:
                platform.add_extension(get_i2c_io())
                self.add_i2c_master()
            """
        if kwargs['hard_spi']:    
            platform.add_extension(get_spi_master_io())
            self.add_spi_master()
        
        if kwargs['soft_spi']:
            platform.add_extension(get_spi_master_io())
            from litex.soc.cores.bitbang import SPIMaster
            self.spi = SPIMaster(platform.request("spimaster"))

        if kwargs['SDcard']:
            platform.add_extension(get_SDcard_io())
            self.add_sdcard()

        """
        I'm preparing some addittional functionality here that shall be kept inactive until the
        relevant fields are added to the GUI.  

        if kwargs['spi_sdcard']:
            platform.add_extension(get_spiSDcard_io())
            self.add_spi_sdcard()
        """ 
        
        if kwargs['external_modules']:  #check for entries in external_modules
            for i in kwargs['external_modules']:
                vlog_src = kwargs['external_modules'][i]['source']
                mod_name = kwargs['external_modules'][i]['module_name']     #see above
                inst_name = kwargs['external_modules'][i]['instance_name']  #using this for now
                ports = kwargs['external_modules'][i]['ports']
                params = kwargs['external_modules'][i]['parameters']
                
                #check if vlog_src is given (currently used to distignuish internal and external)
                if vlog_src == "None":
                    CSRwrap = GenericCSR(ports, params)
                    platform.add_extension(make_io(inst_name, ports))
                    self.add_module(name=inst_name, module=CSRwrap)
                    for k in ports:
                        connector = "con_" + ports[k]['name'];
                        io_portname = inst_name + "_" + ports[k]['name'] #name of the generated external io
                        if ports[k]['direction'] == "in":  #input of external module means output of SoC
                            self.comb += platform.request(io_portname).eq(
                                getattr(getattr(self, inst_name), connector))
                        elif ports[k]['direction'] == "out":
                            self.comb += getattr(getattr(self, inst_name), connector).eq(
                                platform.request(io_portname))
                        #TODO: Check if support for "inout" is worthwhile
                        #elif ports[k]['direction'] == "inout": 
                        else:
                            print("Missing directions for external ports!")
                
                else:   #NOTE: for now I assume that configs will always be valid
                    CSRwrap = GenericVlogModuleCSR(params, ports, platform, mod_name, inst_name, vlog_src)
                    self.add_module(name=inst_name, module=CSRwrap)                    
                """
                On the CSR interface: The way this is designed now, there are two distinct ways of connecting
                an external (Verilog) Module to the system:
                1. GenericCSR: This creates top-level ports connecting them to CSRs according to the data
                               direction. This is primarily designed for such cases where only some of a 
                               modules ports need to be connected to a CSR.
                #TODO: Rework method to be more flexible?
                2. GenericVlogModule: This creates an instance of the external Module within the BaseSoC.
                                      This is intended for modules that are entirely contained within the
                                      BaseSoC with no direct connection to the outside world.
                #TODO: Investigate suitability for LiteX-Cores or possible alternatives
                       The idea is to add any additional periphery as submodules in the Verilog. So far I
                       have the impression that Migen/FHDL doesn't do that for Migen/FHDL modules.
                       Perhaps this can be circumvented by generating the Verilog before adding the thing
                       here but I'm unsure if that is a good idea...
                """
                
#End of my additions to SoC generator_________________________________________________________________________        
        # MMAP Slave Interface ---------------------------------------------------------------------
        """
            These bus interfaces are not really considere in the current version of the SystemBuilder.
            This section of code can be deactivate/removed without issue at the moment.
        """
        #TODO: Implement "expose_bus" option
        
        bus_width = kwargs['bus_data_width']
        bus_addr_width = kwargs['bus_address_width']
        s_bus = {
            "wishbone" : wishbone.Interface(data_width=bus_width, adr_width=bus_addr_width),
            "axi-lite" : axi.AXILiteInterface(data_width=bus_width, address_width=bus_addr_width),
            "axi" : axi.AXIInterface(data_width=bus_width, address_width=bus_addr_width), #TODO: Test if this works properly! 
        }[kwargs["bus_standard"]]
        self.bus.add_master(name="mmap_bus_s", master=s_bus)
        platform.add_extension(s_bus.get_ios("mmap_bus_s"))
        wb_pads = platform.request("mmap_bus_s")
        self.comb += s_bus.connect_to_pads(wb_pads, mode="slave")
        
        # MMAP Master Interface --------------------------------------------------------------------
        # FIXME: Allow Region configuration.
        
        m_bus = {
            "wishbone" : wishbone.Interface(data_width=bus_width, adr_width=bus_addr_width),
            "axi-lite" : axi.AXILiteInterface(data_width=bus_width, address_width=bus_addr_width),
            "axi" : axi.AXIInterface(data_width=bus_width, address_width=bus_addr_width), #TODO: Test if this works properly!
        }[kwargs["bus_standard"]]
        wb_region = SoCRegion(origin=0xa000_0000, size=0x1000_0000, cached=False) # FIXME.
        self.bus.add_slave(name="mmap_bus_m", slave=m_bus, region=wb_region)
        platform.add_extension(m_bus.get_ios("mmap_bus_m"))
        wb_pads = platform.request("mmap_bus_m")
        self.comb += m_bus.connect_to_pads(wb_pads, mode="master")
        
        # Debug ------------------------------------------------------------------------------------
        platform.add_extension(get_debug_ios())
        debug_pads = platform.request("debug")
        self.comb += [
            # Export Signal(s) for debug.
            debug_pads[0].eq(0), # 0.
            debug_pads[1].eq(1), # 1.
            # Etc...
        ]

# Build --------------------------------------------------------------------------------------------
def main():
    #TODO: Implement option for arbitrary file name? 'configFile_output.yaml'
    args = read_config_file('configFile_demo_soc.yaml')
    # SoC.
    soc = LiteXSoCGenerator(
        **args
    )
    
    # Build
    builder = Builder(soc, **builder_arg_filter(**args))
    #TODO: Check if this is the best setting here...
    #builder.build(build_name=args['name'], run=args['build'])
    builder.build(build_name=args['name'], run=False)
    
    #Copy source of e.g. CPU hardware to output directory
    for filepath, language, library, *copy in builder.soc.platform.sources:
        source = filepath
        destination = builder.gateware_dir
        #make sure to only copy files that aren't already at destination
        if os.path.isdir(destination):
            destination = os.path.join(destination, os.path.basename(source))
        if not shutil._samefile(source, destination):
            make = shutil.copy(source, destination)
      
    """TODO: Think of how to handle the generated gateware build-scripts
       Litex will auto-generate build scripts if I give the platfrom and toolchain for
       the automated CRG functionality. These likely will not work properly, as I have
       done nothing to ensure they do, while using Litex in an unconventional way.
       
       The simplest way to deal with this is to just delete them, but that is inelegant
       and inefficient. Maybe they could be kept as part of some sort of "advanced mode"
       that can be activated in the GUI.
    """
    #For now: Clear build scripts from gateware_dir to avoid confusion 
    for file in os.listdir(builder.gateware_dir):
        if not (file.endswith(".v") or file.endswith(".init")):
            path = os.path.join(builder.gateware_dir, file)
            os.remove(path)
            
#Auxiliary Methods ------------------------------------------------------------------------------
def read_config_file(filename):     
    soc_config = yaml.load(open(filename).read(), Loader=yaml.Loader)
    
    # Convert YAML elements to Python/LiteX --------------------------------------------------------
    for k, v in soc_config.items():
        replaces = {"False": False, "True": True, "None": None}
        for r in replaces.keys():
            if v == r:
                soc_config[k] = replaces[r]
        if "clk_freq" in k:
            soc_config[k] = float(soc_config[k])
#This is taken from gen.py in liteDRAM and adapted-------------------------------------------------------

    return soc_config

def builder_arg_filter(**kwargs):
    #Set of arguments must be reduced to relevant options for builder
    valid_keys = [
        #Directories
        "output_dir", "gateware_dir", "software_dir", "include_dir",
        "generated_dir",
        #Compilation
        "compile_software", "compile_gateware", "build_backend",
        #Exports
        "csr_json", "csr_csv", "csr_svd", "memory_x",
        #BIOS
        "bios_lto", "bios_format", "bios_console",
        #Documentation
        "generate_doc"
    ]
    valid_args = {}
    for arg_key in kwargs.keys():
        for v_key in valid_keys:
            if v_key == arg_key:
                valid_args.update({v_key: kwargs[v_key]})
    #TODO: Add option for compile software?
    valid_args.update({"compile_software" : True})
    valid_args.update({"compile_gateware" : False})
    
    return valid_args 

if __name__ == "__main__":
    main()
