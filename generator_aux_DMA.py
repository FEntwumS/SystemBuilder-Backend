#!/usr/bin/env python3

#
# This file is not part of LiteX.
# Copyright (?) 2025 Sven Krause <sven.krause@fh-dortmund.de> 
#
# SPDX-License-Identifier: BSD-2-Clause

import shutil
import yaml
import sys
import os

from litex.soc.interconnect import *
from litex.soc.interconnect.csr_eventmanager import *
from litex.gen import LiteXModule 
#from litex.soc.interconnect import stream
from litex.soc.cores.dma import WishboneDMAReader, WishboneDMAWriter

""" This file contains classes related to DMA for use with litex_generator.py

    NOTE: All of this here is still work in progress and may contain some bad designs!

    This comment is used for general information on what's here as well as how LiteX's
    stream interfaces work. It is supposed to serve as documentation of how this aspect
    of the System Builder works. If you have anything to add or correct, feel free to 
    reach out and submit your notes.    

    Top-Level:
        1. WishboneDmaTestSimple (Testsystem: Write from mem to FIFO and back to mem)
        2. WishboneDmaTest       (Like DmaTestSimple, but with arbitrary FIFO width)
    Sub-classes:    
        1. WishboneDmaMemToX
        2. WishboneDmaXToMem
    Controls/"Cores":
        1. DMATestCore
    
    Some important observations reagrding the stream classes:
        -The "stream" classes are a flexible way to implement dma and other data
         streams and can be adapted to work with different interfaces
        -The standard interface is not very transparent and it's not really obvious how
         signals will behave when they aren't deliberately controlled in the design
            -E.g. signals like "first" and "last" will have to be set somewhere in the
             chain of "Endpoints". If they are not set explicitly, it is assumed that
             they will come form the previous link in the chain. If no link sets the 
             signals, they will always be 0.
        -It seems that there aren't many "hard" rules on how to use the stream classes
         and the "correct" way depends on the application. LiteX will not stop
         you from creating nonsense designs, so that must be taken into account.
    """

####Top-Level------------------------------------------------------------------------------
#   These classes can be instantiated directly in the litex_generator.py
#   They instantiate sub-classes defined below or imported from liteX

class WishboneDmaTestSimple(LiteXModule):
    def __init__(self, soc, name="generic_dma", mode="read+write", fifo_depth=256):
        #check if directionality mode input is valid
        assert mode in ["read", "write", "read+write"]
        
        #"Core" handles the high-level control and contains the dummy target fifo
        self.core = core = DMATestCore(bus.data_width)
        
        bus = wishbone.Interface(
                data_width  = soc.bus.data_width,
                adr_width   = soc.bus.get_address_width(standard="wishbone"),
                adressing   = "word",   #address by word, other option is "byte"
                mode = "w", #writes to bus
        )        
        self.x2mem_dma = x2mem_dma = WishboneDMAWriter(bus=bus, endianness=soc.cpu.endianness, with_csr=True)
        self.comb += core.source.connect(x2mem_dma.sink)
        #haven't entirely figured out the significance of this
        dma_bus = getattr(soc, "dma_bus", soc.bus)
        dma_bus.add_master(master=bus)
        bus = wishbone.Interface(
            data_width  = soc.bus.data_width,
            adr_width   = soc.bus.get_address_width(standard="wishbone"),
            adressing   = "word",
            mode = "r", #reads from bus
        )
        self.mem2x_dma = mem2x_dma = WishboneDMAReader(bus=bus,fifo_depth=fifo_depth, endianness=soc.cpu.endianness, with_csr=True)
        self.comb += mem2x_dma.source.connect(core.sink)
        #see above comment on dma_bus
        dma_bus = getattr(soc, "dma_bus", soc.bus)
        dma_bus.add_master(master=bus)
        
        #here comes some eventhandler stuff I do not properly understand yet
        self.ev = ev = EventManager()    #instantiate eventmanager (interrupt handler?) 
        if "read" in mode:
            ev.x2mem_dma = EventSourcePulse(description="Block2Mem DMA terminated.")
        if "write" in mode:
            ev.mem2x_dma = EventSourcePulse(description="Mem2Block DMA terminated.") 
  
class WishboneDmaTest(LiteXModule):
    def __init__(self, soc, name="generic_dma", mode="read+write", data_width=32, fifo_depth=256):
        #check if directionality mode input is valid
        assert mode in ["read", "write", "read+write"]
        
        #"Core" handles the high-level control and contains the dummy target fifo
        self.core = core = DMATestCore(data_width)
        
        """Initial version modeled after LiteSDCard
           here an interface to the wishbone bus is created for the "read" side
           "read" means read from X, write to Mem
        """
        if "read" in mode:
            bus = wishbone.Interface(
                data_width  = soc.bus.data_width,
                adr_width   = soc.bus.get_address_width(standard="wishbone"),
                adressing   = "word",   #address by word, other option is "byte"
                mode = "w", #writes to bus
            )
            self.x2mem = x2mem = WishboneDmaXToMem (bus=bus, endianness=soc.cpu.endianness, data_width=data_width)
            self.comb += core.source.connect(x2mem.sink)
            #I'm not entirely sure what the "dma_bus" is about
            dma_bus = getattr(soc, "dma_bus", soc.bus)
            dma_bus.add_master(master=bus)
            
        if "write" in mode:
            bus = wishbone.Interface(
                data_width  = soc.bus.data_width,
                adr_width   = soc.bus.get_address_width(standard="wishbone"),
                adressing   = "word",
                mode = "r", #reads from bus
            )
            self.mem2x = mem2x = WishboneDmaMemToX(bus=bus, endianness=soc.cpu.endianness, data_width=data_width)
            self.comb += mem2x.source.connect(core.sink)
            #see above comment on dma_bus
            dma_bus = getattr(soc, "dma_bus", soc.bus)
            dma_bus.add_master(master=bus)
            
        #here comes some eventhandler stuff I don't really undrstand yet...
        self.ev = ev = EventManager()    #instantiate eventmanager (interrupt handler?) 
        if "read" in mode:
            ev.x2mem_dma = EventSourcePulse(description="Block2Mem DMA terminated.")
        if "write" in mode:
            ev.mem2x_dma = EventSourcePulse(description="Mem2Block DMA terminated.")


####Sub-Classes-----------------------------------------------------------------------------
#   These classes are meant to be used with a wrapper (see WishboneDmaTest)
#   They contain additional adjustable FIFOs and data width converters
#   WishboneDmaXToMem, WishboneDmaMemToX modeled after LiteSDCard's block2mem, mem2block
 
class WishboneDmaMemToX(LiteXModule):
    
    def __init__(self, bus, endianness, fifo_depth=32, data_width=8):
        self.bus = bus
        self.source = stream.Endpoint([("data", data_width)]) #I think "data" is endpoint name, 8 is data width?
        self.irq = Signal() #maybe this exercise can also teach me a thing or two about interrupts in liteX
     
        #initialize dma reader module
        self.dma = WishboneDMAReader(bus, fifo_depth=16, with_csr=True, endianness=endianness)
        #the converter handles the transition from bus_width to data_width
        converter = stream.Converter(bus.data_width, data_width, reverse = True)
        fifo = stream.SyncFIFO([("data", data_width)], fifo_depth, buffered=True)
        self.submodules += converter, fifo
        
        #here some wiring stuff
        #this uses the "stream" classes of litex. 
        #I still haven't quite wrapped my head around how the source/sink terminology works
        self.comb+= [
            self.dma.source.connect(converter.sink),
            converter.source.connect(fifo.sink),
            fifo.source.connect(self.source),
        ]
        
        #This &s previous value of dma._done csr with current one
        #This way the rising edge is detected
        done_d = Signal()
        self.sync += done_d.eq(self.dma._done.status)   #I think the signal is tied to the CSR here
        self.sync += self.irq.eq(self.dma._done.status & ~done_d)

class WishboneDmaXToMem(LiteXModule):
    
    def __init__(self, bus, endianness, fifo_depth=512, data_width=8):
        self.bus = bus
        self.sink = stream.Endpoint([("data", data_width)]) 
        self.irq = Signal()
        
        fifo = stream.SyncFIFO([("data", data_width)], fifo_depth, buffered = True)
        converter = stream.Converter(data_width, bus.data_width, reverse=True)
        self.submodules += fifo, converter
        self.dma = WishboneDMAWriter(bus, endianness=endianness, with_csr=True)
        
        #here Signals are defined and tied to the endpoint and dma classes
        start = Signal()
        connect= Signal()
        #"start" is set to be valid&&first signals from sink (stream.Endoint())
        self.comb += start.eq(self.sink.valid & self.sink.first)
        #"connect" is set 1 when dma._enable.storage (CSR) && start
        #only reset to 0 if dma._enable.storage goes 0
        self.sync += [
            If(~self.dma._enable.storage,
                connect.eq(0)
            ).Elif(start, 
                connect.eq(1)
            )
        ]
        #Here the stream Endpoint "sink" is connected to fifo.sink if
        #dma._enable.storage AND (start OR connect) are set
        #Otherwise the Endpoints "ready" signal is set to 1
        self.comb += [
            If(self.dma._enable.storage & (start | connect),
                self.sink.connect(fifo.sink)
            ).Else(
                self.sink.ready.eq(1)
            ),
            #FIFO gives input to converter, converter gives input to dma
            fifo.source.connect(converter.sink),
            converter.source.connect(self.dma.sink),
        ]
        
        # IRQ / Generate IRQ on DMA done rising edge
        done_d = Signal()
        self.sync += done_d.eq(self.dma._done.status)
        self.sync += self.irq.eq(self.dma._done.status & ~done_d)

####Controls / "Cores"---------------------------------------------------------------------
#   This section contains classes for high-level control of the data flow
#   DMATestCore is part of WishboneDmaTest and WishboneDmaTestSimple
 
class DMATestCore(LiteXModule):    
    from litex.soc.interconnect import stream
    def __init__(self, data_width):
        self.sink   = stream.Endpoint([("data", data_width)])
        self.source   = stream.Endpoint([("data", data_width)])
        #This is the "high level" control logic
        self.start      = CSRStorage(description="Run the test")
        self.wr_done    = CSRStatus(description="Writing complete")
        self.rd_done    = CSRStatus(description="Reading complete")
        
        #some additional CSRs for debugging and understanding what's going on
        self.state = CSRStatus(size=3, description="Current State")
        self.count = CSRStatus(size=8, description="Counter for data read and stuff")
        
         #set up fifo to temporarily store values
        self.fifo = fifo = stream.SyncFIFO([("data", data_width)], 512, buffered = True)
        
        #Like most of this, this is based on the LiteSDCard construct
        #I think this is just assigning variables or cleaner code?
        #maabe the methods from Migen need it idk
        start = self.start.re   #this way the signal should be usable as a "pulse"
        wr_done = self.wr_done.status
        rd_done = self.rd_done.status
    
        data_count = Signal(8)  #8-bit count should be enough
        
        #in analogy to the block delimiter in SDCore, limit data to 32 words
        """
        When using the "last" signals for flow control, this setup wiht the counter
        imposes a hard limit on the length of transmissions. Set up the way it is
        any transmission will be stopped after 32 words.
        """
        self.sync += [
            If(self.sink.valid & self.sink.ready, #under this condition,   
                data_count.eq(data_count + 1),    #a word will be transmitted with each clock cycle 
                If(self.sink.last, data_count.eq(0)) #reset counter on transmission of last word
            )
        ]
        self.comb += If(data_count == 31, 
            self.sink.last.eq(1) #set sink.last, when 31 of 32 words sent
            ).Elif(data_count == 0,
                self.sink.first.eq(1)   #set sink.first for reception of first data
            )
        
        #I will probably need some kind of state machine for control flow
    
        #Control FSM
        self.fsm = fsm = FSM()
        fsm.act("IDLE",
            #initial setup
            NextValue(wr_done, 0),
            NextValue(rd_done, 0),
            NextValue(data_count, 0),
            NextValue(self.state.status, 0),
            If(start,
                NextValue(wr_done, 0),
                NextValue(rd_done, 0),
                NextState("DATA-WRITE")
            )
        )
        fsm.act("DATA-WRITE",
            self.sink.connect(fifo.sink),
            NextValue(self.state.status, 1),
            If(fifo.sink.valid & fifo.sink.ready & fifo.sink.last,
                #When last word is sent, set wr_done and go to next state
                NextValue(wr_done, 1),
                NextState("WAIT")  
            )
        )
        fsm.act("WAIT",
            NextValue(self.state.status, 2),
            If(start,
                NextState("DATA-READ")
            )
        )
        fsm.act("DATA-READ",
            NextValue(self.state.status, 3),
            fifo.source.connect(self.source),
            If(fifo.source.last & fifo.source.ready,
               #fifo.source.connect(self.source),
               NextValue(self.state.status, 4),                
               NextValue(rd_done, 1),   #on last word, set rd_done
               NextState("IDLE")       #and proceed to IDLE state
            )
        )