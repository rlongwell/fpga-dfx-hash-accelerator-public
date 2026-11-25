// SPDX-License-Identifier: MIT
// Static control, DMA-to-file framing and DFX boundary isolation.
module hash_shell (
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
    input logic rp_tready, rp_busy, rp_digest_valid, rp_error,
    input logic [255:0] rp_digest,
    input logic [31:0] rp_algorithm_id
);
    localparam logic [31:0] ABI_VERSION = 32'h00010000;
    localparam logic [31:0] ERR_KEEP=1, ERR_LENGTH=2, ERR_ENGINE=3,
        ERR_CONTROL=4, ERR_ABORT=5, ERR_ISOLATED=6;
    logic isolated, active, done_q, error_q, start_q;
    logic [2:0] reset_count;
    logic [63:0] length_q, accepted_q, remaining_q, cycles_q;
    logic [255:0] digest_q;
    logic [31:0] error_code;
    logic aw_pending, w_pending;
    logic [11:0] awaddr_q;
    logic [31:0] wdata_q;
    logic [3:0] wstrb_q;
    logic [3:0] beat_bytes;
    logic keep_ok, beat_ok, engine_ready;

    function automatic logic [31:0] merge_bytes(
        input logic [31:0] old_value, new_value,
        input logic [3:0] strobes
    );
        for (int i=0;i<4;i++)
            merge_bytes[i*8+:8] = strobes[i] ? new_value[i*8+:8] : old_value[i*8+:8];
    endfunction

    always_comb begin
        beat_bytes = 0;
        for (int i=0;i<8;i++) beat_bytes += {3'b0,s_axis_tkeep[i]};
        keep_ok = (s_axis_tkeep != 0) &&
                  ((s_axis_tkeep & (s_axis_tkeep + 8'd1)) == 0);
        // Keep the 64-bit subtract in a local registered counter. Only a small
        // compare/reduction crosses the DFX boundary in the handshake path.
        beat_ok = keep_ok && ((|remaining_q[63:4]) || remaining_q[3:0] >= beat_bytes);
    end

    assign rp_resetn = aresetn && !isolated && (reset_count == 0);
    assign rp_start = start_q && rp_resetn;
    assign rp_message_length = rp_resetn ? length_q : 64'd0;
    assign rp_tdata = rp_resetn ? s_axis_tdata : 64'd0;
    assign rp_tkeep = rp_resetn ? s_axis_tkeep : 8'd0;
    assign rp_tvalid = rp_resetn && active && !start_q &&
                      (remaining_q != 0) && s_axis_tvalid && beat_ok;
    assign rp_tlast = rp_tvalid && !(|remaining_q[63:4]) && (beat_bytes == remaining_q[3:0]);
    assign s_axis_tready = rp_resetn && active && !start_q &&
                          (remaining_q != 0) &&
                          ((s_axis_tvalid && !beat_ok) || rp_tready);
    assign rp_digest_ready = rp_resetn && active && !start_q;
    assign engine_ready = rp_resetn && !active && !rp_busy && !rp_digest_valid;
    assign irq = done_q || error_q;

    assign s_axi_awready = aresetn && !aw_pending && !s_axi_bvalid;
    assign s_axi_wready = aresetn && !w_pending && !s_axi_bvalid;
    assign s_axi_arready = aresetn && !s_axi_rvalid;

    always_ff @(posedge aclk) begin
        if (!aresetn) begin
            isolated <= 1; active <= 0; done_q <= 0; error_q <= 0; start_q <= 0;
            reset_count <= 4; length_q <= 0; accepted_q <= 0; remaining_q <= 0; cycles_q <= 0;
            digest_q <= 0; error_code <= 0;
            aw_pending <= 0; w_pending <= 0; awaddr_q <= 0; wdata_q <= 0; wstrb_q <= 0;
            s_axi_bresp <= 0; s_axi_bvalid <= 0;
            s_axi_rresp <= 0; s_axi_rvalid <= 0; s_axi_rdata <= 0;
        end else begin
            start_q <= 0;
            if (isolated) reset_count <= 4;
            else if (reset_count != 0) reset_count <= reset_count - 1'b1;
            if (active) cycles_q <= cycles_q + 1'b1;

            if (s_axis_tvalid && s_axis_tready) begin
                if (!beat_ok) begin
                    active <= 0; error_q <= 1; reset_count <= 4;
                    error_code <= keep_ok ? ERR_LENGTH : ERR_KEEP;
                end else begin
                    accepted_q <= accepted_q + {60'd0,beat_bytes};
                    remaining_q <= remaining_q - {60'd0,beat_bytes};
                end
            end
            if (active && rp_resetn && !start_q) begin
                if (rp_error) begin
                    active <= 0; error_q <= 1; error_code <= ERR_ENGINE; reset_count <= 4;
                end else if (rp_digest_valid) begin
                    active <= 0;
                    if (remaining_q == 0) begin
                        digest_q <= rp_digest; done_q <= 1;
                    end else begin
                        error_q <= 1; error_code <= ERR_LENGTH; reset_count <= 4;
                    end
                end
            end

            if (s_axi_awvalid && s_axi_awready) begin
                awaddr_q <= s_axi_awaddr[11:0]; aw_pending <= 1;
            end
            if (s_axi_wvalid && s_axi_wready) begin
                wdata_q <= s_axi_wdata; wstrb_q <= s_axi_wstrb; w_pending <= 1;
            end
            if (s_axi_bvalid && s_axi_bready) s_axi_bvalid <= 0;
            if (aw_pending && w_pending && !s_axi_bvalid) begin
                aw_pending <= 0; w_pending <= 0;
                s_axi_bvalid <= 1; s_axi_bresp <= 0;
                case (awaddr_q[11:0])
                    12'h000: if (wstrb_q[0]) begin
                        // ISOLATE is a retained bit; all other control bits are pulses.
                        isolated <= wdata_q[2];
                        if (wdata_q[3]) begin
                            done_q <= 0; error_q <= 0; error_code <= 0;
                        end
                        if (wdata_q[2] && active) begin
                            active <= 0; error_q <= 1; error_code <= ERR_ISOLATED;
                            reset_count <= 4;
                        end
                        if (wdata_q[1]) begin
                            active <= 0; done_q <= 0; error_q <= 1;
                            error_code <= ERR_ABORT; reset_count <= 4;
                        end
                        if (wdata_q[0]) begin
                            if (!engine_ready || wdata_q[2] || wdata_q[1] ||
                                (rp_algorithm_id == 2 && |length_q[63:61])) begin
                                error_q <= 1; error_code <= ERR_CONTROL; s_axi_bresp <= 2;
                            end else begin
                                active <= 1; start_q <= 1; done_q <= 0; error_q <= 0;
                                accepted_q <= 0; remaining_q <= length_q;
                                cycles_q <= 0; digest_q <= 0; error_code <= 0;
                            end
                        end
                    end
                    12'h010: begin
                        if (active) s_axi_bresp <= 2;
                        else length_q[31:0] <= merge_bytes(length_q[31:0],wdata_q,wstrb_q);
                    end
                    12'h014: begin
                        if (active) s_axi_bresp <= 2;
                        else length_q[63:32] <= merge_bytes(length_q[63:32],wdata_q,wstrb_q);
                    end
                    default: s_axi_bresp <= 2;
                endcase
            end

            if (s_axi_rvalid && s_axi_rready) s_axi_rvalid <= 0;
            if (s_axi_arvalid && s_axi_arready) begin
                s_axi_rvalid <= 1; s_axi_rresp <= 0;
                case (s_axi_araddr[11:0])
                    12'h000: s_axi_rdata <= {29'd0,isolated,2'd0};
                    12'h004: s_axi_rdata <= {27'd0,engine_ready,isolated,error_q,done_q,active};
                    12'h008: s_axi_rdata <= rp_resetn ? rp_algorithm_id : 32'd0;
                    12'h00c: s_axi_rdata <= ABI_VERSION;
                    12'h010: s_axi_rdata <= length_q[31:0];
                    12'h014: s_axi_rdata <= length_q[63:32];
                    12'h018: s_axi_rdata <= accepted_q[31:0];
                    12'h01c: s_axi_rdata <= accepted_q[63:32];
                    12'h020,12'h024,12'h028,12'h02c,
                    12'h030,12'h034,12'h038,12'h03c:
                        s_axi_rdata <= digest_q[s_axi_araddr[4:2]*32+:32];
                    12'h040: s_axi_rdata <= cycles_q[31:0];
                    12'h044: s_axi_rdata <= cycles_q[63:32];
                    12'h048: s_axi_rdata <= error_code;
                    default: begin s_axi_rdata <= 0; s_axi_rresp <= 2; end
                endcase
            end
        end
    end

    // DMA TLAST is intentionally not used to end a file. AXI PROT has no
    // permission interpretation in this peripheral; PS address protection is external.
    logic unused_inputs;
    assign unused_inputs = ^{s_axis_tlast,s_axi_awprot,s_axi_arprot,
                             s_axi_awaddr[31:12],s_axi_araddr[31:12]};
endmodule
