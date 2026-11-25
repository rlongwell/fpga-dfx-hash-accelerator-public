# PL issues only a GEM transmit-start write, with acknowledgments entirely in BRAM.
# S_AXI_GP0 can access PS peripheral registers; HP ports cannot.
set_property CONFIG.PCW_USE_S_AXI_GP0 1 [get_bd_cells ps7]
set txbus [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_interconnect:2.1 net_tx_bus]
set_property -dict [list CONFIG.NUM_SI 1 CONFIG.NUM_MI 1] $txbus
set tx [create_bd_intf_port -mode Slave -vlnv xilinx.com:interface:aximm_rtl:1.0 S_AXI_NET]
set_property -dict [list CONFIG.PROTOCOL AXI4LITE CONFIG.ADDR_WIDTH 32 CONFIG.DATA_WIDTH 32 \
    CONFIG.READ_WRITE_MODE READ_WRITE CONFIG.HAS_BURST 0 CONFIG.HAS_LOCK 0 \
    CONFIG.HAS_CACHE 0 CONFIG.HAS_QOS 0 CONFIG.HAS_REGION 0 CONFIG.FREQ_HZ 100000000] $tx
connect_bd_intf_net $tx [get_bd_intf_pins net_tx_bus/S00_AXI]
connect_bd_intf_net [get_bd_intf_pins net_tx_bus/M00_AXI] [get_bd_intf_pins ps7/S_AXI_GP0]
connect_bd_net [get_bd_pins ps7/FCLK_CLK0] [get_bd_pins ps7/S_AXI_GP0_ACLK] \
    [get_bd_pins net_tx_bus/ACLK] [get_bd_pins net_tx_bus/S00_ACLK] [get_bd_pins net_tx_bus/M00_ACLK]
connect_bd_net [get_bd_pins reset/interconnect_aresetn] [get_bd_pins net_tx_bus/ARESETN]
connect_bd_net [get_bd_pins reset/peripheral_aresetn] \
    [get_bd_pins net_tx_bus/S00_ARESETN] [get_bd_pins net_tx_bus/M00_ARESETN]
set_property CONFIG.ASSOCIATED_BUSIF {M_AXI_CTRL:M_AXIS_DATA:S_AXI_NET} [get_bd_ports pl_clk]
puts "NET_TX_SEGMENTS [get_bd_addr_segs ps7/S_AXI_GP0/*]"
assign_bd_address -target_address_space [get_bd_addr_spaces S_AXI_NET] [get_bd_addr_segs ps7/S_AXI_GP0/*]
validate_bd_design
save_bd_design
