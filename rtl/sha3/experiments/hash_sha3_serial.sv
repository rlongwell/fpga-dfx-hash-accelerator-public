// SPDX-License-Identifier: MIT
// Original SHA3-256 RTL implementing FIPS 202. This is not the Oxide baseline.
// Area experiment: parity, 25 lane rho/pi cycles, and five chi rows per round.
// Digest is a view of the held state: there is no separate digest register.
module hash_sha3_serial (
    input  logic aclk, aresetn, start,
    input  logic [63:0] message_length,
    input  logic [63:0] s_axis_tdata,
    input  logic [7:0] s_axis_tkeep,
    input  logic s_axis_tvalid, s_axis_tlast,
    output logic s_axis_tready,
    output logic [255:0] digest,
    output logic digest_valid,
    input  logic digest_ready,
    output logic busy,
    output logic [31:0] algorithm_id,
    output logic error
);
    typedef enum logic [3:0] {IDLE, ABSORB, PAD, PARITY, RHO_PI, CHI, HOLD, FAILED} state_t;
    state_t state;
    logic [63:0] lanes [0:24];
    logic [63:0] intermediate [0:24];
    logic [63:0] parity [0:4];
    logic [4:0] lane_index;
    logic [2:0] column_index, row_index;
    logic [63:0] selected_lane, transformed_lane;
    localparam int DEST [0:24] = '{
         0,10,20,5,15,16,1,11,21,6,7,17,2,12,22,23,8,18,3,13,14,24,9,19,4
    };
    logic [7:0] position;
    logic [4:0] round_index;
    logic final_permutation, pad_after_permutation;
    logic accepted_start, byte_valid, byte_ready, byte_last, stream_error;
    logic [7:0] byte_data;

    localparam logic [63:0] RC [0:23] = '{
        64'h0000000000000001, 64'h0000000000008082,
        64'h800000000000808a, 64'h8000000080008000,
        64'h000000000000808b, 64'h0000000080000001,
        64'h8000000080008081, 64'h8000000000008009,
        64'h000000000000008a, 64'h0000000000000088,
        64'h0000000080008009, 64'h000000008000000a,
        64'h000000008000808b, 64'h800000000000008b,
        64'h8000000000008089, 64'h8000000000008003,
        64'h8000000000008002, 64'h8000000000000080,
        64'h000000000000800a, 64'h800000008000000a,
        64'h8000000080008081, 64'h8000000000008080,
        64'h0000000080000001, 64'h8000000080008008
    };
    // Index x+5*y follows the FIPS 202 state mapping.
    localparam int RHO [0:24] = '{
         0, 1,62,28,27, 36,44, 6,55,20, 3,10,43,25,39,
        41,45,15,21, 8, 18, 2,61,56,14
    };
    function automatic logic [63:0] rol64(input logic [63:0] value, input int n);
        return (value << n) | (value >> ((64-n) % 64));
    endfunction

    assign selected_lane = lanes[lane_index] ^ parity[(int'(column_index)+4)%5] ^
        rol64(parity[(int'(column_index)+1)%5],1);
    assign transformed_lane = rol64(selected_lane,RHO[lane_index]);

    assign accepted_start = aresetn && start && (state == IDLE || state == FAILED);
    assign byte_ready = aresetn && (state == ABSORB) && !stream_error;
    assign algorithm_id = 32'd1;
    assign error = stream_error || (state == FAILED);
    assign busy = (state != IDLE && state != HOLD && state != FAILED);
    assign digest_valid = aresetn && (state == HOLD);
    for (genvar i=0; i<4; i++) begin : digest_lanes
        assign digest[64*i +: 64] = lanes[i];
    end

    axis_bytes input_buffer (
        .aclk, .aresetn, .start(accepted_start), .message_length,
        .s_axis_tdata, .s_axis_tkeep, .s_axis_tvalid, .s_axis_tlast, .s_axis_tready,
        .byte_data, .byte_valid, .byte_last, .byte_ready, .error(stream_error)
    );

    always_ff @(posedge aclk) begin
        if (!aresetn) begin
            state <= IDLE; position <= 0; round_index <= 0;
            lane_index <= 0; column_index <= 0; row_index <= 0;
            for (int i=0; i<5; i++) parity[i] <= 0;
            for (int i=0; i<25; i++) intermediate[i] <= 0;
            final_permutation <= 0; pad_after_permutation <= 0;
            for (int i=0; i<25; i++) lanes[i] <= 0;
        end else if (accepted_start) begin
            state <= (message_length == 0) ? PAD : ABSORB;
            position <= 0; round_index <= 0;
            final_permutation <= 0; pad_after_permutation <= 0;
            for (int i=0; i<25; i++) lanes[i] <= 0;
        end else if (stream_error) begin
            state <= FAILED;
        end else begin
            case (state)
                ABSORB: if (byte_valid && byte_ready) begin
                    lanes[position[7:3]][8*position[2:0] +: 8] <=
                        lanes[position[7:3]][8*position[2:0] +: 8] ^ byte_data;
                    if (position == 135) begin
                        position <= 0; round_index <= 0;
                        final_permutation <= 0;
                        pad_after_permutation <= byte_last;
                        state <= PARITY;
                    end else begin
                        position <= position + 1'b1;
                        if (byte_last) state <= PAD;
                    end
                end
                PAD: begin
                    // SHA3 domain 01 followed by pad10*1, in LSB-first bytes.
                    if (position == 135) begin
                        lanes[16][63:56] <= lanes[16][63:56] ^ 8'h86;
                    end else begin
                        lanes[position[7:3]][8*position[2:0] +: 8] <=
                            lanes[position[7:3]][8*position[2:0] +: 8] ^ 8'h06;
                        lanes[16][63:56] <= lanes[16][63:56] ^ 8'h80;
                    end
                    final_permutation <= 1;
                    round_index <= 0;
                    state <= PARITY;
                end
                PARITY: begin
                    for (int x=0; x<5; x++) begin
                        parity[x] <= lanes[x] ^ lanes[x+5] ^ lanes[x+10] ^ lanes[x+15] ^ lanes[x+20];
                    end
                    lane_index <= 0; column_index <= 0; state <= RHO_PI;
                end
                RHO_PI: begin
                    intermediate[DEST[lane_index]] <= transformed_lane;
                    if (lane_index == 24) begin
                        row_index <= 0; state <= CHI;
                    end else begin
                        lane_index <= lane_index + 1'b1;
                        column_index <= (column_index == 4) ? 3'd0 : column_index + 1'b1;
                    end
                end
                CHI: begin
                    for (int x=0; x<5; x++) begin
                        lanes[5*int'(row_index)+x] <= intermediate[5*int'(row_index)+x] ^
                            ((~intermediate[5*int'(row_index)+(x+1)%5]) &
                              intermediate[5*int'(row_index)+(x+2)%5]) ^
                            ((row_index == 0 && x == 0) ? RC[round_index] : 64'd0);
                    end
                    if (row_index == 4) begin
                        if (round_index == 23) begin
                            round_index <= 0;
                            if (final_permutation) state <= HOLD;
                            else if (pad_after_permutation) state <= PAD;
                            else state <= ABSORB;
                        end else begin round_index <= round_index + 1'b1; state <= PARITY; end
                    end else row_index <= row_index + 1'b1;
                end
                HOLD: if (digest_ready) state <= IDLE;
                default: ;
            endcase
        end
    end
endmodule
