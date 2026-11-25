// SPDX-License-Identifier: MIT
// Simulation wrapper with partition boundary observation ports.
module hash_integration (
    input logic aclk, aresetn,
    input logic [31:0] s_axi_awaddr,
    input logic [2:0] s_axi_awprot,
    input logic s_axi_awvalid,
    output logic s_axi_awready,
    input logic [31:0] s_axi_wdata,
    input logic [3:0] s_axi_wstrb,
    input logic s_axi_wvalid,
    output logic s_axi_wready,
    output logic [1:0] s_axi_bresp,
    output logic s_axi_bvalid,
    input logic s_axi_bready,
    input logic [31:0] s_axi_araddr,
    input logic [2:0] s_axi_arprot,
    input logic s_axi_arvalid,
    output logic s_axi_arready,
    output logic [31:0] s_axi_rdata,
    output logic [1:0] s_axi_rresp,
    output logic s_axi_rvalid,
    input logic s_axi_rready,
    input logic [63:0] s_axis_tdata,
    input logic [7:0] s_axis_tkeep,
    input logic s_axis_tvalid, s_axis_tlast,
    output logic s_axis_tready,
    output logic irq,
    output logic rp_start, rp_resetn,
    output logic [63:0] rp_message_length, rp_tdata,
    output logic [7:0] rp_tkeep,
    output logic rp_tvalid, rp_tlast, rp_digest_ready,
    output logic rp_tready, rp_busy, rp_digest_valid, rp_error,
    output logic [255:0] rp_digest,
    output logic [31:0] rp_algorithm_id
);
    hash_shell control (.*);
    hash_rm u_hash (
        .aclk, .aresetn(rp_resetn), .start(rp_start),
        .message_length(rp_message_length), .s_axis_tdata(rp_tdata),
        .s_axis_tkeep(rp_tkeep), .s_axis_tvalid(rp_tvalid),
        .s_axis_tlast(rp_tlast), .s_axis_tready(rp_tready),
        .digest(rp_digest), .digest_valid(rp_digest_valid),
        .digest_ready(rp_digest_ready), .busy(rp_busy),
        .algorithm_id(rp_algorithm_id), .error(rp_error)
    );
endmodule
