// SPDX-License-Identifier: MIT
// One static PS/DMA/control shell and one physically reconfigurable hash cell.
module system_top (
    inout wire [14:0] DDR_addr,
    inout wire [2:0] DDR_ba,
    inout wire DDR_cas_n,
    inout wire DDR_ck_n,
    inout wire DDR_ck_p,
    inout wire DDR_cke,
    inout wire DDR_cs_n,
    inout wire [3:0] DDR_dm,
    inout wire [31:0] DDR_dq,
    inout wire [3:0] DDR_dqs_n,
    inout wire [3:0] DDR_dqs_p,
    inout wire DDR_odt,
    inout wire DDR_ras_n,
    inout wire DDR_reset_n,
    inout wire DDR_we_n,
    inout wire FIXED_IO_ddr_vrn,
    inout wire FIXED_IO_ddr_vrp,
    inout wire [53:0] FIXED_IO_mio,
    inout wire FIXED_IO_ps_clk,
    inout wire FIXED_IO_ps_porb,
    inout wire FIXED_IO_ps_srstb
);
    wire aclk, aresetn, irq;
    wire [31:0] s_axi_awaddr;
    wire [2:0] s_axi_awprot;
    wire s_axi_awvalid;
    wire s_axi_awready;
    wire [31:0] s_axi_wdata;
    wire [3:0] s_axi_wstrb;
    wire s_axi_wvalid;
    wire s_axi_wready;
    wire [1:0] s_axi_bresp;
    wire s_axi_bvalid;
    wire s_axi_bready;
    wire [31:0] s_axi_araddr;
    wire [2:0] s_axi_arprot;
    wire s_axi_arvalid;
    wire s_axi_arready;
    wire [31:0] s_axi_rdata;
    wire [1:0] s_axi_rresp;
    wire s_axi_rvalid;
    wire s_axi_rready;
    wire [63:0] s_axis_tdata;
    wire [7:0] s_axis_tkeep;
    wire s_axis_tvalid;
    wire s_axis_tready;
    wire s_axis_tlast;
    wire rp_start;
    wire rp_resetn;
    wire [63:0] rp_message_length;
    wire [63:0] rp_tdata;
    wire [7:0] rp_tkeep;
    wire rp_tvalid;
    wire rp_tlast;
    wire rp_digest_ready;
    wire rp_tready;
    wire rp_busy;
    wire rp_digest_valid;
    wire rp_error;
    wire [255:0] rp_digest;
    wire [31:0] rp_algorithm_id;

    ps_dma_wrapper u_ps_dma (
        .DDR_addr(DDR_addr),
        .DDR_ba(DDR_ba),
        .DDR_cas_n(DDR_cas_n),
        .DDR_ck_n(DDR_ck_n),
        .DDR_ck_p(DDR_ck_p),
        .DDR_cke(DDR_cke),
        .DDR_cs_n(DDR_cs_n),
        .DDR_dm(DDR_dm),
        .DDR_dq(DDR_dq),
        .DDR_dqs_n(DDR_dqs_n),
        .DDR_dqs_p(DDR_dqs_p),
        .DDR_odt(DDR_odt),
        .DDR_ras_n(DDR_ras_n),
        .DDR_reset_n(DDR_reset_n),
        .DDR_we_n(DDR_we_n),
        .FIXED_IO_ddr_vrn(FIXED_IO_ddr_vrn),
        .FIXED_IO_ddr_vrp(FIXED_IO_ddr_vrp),
        .FIXED_IO_mio(FIXED_IO_mio),
        .FIXED_IO_ps_clk(FIXED_IO_ps_clk),
        .FIXED_IO_ps_porb(FIXED_IO_ps_porb),
        .FIXED_IO_ps_srstb(FIXED_IO_ps_srstb),
        .M_AXI_CTRL_awaddr(s_axi_awaddr),
        .M_AXI_CTRL_awprot(s_axi_awprot),
        .M_AXI_CTRL_awvalid(s_axi_awvalid),
        .M_AXI_CTRL_awready(s_axi_awready),
        .M_AXI_CTRL_wdata(s_axi_wdata),
        .M_AXI_CTRL_wstrb(s_axi_wstrb),
        .M_AXI_CTRL_wvalid(s_axi_wvalid),
        .M_AXI_CTRL_wready(s_axi_wready),
        .M_AXI_CTRL_bresp(s_axi_bresp),
        .M_AXI_CTRL_bvalid(s_axi_bvalid),
        .M_AXI_CTRL_bready(s_axi_bready),
        .M_AXI_CTRL_araddr(s_axi_araddr),
        .M_AXI_CTRL_arprot(s_axi_arprot),
        .M_AXI_CTRL_arvalid(s_axi_arvalid),
        .M_AXI_CTRL_arready(s_axi_arready),
        .M_AXI_CTRL_rdata(s_axi_rdata),
        .M_AXI_CTRL_rresp(s_axi_rresp),
        .M_AXI_CTRL_rvalid(s_axi_rvalid),
        .M_AXI_CTRL_rready(s_axi_rready),
        .M_AXIS_DATA_tdata(s_axis_tdata),
        .M_AXIS_DATA_tkeep(s_axis_tkeep),
        .M_AXIS_DATA_tvalid(s_axis_tvalid),
        .M_AXIS_DATA_tready(s_axis_tready),
        .M_AXIS_DATA_tlast(s_axis_tlast),
        .hash_irq(irq),
        .pl_clk(aclk),
        .pl_resetn(aresetn)
    );

    hash_shell u_shell (
        .aclk(aclk),
        .aresetn(aresetn),
        .irq(irq),
        .s_axi_awaddr(s_axi_awaddr),
        .s_axi_awprot(s_axi_awprot),
        .s_axi_awvalid(s_axi_awvalid),
        .s_axi_awready(s_axi_awready),
        .s_axi_wdata(s_axi_wdata),
        .s_axi_wstrb(s_axi_wstrb),
        .s_axi_wvalid(s_axi_wvalid),
        .s_axi_wready(s_axi_wready),
        .s_axi_bresp(s_axi_bresp),
        .s_axi_bvalid(s_axi_bvalid),
        .s_axi_bready(s_axi_bready),
        .s_axi_araddr(s_axi_araddr),
        .s_axi_arprot(s_axi_arprot),
        .s_axi_arvalid(s_axi_arvalid),
        .s_axi_arready(s_axi_arready),
        .s_axi_rdata(s_axi_rdata),
        .s_axi_rresp(s_axi_rresp),
        .s_axi_rvalid(s_axi_rvalid),
        .s_axi_rready(s_axi_rready),
        .s_axis_tdata(s_axis_tdata),
        .s_axis_tkeep(s_axis_tkeep),
        .s_axis_tvalid(s_axis_tvalid),
        .s_axis_tready(s_axis_tready),
        .s_axis_tlast(s_axis_tlast),
        .rp_start(rp_start),
        .rp_resetn(rp_resetn),
        .rp_message_length(rp_message_length),
        .rp_tdata(rp_tdata),
        .rp_tkeep(rp_tkeep),
        .rp_tvalid(rp_tvalid),
        .rp_tlast(rp_tlast),
        .rp_digest_ready(rp_digest_ready),
        .rp_tready(rp_tready),
        .rp_busy(rp_busy),
        .rp_digest_valid(rp_digest_valid),
        .rp_error(rp_error),
        .rp_digest(rp_digest),
        .rp_algorithm_id(rp_algorithm_id)
    );

    (* KEEP_HIERARCHY = "yes" *) hash_rm u_hash (
        .aclk(aclk),
        .aresetn(rp_resetn),
        .start(rp_start),
        .message_length(rp_message_length),
        .s_axis_tdata(rp_tdata),
        .s_axis_tkeep(rp_tkeep),
        .s_axis_tvalid(rp_tvalid),
        .s_axis_tready(rp_tready),
        .s_axis_tlast(rp_tlast),
        .digest(rp_digest),
        .digest_valid(rp_digest_valid),
        .digest_ready(rp_digest_ready),
        .busy(rp_busy),
        .algorithm_id(rp_algorithm_id),
        .error(rp_error)
    );
endmodule
