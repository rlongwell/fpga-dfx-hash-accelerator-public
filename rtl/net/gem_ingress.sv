// SPDX-License-Identifier: MIT
// GEM RX descriptors AND packet buffers live in dual-port FPGA block RAM.
// Port A belongs to GEM/PS AXI; this module owns port B. No ARM payload copies.
// Experimental EtherType 88b5, version/type 1/1; all protocol integers LE.
// 64-byte header: Ethernet(14), version/type(2), session(4), offset(8), size(4).
// Reliable in-order acceptance: duplicate/out-of-order packets are discarded.
module gem_ingress (
    input wire clk, resetn, axi_resetn,
    output logic [17:0] addr,
    output logic en,
    output logic [3:0] we,
    output logic [31:0] wdata,
    input wire [31:0] rdata,
    input wire [63:0] ram64,
    output logic enabled,
    output logic [63:0] tdata,
    output logic [7:0] tkeep,
    output logic tvalid,
    input wire tready,
    output wire tlast,
    input wire [255:0] digest,
    input wire digest_valid, core_error,
    // Write-only AXI-Lite master: start GEM transmission through S_AXI_GP0.
    output logic awvalid, wvalid,
    input wire awready, wready, bvalid,
    input wire [1:0] bresp,
    output wire [31:0] awaddr, tx_wdata,
    output wire bready
);
    typedef enum logic [5:0] {CFG, CFG_WAIT, SESSION, SESSION_WAIT,
        LENGTH0, LENGTH0_WAIT, LENGTH1, LENGTH1_WAIT,
        DESC, DESC_WAIT, STATUS, STATUS_WAIT, HDR, HDR_WAIT, CHECK,
        LO, HI, PACK, SEND, RELEASE, COUNT0, COUNT1, COUNT2, POLL,
        MAC, MAC_WAIT, TXDESC, TXDESC_WAIT, TXWORD, TXOWN, TXKICK, TXRESP,
        COUNT3, COUNT4, R_INIT, R_FETCH, R_PACK, R_SEND, R_DONE, CFG_APPLY} state_t;
    state_t state;
    logic [4:0] slot;
    logic [3:0] hindex;
    logic [31:0] session_id;
    logic [13:0] desc_status;
    logic [31:0] header [0:7];
    logic [63:0] length, accepted;
    logic [31:0] packets;
    logic [10:0] payload_left, position;
    logic [31:0] low_word;
    logic replay;
    logic [17:0] replay_pos, replay_last;
    logic [31:0] config_word;
    logic [63:0] replay_left;
    wire [3:0] replay_take = replay_left >= 8 ? 4'd8 : {1'b0,replay_left[2:0]};
    // Absolute addresses and a precomputed last address avoid an add/compare/
    // mux/add chain on the high-fanout BRAM address bus.
    wire [17:0] replay_next = replay_pos == replay_last ? 18'h1000 : replay_pos + 18'd8;
    logic [31:0] mac_words [0:3];
    logic [1:0] mac_index;
    logic [3:0] tx_index;
    logic [12:0] ack_timer;
    logic [255:0] result_digest;
    logic result_done, result_error;
    logic [63:0] ack_accepted;
    logic [31:0] ack_status;
    logic [255:0] ack_digest;
    logic tx_pending, tx_complete, tx_fault;
    wire [17:0] packet_base = 18'h01000 + {2'b0, slot, 11'b0};
    wire [63:0] offset = {header[6], header[5]};
    wire [31:0] payload_size = header[7];
    wire [3:0] take = payload_left >= 8 ? 4'd8 : {1'b0,payload_left[2:0]};
    assign tlast = replay ? replay_left <= 8 : accepted + {60'b0,take} == length;
    assign awaddr = 32'he000b000;
    // MDIO enabled, RX enabled, TX enabled, start TX. No IRQs or ARM intervention.
    assign tx_wdata = 32'h0000021c;
    assign bready = 1;

    // A hash abort/DFX reset must not withdraw half of an accepted AXI write.
    // The bus transaction completes under the GLOBAL AXI reset independently
    // of resetn, which resets only hash/ingress state.
    always_ff @(posedge clk) begin
        if (!axi_resetn) begin
            awvalid <= 0; wvalid <= 0; tx_pending <= 0;
            tx_complete <= 0; tx_fault <= 0;
        end else begin
            tx_complete <= 0;
            if (awvalid && awready) awvalid <= 0;
            if (wvalid && wready) wvalid <= 0;
            if (resetn && state == TXKICK && !tx_pending) begin
                awvalid <= 1; wvalid <= 1; tx_pending <= 1;
            end
            if (bvalid && tx_pending) begin
                tx_pending <= 0; tx_complete <= 1; tx_fault <= bresp != 0;
            end
        end
    end

    always_comb begin
        en = 1; we = 0; wdata = 0; addr = 0;
        case (state)
            CFG, CFG_WAIT, POLL: addr = 18'h400;
            SESSION, SESSION_WAIT: addr = 18'h404;
            LENGTH0, LENGTH0_WAIT: addr = 18'h408;
            LENGTH1, LENGTH1_WAIT: addr = 18'h40c;
            MAC, MAC_WAIT: addr = 18'h410 + {14'b0,mac_index,2'b00};
            DESC, DESC_WAIT: addr = {10'b0,slot,3'b000};
            STATUS, STATUS_WAIT: addr = {10'b0,slot,3'b100};
            HDR, HDR_WAIT: addr = packet_base + {12'b0,hindex,2'b00};
            LO: addr = packet_base + {7'b0,position};
            HI, PACK: addr = packet_base + {7'b0,position} + 18'd4;
            RELEASE: begin
                addr = {10'b0,slot,3'b000}; we = 4'hf;
                wdata = 32'h80001000 + {16'b0,slot,11'b0} + (slot == 31 ? 32'd2 : 32'd0);
            end
            COUNT0: begin addr = 18'h500; we = 15; wdata = accepted[31:0]; end
            COUNT1: begin addr = 18'h504; we = 15; wdata = accepted[63:32]; end
            COUNT2: begin addr = 18'h508; we = 15; wdata = packets; end
            R_FETCH, R_PACK: addr = replay_pos;
            R_SEND: begin
                // Re-reading the same next word while stalled is harmless.
                // Do not route core READY through the BRAM enable/decode tree.
                en = 1;
                addr = replay_next;
            end
            COUNT4: begin addr = 18'h510; we = 15; wdata = {30'b0,result_error,result_done}; end
            COUNT3: begin addr = 18'h50c; we = 15; wdata = 32'h4e455431; end
            TXDESC, TXDESC_WAIT: addr = 18'h204;
            TXWORD: begin
                addr = 18'h800 + {12'b0,tx_index,2'b00}; we = 15;
                case (tx_index)
                    0: wdata = mac_words[0];
                    1: wdata = {mac_words[2][15:0],mac_words[1][15:0]};
                    2: wdata = {mac_words[3][15:0],mac_words[2][31:16]};
                    3: wdata = 32'h0201b588;
                    4: wdata = session_id;
                    5: wdata = ack_accepted[31:0];
                    6: wdata = ack_accepted[63:32];
                    7: wdata = ack_status;
                    default: wdata = ack_digest[{tx_index[2:0],5'b0} +: 32];
                endcase
            end
            TXOWN: begin addr = 18'h204; we = 15; wdata = 32'h40008040; end
            default: en = 0;
        endcase
    end

    always_ff @(posedge clk) begin
        if (!resetn) begin
            state <= CFG; enabled <= 0; slot <= 0; hindex <= 0;
            session_id <= 0; length <= 0; accepted <= 0; packets <= 0;
            desc_status <= 0; payload_left <= 0; position <= 0;
            low_word <= 0; tdata <= 0; tkeep <= 0; tvalid <= 0;
            replay <= 0; replay_pos <= 0; replay_left <= 0;
            replay_last <= 0; config_word <= 0;
            mac_index <= 0; tx_index <= 0; ack_timer <= 0;
            result_digest <= 0; result_done <= 0; result_error <= 0;
            ack_digest <= 0; ack_accepted <= 0; ack_status <= 0;
            for (int i=0;i<8;i=i+1) header[i] <= 0;
            for (int i=0;i<4;i=i+1) mac_words[i] <= 0;
        end else begin
        if (enabled && ack_timer < 5000) ack_timer <= ack_timer + 1;
        if (digest_valid) begin result_digest <= digest; result_done <= 1; end
        if (core_error) result_error <= 1;
        case (state)
            CFG: state <= CFG_WAIT;
            CFG_WAIT: begin config_word <= rdata; state <= CFG_APPLY; end
            CFG_APPLY: if (config_word == 32'h314e4554 || config_word == 32'h31504c52) begin
                replay <= config_word == 32'h31504c52;
                enabled <= 1; slot <= 0; accepted <= 0; packets <= 0; state <= SESSION;
            end else begin enabled <= 0; state <= CFG; end
            SESSION: state <= SESSION_WAIT;
            SESSION_WAIT: begin session_id <= rdata; state <= LENGTH0; end
            LENGTH0: state <= LENGTH0_WAIT;
            LENGTH0_WAIT: begin length[31:0] <= rdata; state <= LENGTH1; end
            LENGTH1: state <= LENGTH1_WAIT;
            LENGTH1_WAIT: begin length[63:32] <= rdata; mac_index <= 0; state <= replay ? R_INIT : MAC; end
            MAC: state <= MAC_WAIT;
            MAC_WAIT: begin
                mac_words[mac_index] <= rdata;
                if (mac_index == 3) state <= COUNT0;
                else begin mac_index <= mac_index + 1; state <= MAC; end
            end
            DESC: state <= ack_timer == 5000 ? TXDESC : DESC_WAIT;
            DESC_WAIT: state <= rdata[0] ? STATUS : POLL;
            POLL: state <= CHECK; // CHECK distinguishes polling from a parsed header below.
            STATUS: state <= STATUS_WAIT;
            STATUS_WAIT: begin desc_status <= {rdata[15:14],rdata[11:0]}; hindex <= 0; state <= HDR; end
            HDR: state <= HDR_WAIT;
            HDR_WAIT: begin
                header[hindex[2:0]] <= rdata;
                if (hindex == 7) begin hindex <= 8; state <= CHECK; end
                else begin hindex <= hindex + 1; state <= HDR; end
            end
            CHECK: if (hindex != 8) begin
                if (rdata != 32'h314e4554) begin enabled <= 0; state <= CFG; end
                else state <= DESC;
            end else begin
                hindex <= 0;
                if (desc_status[13:12] == 2'b11 && header[3] == 32'h0101b588 &&
                    header[4] == session_id && offset == accepted &&
                    payload_size > 0 && payload_size <= 1440 &&
                    {20'b0,desc_status[11:0]} == payload_size + 32'd64 &&
                    accepted <= length && {32'b0,payload_size} <= length - accepted) begin
                    payload_left <= payload_size[10:0]; position <= 64; state <= LO;
                end else state <= RELEASE;
            end
            LO: state <= HI;
            HI: begin low_word <= rdata; state <= PACK; end
            PACK: begin
                tdata <= {rdata, low_word};
                tkeep <= 8'hff >> (4'd8 - take);
                tvalid <= 1; state <= SEND;
            end
            SEND: if (tready) begin
                tvalid <= 0; accepted <= accepted + {60'b0,take};
                if (payload_left <= 8) begin packets <= packets + 1; state <= RELEASE; end
                else begin payload_left <= payload_left - 11'd8; position <= position + 11'd8; state <= LO; end
            end
            RELEASE: begin slot <= slot + 1; state <= COUNT0; end
            COUNT0: state <= COUNT1;
            COUNT1: state <= COUNT2;
            COUNT2: state <= COUNT3;
            COUNT3: state <= COUNT4;
            COUNT4: state <= replay ? R_DONE : DESC;
            R_INIT: begin
                replay_pos <= 18'h1000; replay_left <= length;
                replay_last <= 18'h0ff8 + session_id[17:0];
                if (session_id == 0 || session_id > 32'h3f000 || session_id[2:0] != 0) begin
                    result_error <= 1; state <= COUNT0;
                end else state <= length == 0 ? COUNT0 : R_FETCH;
            end
            R_FETCH: state <= R_PACK;
            R_PACK: begin
                tdata <= ram64; tkeep <= 8'hff >> (4'd8-replay_take);
                tvalid <= 1; state <= R_SEND;
            end
            R_SEND: if (tready) begin
                tvalid <= 0; accepted <= accepted + {60'b0,replay_take};
                replay_left <= replay_left - {60'b0,replay_take};
                replay_pos <= replay_next;
                // The next BRAM read starts on this handshake: two clocks/beat,
                // independent of core backpressure (400 MB/s source at 100 MHz).
                state <= replay_left <= 8 ? COUNT0 : R_PACK;
            end
            R_DONE: state <= COUNT0; // Publish final counters/status; reset aborts or selects a new source.
            TXDESC: state <= TXDESC_WAIT;
            TXDESC_WAIT: if (rdata[31]) begin
                tx_index <= 0; ack_accepted <= accepted;
                ack_status <= result_error ? 32'd2 : (result_done ? 32'd1 : 32'd0);
                ack_digest <= result_digest; state <= TXWORD;
            end else begin ack_timer <= 4900; state <= DESC; end
            TXWORD: if (tx_index == 15) state <= TXOWN;
                else tx_index <= tx_index + 1;
            TXOWN: state <= TXKICK;
            TXKICK: if (!tx_pending) state <= TXRESP;
            TXRESP: if (tx_complete) begin
                if (tx_fault) result_error <= 1;
                ack_timer <= 0; state <= DESC;
            end
            default: state <= CFG;
        endcase
        end
    end
endmodule
