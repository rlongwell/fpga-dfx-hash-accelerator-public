# Sourced by system.tcl in a fresh project for xc7z020clg400-1.
set_property board_part digilentinc.com:zybo-z7-20:part0:1.2 [current_project]
create_bd_design ps_dma
set ps [create_bd_cell -type ip -vlnv xilinx.com:ip:processing_system7:5.5 ps7]
apply_bd_automation -rule xilinx.com:bd_rule:processing_system7 \
    -config {make_external "FIXED_IO, DDR" apply_board_preset "1" Master "Disable" Slave "Disable"} $ps
set_property -dict [list CONFIG.PCW_USE_M_AXI_GP0 {1} CONFIG.PCW_USE_S_AXI_HP0 {1} \
    CONFIG.PCW_S_AXI_HP0_DATA_WIDTH {64} CONFIG.PCW_EN_CLK0_PORT {1} \
    CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ {100} CONFIG.PCW_USE_FABRIC_INTERRUPT {1} \
    CONFIG.PCW_IRQ_F2P_INTR {1}] $ps
set dma [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_dma:7.1 dma]
set_property -dict [list CONFIG.c_include_sg {0} CONFIG.c_include_mm2s {1} \
    CONFIG.c_include_s2mm {0} CONFIG.c_m_axi_mm2s_data_width {64} \
    CONFIG.c_m_axis_mm2s_tdata_width {64} CONFIG.c_include_mm2s_dre {1} \
    CONFIG.c_sg_length_width {26} CONFIG.c_addr_width {32}] $dma
set ctrl [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_interconnect:2.1 control]
set_property -dict [list CONFIG.NUM_SI {1} CONFIG.NUM_MI {2}] $ctrl
set mem [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_interconnect:2.1 memory]
set_property -dict [list CONFIG.NUM_SI {1} CONFIG.NUM_MI {1}] $mem
set rst [create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset:5.0 reset]
set_property CONFIG.C_EXT_RESET_HIGH {0} $rst
set one [create_bd_cell -type ip -vlnv xilinx.com:ip:xlconstant:1.1 one]
set_property -dict [list CONFIG.CONST_WIDTH {1} CONFIG.CONST_VAL {1}] $one
set irqcat [create_bd_cell -type ip -vlnv xilinx.com:ip:xlconcat:2.1 interrupts]
set_property CONFIG.NUM_PORTS {2} $irqcat

connect_bd_intf_net [get_bd_intf_pins ps7/M_AXI_GP0] [get_bd_intf_pins control/S00_AXI]
connect_bd_intf_net [get_bd_intf_pins control/M00_AXI] [get_bd_intf_pins dma/S_AXI_LITE]
connect_bd_intf_net [get_bd_intf_pins dma/M_AXI_MM2S] [get_bd_intf_pins memory/S00_AXI]
connect_bd_intf_net [get_bd_intf_pins memory/M00_AXI] [get_bd_intf_pins ps7/S_AXI_HP0]
set ext_ctrl [create_bd_intf_port -mode Master -vlnv xilinx.com:interface:aximm_rtl:1.0 M_AXI_CTRL]
set_property -dict [list CONFIG.PROTOCOL {AXI4LITE} CONFIG.ADDR_WIDTH {32} \
    CONFIG.DATA_WIDTH {32} CONFIG.READ_WRITE_MODE {READ_WRITE} \
    CONFIG.HAS_BURST {0} CONFIG.HAS_LOCK {0} CONFIG.HAS_CACHE {0} \
    CONFIG.HAS_QOS {0} CONFIG.HAS_REGION {0}] $ext_ctrl
connect_bd_intf_net $ext_ctrl [get_bd_intf_pins control/M01_AXI]
set ext_axis [create_bd_intf_port -mode Master -vlnv xilinx.com:interface:axis_rtl:1.0 M_AXIS_DATA]
connect_bd_intf_net $ext_axis [get_bd_intf_pins dma/M_AXIS_MM2S]

set clkport [create_bd_port -dir O -type clk pl_clk]
set_property -dict [list CONFIG.FREQ_HZ {100000000} \
    CONFIG.ASSOCIATED_BUSIF {M_AXI_CTRL:M_AXIS_DATA} CONFIG.ASSOCIATED_RESET {pl_resetn}] $clkport
set rstport [create_bd_port -dir O -type rst pl_resetn]
set_property CONFIG.POLARITY ACTIVE_LOW $rstport
set irqport [create_bd_port -dir I -type intr hash_irq]
set_property CONFIG.SENSITIVITY LEVEL_HIGH $irqport
connect_bd_net [get_bd_pins ps7/FCLK_CLK0] $clkport [get_bd_pins reset/slowest_sync_clk] \
    [get_bd_pins ps7/M_AXI_GP0_ACLK] [get_bd_pins ps7/S_AXI_HP0_ACLK] \
    [get_bd_pins dma/s_axi_lite_aclk] [get_bd_pins dma/m_axi_mm2s_aclk] \
    [get_bd_pins control/ACLK] [get_bd_pins control/S00_ACLK] \
    [get_bd_pins control/M00_ACLK] [get_bd_pins control/M01_ACLK] \
    [get_bd_pins memory/ACLK] [get_bd_pins memory/S00_ACLK] [get_bd_pins memory/M00_ACLK]
connect_bd_net [get_bd_pins ps7/FCLK_RESET0_N] [get_bd_pins reset/ext_reset_in]
connect_bd_net [get_bd_pins one/dout] [get_bd_pins reset/dcm_locked]
connect_bd_net [get_bd_pins reset/interconnect_aresetn] \
    [get_bd_pins control/ARESETN] [get_bd_pins memory/ARESETN]
connect_bd_net [get_bd_pins reset/peripheral_aresetn] $rstport [get_bd_pins dma/axi_resetn] \
    [get_bd_pins control/S00_ARESETN] [get_bd_pins control/M00_ARESETN] \
    [get_bd_pins control/M01_ARESETN] [get_bd_pins memory/S00_ARESETN] [get_bd_pins memory/M00_ARESETN]
connect_bd_net [get_bd_pins dma/mm2s_introut] [get_bd_pins interrupts/In0]
connect_bd_net $irqport [get_bd_pins interrupts/In1]
connect_bd_net [get_bd_pins interrupts/dout] [get_bd_pins ps7/IRQ_F2P]

# The shell has one stable 4-KiB control aperture; only its register contents vary.
set shell_seg [create_bd_addr_seg -range 0x1000 -offset 0x43C00000 \
    [get_bd_addr_spaces ps7/Data] [get_bd_addr_segs M_AXI_CTRL/Reg] SEG_hash_control]
assign_bd_address -offset 0x40400000 -range 0x00010000 \
    -target_address_space [get_bd_addr_spaces ps7/Data] [get_bd_addr_segs dma/S_AXI_LITE/Reg]
assign_bd_address -offset 0x00000000 -range 0x40000000 \
    -target_address_space [get_bd_addr_spaces dma/Data_MM2S] [get_bd_addr_segs ps7/S_AXI_HP0/HP0_DDR_LOWOCM]
validate_bd_design
save_bd_design
