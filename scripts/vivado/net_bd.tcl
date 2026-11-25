# Dedicated GEM-to-PL receive memory; original GP0 DMA/control path retained.
source [file join $root scripts vivado system_bd.tcl]
set_property CONFIG.PCW_USE_M_AXI_GP1 {1} [get_bd_cells ps7]
set nic [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_interconnect:2.1 net_bus]
set_property -dict [list CONFIG.NUM_SI 1 CONFIG.NUM_MI 1] $nic
set bc [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_bram_ctrl:4.1 net_bram_ctrl]
set_property -dict [list CONFIG.DATA_WIDTH 64 CONFIG.SINGLE_PORT_BRAM 1 CONFIG.ECC_TYPE 0] $bc
set br [create_bd_cell -type ip -vlnv xilinx.com:ip:blk_mem_gen:8.4 net_memory]
set_property -dict [list CONFIG.Memory_Type True_Dual_Port_RAM \
    CONFIG.Use_Byte_Write_Enable true CONFIG.Byte_Size 8 \
    CONFIG.Write_Width_A 64 CONFIG.Write_Depth_A 32768 CONFIG.Read_Width_A 64 \
    CONFIG.Write_Width_B 64 CONFIG.Read_Width_B 64 \
    CONFIG.Enable_B Use_ENB_Pin CONFIG.Register_PortB_Output_of_Memory_Primitives false \
    CONFIG.Register_PortA_Output_of_Memory_Primitives false] $br
connect_bd_intf_net [get_bd_intf_pins ps7/M_AXI_GP1] [get_bd_intf_pins net_bus/S00_AXI]
connect_bd_intf_net [get_bd_intf_pins net_bus/M00_AXI] [get_bd_intf_pins net_bram_ctrl/S_AXI]
connect_bd_intf_net [get_bd_intf_pins net_bram_ctrl/BRAM_PORTA] [get_bd_intf_pins net_memory/BRAM_PORTA]
make_bd_intf_pins_external [get_bd_intf_pins net_memory/BRAM_PORTB]
set_property name NET_BRAM [get_bd_intf_ports BRAM_PORTB_0]
# The external master must describe all eight byte enables. Leaving its default
# MEM_WIDTH=32 silently tied WEB[7:4] low in the generated 64-bit memory netlist.
# BRAM-controller mode also requires symmetric ports; the AXI interconnect
# converts GP1's 32-bit transactions to the 64-bit controller interface.
set_property -dict [list CONFIG.MEM_WIDTH 64 CONFIG.MEM_SIZE 262144] [get_bd_intf_ports NET_BRAM]
connect_bd_net [get_bd_pins ps7/FCLK_CLK0] [get_bd_pins ps7/M_AXI_GP1_ACLK] \
    [get_bd_pins net_bus/ACLK] [get_bd_pins net_bus/S00_ACLK] [get_bd_pins net_bus/M00_ACLK] \
    [get_bd_pins net_bram_ctrl/s_axi_aclk]
connect_bd_net [get_bd_pins reset/interconnect_aresetn] [get_bd_pins net_bus/ARESETN]
connect_bd_net [get_bd_pins reset/peripheral_aresetn] [get_bd_pins net_bus/S00_ARESETN] \
    [get_bd_pins net_bus/M00_ARESETN] [get_bd_pins net_bram_ctrl/s_axi_aresetn]
assign_bd_address -offset 0x80000000 -range 0x00040000 \
    -target_address_space [get_bd_addr_spaces ps7/Data] [get_bd_addr_segs net_bram_ctrl/S_AXI/Mem0]
source [file join $root scripts vivado net_tx.tcl]
validate_bd_design
save_bd_design
