#!/usr/bin/env python3

# This file is not really part of LiteX.
#
# Copyright (?) 2025 Sven Krause <sven.krause@fh-dortmund.de> 
#
# SPDX-License-Identifier: BSD-2-Clause

from litex.build.io import CRG  #this has (ostensibly) vendor agnostic power-on reset
                                 #might be useless though
from litex.gen import LiteXModule   

#Dedicated CRG class for Gatemate.
#This is for initial testing only     
class _CRG_CCGM(LiteXModule):
    def __init__(self, platform,  sys_clk_freq, ref_clk_freq):
        from litex.soc.cores.clock.colognechip import GateMatePLL
        self.rst    = Signal()
        rst_n       = Signal()
        self.cd_sys = ClockDomain()

        # Clk / Rst
        ref_clk = platform.request("clk")
        #watch for active low/high reset
        self.rst = platform.request("rst", 0)

        self.specials += Instance("CC_USR_RSTN", o_USR_RSTN = rst_n)

        # PLL
        self.pll = pll = GateMatePLL(perf_mode="economy")
        self.comb += pll.reset.eq(~rst_n | self.rst)
        pll.register_clkin(ref_clk, ref_clk_freq)
        pll.create_clkout(self.cd_sys, sys_clk_freq)
        
        #I don't think this is necessary to implement
        #platform.add_period_constraint(self.cd_sys.clk, 1e9/sys_clk_freq)

class _CRG_XilinxSpartan6(LiteXModule):
    def __init__(self, platform, sys_clk_freq, ref_clk_freq):
        from litex.soc.cores.clock.xilinx_s6 import S6PLL
        self.rst       = Signal()
        self.cd_sys    = ClockDomain()

        # Clk/Rst
        ref_clk = platform.request("clk")
        rst = platform.request("rst")

        # PLL
        self.pll = pll = S6PLL()
        self.comb += pll.reset.eq(~rst | self.rst)
        pll.register_clkin(ref_clk, ref_clk_freq)
        pll.create_clkout(self.cd_sys,    sys_clk_freq)

class _CRG_Xilinx7Series(LiteXModule):
    def __init__(self, platform, sys_clk_freq, ref_clk_freq):
        from litex.soc.cores.clock.xilinx_s7 import S7PLL
        self.rst          = Signal()
        self.cd_sys       = ClockDomain()
        # # #
        ref_clk = platform.request("clk")

        self.pll = pll = S7PLL(speedgrade=-1) #TODO: Check significance of speedgrade here!
        self.comb += pll.reset.eq(~platform.request("rst") | self.rst) #TODO:Check if reset thing here is correct
        pll.register_clkin(ref_clk, ref_clk_freq)
        pll.create_clkout(self.cd_sys,       sys_clk_freq)
        
        """
        These are found in many of the target files, but I think they aren't needed here.
        The first sets constraints in the constraint file that litex can generate but isn't
        utilized here. It may make sense to look into that at a later point...
        The second instatiates the "IDELAYCTRL" primitive for input delay calibration, which
        is beyond the scope of what this generator is supposed to do. 
        """
        #platform.add_false_path_constraints(self.cd_sys.clk, pll.clkin) # Ignore sys_clk to pll.clkin path created by SoC's rst.
        #self.idelayctrl = S7IDELAYCTRL(self.cd_idelay)

class _CRG_XilinxUltrascale(LiteXModule):
    #keeping this as simple as possible for now
    def __init__(self, platform, sys_clk_freq, ref_clk_freq):
        from litex.soc.cores.clock.xilinx_us import USMMCM
        self.rst       = Signal()
        self.cd_sys    = ClockDomain()
        # # #
        self.pll = pll = USMMCM(speedgrade=-2)
        self.comb += pll.reset.eq(platform.request("rst") | self.rst)
        pll.register_clkin(platform.request("clk"), ref_clk_freq)
        pll.create_clkout(self.cd_sys, sys_clk_freq)
       
        """not sure why, but the target files for US and USP are a bit odd; some import the platform
            but use S7PLL instantiation or they use this weird CRG module that creates a 4x sys_clk
            for no apparent reason other than to divide it back down to sys_clk using a BUFGCE_DIV buffer
            I could not find the sys4x.clk connected to anything in any of the target files...
            Might be for DDRRAM, but I'll have to look into that...
        self.specials += [
            Instance("BUFGCE_DIV",
                p_BUFGCE_DIVIDE=4,
                i_CE=1, i_I=self.cd_pll4x.clk, o_O=self.cd_sys.clk),
            Instance("BUFGCE",
                i_CE=1, i_I=self.cd_pll4x.clk, o_O=self.cd_sys4x.clk),
        ]

        self.idelayctrl = USIDELAYCTRL(cd_ref=self.cd_idelay, cd_sys=self.cd_sys)
        """
 
class _CRG_XilinxUltrascalePlus(LiteXModule):
    #also doing a minimalist iplementation here for now
    def __init__(self, platform, sys_clk_freq, ref_clk_freq):
        from litex.soc.cores.clock.xilinx_usp import USPMMCM
        self.rst       = Signal()
        self.cd_sys    = ClockDomain()
        # # #
        self.pll = pll = USPMMCM(speedgrade=-2)
        self.comb += pll.reset.eq(self.rst)
        pll.register_clkin(platform.request("clk"), ref_clk_freq)
        pll.create_clkout(self.cd_sys, sys_clk_freq)

#This almost works, but for some reason litex is trying to backend stuff...
class _CRG_LatticeECP5(LiteXModule):
    def __init__(self, platform, sys_clk_freq, ref_clk_freq):
        from litex.soc.cores.clock.lattice_ecp5 import ECP5PLL
        from migen.genlib.resetsync import AsyncResetSynchronizer
        #TODO: Find out if the AsyncResetSynchronize is needed/useful here
        self.rst        = Signal()
        self.cd_init    = ClockDomain()
        self.cd_por     = ClockDomain()
        self.cd_sys     = ClockDomain()

        # # #

        self.stop  = Signal()
        self.reset = Signal()

        # Clk / Rst
        ref_clk = platform.request("clk")
        #TODO: Find way to deal with this...
        rst  = platform.request("rst")

        # Power on reset
        por_count = Signal(16, reset=2**16-1)
        por_done  = Signal()
        self.comb += self.cd_por.clk.eq(ref_clk)
        self.comb += por_done.eq(por_count == 0)
        self.sync.por += If(~por_done, por_count.eq(por_count - 1))

        # PLL
        self.pll = pll = ECP5PLL()
        self.comb += pll.reset.eq(~por_done | ~rst | self.rst)
        pll.register_clkin(ref_clk, ref_clk_freq)
        pll.create_clkout(self.cd_sys, sys_clk_freq)
        pll.create_clkout(self.cd_init, 25e6)
        self.specials += AsyncResetSynchronizer(self.cd_sys, ~pll.locked | self.reset)
        
        """ This part is only needed when using ddr memory or other such cores
        self.cd_sys2x   = ClockDomain()
        self.cd_sys2x_i = ClockDomain()
        
        pll.create_clkout(self.cd_sys2x_i, 2*sys_clk_freq)
        pll.create_clkout(self.cd_init, 25e6)
        self.specials += [
            Instance("ECLKSYNCB",
                i_ECLKI = self.cd_sys2x_i.clk,
                i_STOP  = self.stop,
                o_ECLKO = self.cd_sys2x.clk),
            Instance("CLKDIVF",
                p_DIV     = "2.0",
                i_ALIGNWD = 0,
                i_CLKI    = self.cd_sys2x.clk,
                i_RST     = self.reset,
                o_CDIVX   = self.cd_sys.clk),
            AsyncResetSynchronizer(self.cd_sys, ~pll.locked | self.reset),
        ]"""
  
class _CRGLatticeiCE40(LiteXModule):
    #Note: This was essentially just copied from the icebreaker.py target file
    def __init__(self, platform, sys_clk_freq, ref_clk_freq):
        self.rst    = Signal()
        self.cd_sys = ClockDomain()
        self.cd_por = ClockDomain()
        # # #

        # Clk/Rst
        clk = platform.request("clk")
        rst_n = platform.request("user_btn_n")

        # Power On Reset
        por_count = Signal(16, reset=2**16-1)
        por_done  = Signal()
        self.comb += self.cd_por.clk.eq(ClockSignal())
        self.comb += por_done.eq(por_count == 0)
        self.sync.por += If(~por_done, por_count.eq(por_count - 1))

        # PLL
        self.pll = pll = iCE40PLL(primitive="SB_PLL40_PAD")
        self.comb += pll.reset.eq(~rst_n) # TODO: Add proper iCE40PLL reset support and add back | self.rst.
        pll.register_clkin(clk12, 12e6)
        pll.create_clkout(self.cd_sys, sys_clk_freq, with_reset=False)
        self.specials += AsyncResetSynchronizer(self.cd_sys, ~por_done | ~pll.locked)
        #platform.add_period_constraint(self.cd_sys.clk, 1e9/sys_clk_freq)