// SPDX-License-Identifier: MIT
// Original RFC 7693 BLAKE2s-256 RTL: unkeyed, fanout=1, depth=1.
// Four parallel G functions, each divided into four clocked steps.
module hash_blake2s (
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
    typedef enum logic [2:0] {IDLE,FILL,PREP,RUN,COMMIT,HOLD,FAILED} state_t;
    state_t state;
    logic [31:0] h [0:7], m [0:15], v [0:15];
    logic [31:0] mix_a [0:3], mix_c [0:3];
    logic [63:0] byte_count;
    logic [5:0] position;
    logic [3:0] round_index;
    logic [1:0] substep;
    logic diagonal, final_block;
    logic accepted_start, byte_valid, byte_ready, byte_last, stream_error;
    logic [7:0] byte_data;

    localparam logic [31:0] IV [0:7] = '{
        32'h6a09e667,32'hbb67ae85,32'h3c6ef372,32'ha54ff53a,
        32'h510e527f,32'h9b05688c,32'h1f83d9ab,32'h5be0cd19
    };
    localparam logic [3:0] SIGMA [0:9][0:15] = '{
        '{0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15},
        '{14,10,4,8,9,15,13,6,1,12,0,2,11,7,5,3},
        '{11,8,12,0,5,2,15,13,10,14,3,6,7,1,9,4},
        '{7,9,3,1,13,12,11,14,2,6,5,10,4,0,15,8},
        '{9,0,5,7,2,4,10,15,14,1,11,12,6,8,3,13},
        '{2,12,6,10,0,11,8,3,4,13,7,5,15,14,1,9},
        '{12,5,1,15,14,13,4,10,0,7,6,3,9,2,8,11},
        '{13,11,7,14,12,1,3,9,5,0,15,4,8,6,2,10},
        '{6,15,14,9,11,3,0,8,12,2,13,7,1,4,10,5},
        '{10,2,8,4,7,6,1,5,15,11,9,14,3,12,13,0}
    };
    function automatic logic [31:0] ror32(input logic [31:0] value,input int n);
        return (value >> n) | (value << (32-n));
    endfunction
    always_comb begin
        for(int i=0;i<4;i++) begin
            mix_a[i] = v[i] + v[4+(i+(diagonal ? 1:0))%4] +
                m[SIGMA[round_index][2*(i+(diagonal ? 4:0))+(substep==2 ? 1:0)]];
            mix_c[i] = v[8+(i+(diagonal ? 2:0))%4] + v[12+(i+(diagonal ? 3:0))%4];
        end
    end
    assign accepted_start = aresetn && start && (state==IDLE || state==FAILED);
    assign byte_ready = aresetn && state==FILL && !stream_error;
    assign algorithm_id = 32'd3;
    assign error = stream_error || state==FAILED;
    assign busy = state!=IDLE && state!=HOLD && state!=FAILED;
    assign digest_valid = aresetn && state==HOLD;
    for(genvar i=0;i<8;i++) begin : digest_words
        assign digest[32*i +:32] = h[i];
    end
    axis_bytes input_buffer (
        .aclk,.aresetn,.start(accepted_start),.message_length,
        .s_axis_tdata,.s_axis_tkeep,.s_axis_tvalid,.s_axis_tlast,.s_axis_tready,
        .byte_data,.byte_valid,.byte_last,.byte_ready,.error(stream_error)
    );

    always_ff @(posedge aclk) begin
        if(!aresetn) begin
            state<=IDLE;byte_count<=0;position<=0;round_index<=0;
            substep<=0;diagonal<=0;final_block<=0;
            for(int i=0;i<8;i++) h[i]<=0;
            for(int i=0;i<16;i++) begin m[i]<=0;v[i]<=0;end
        end else if(accepted_start) begin
            state<=message_length==0 ? PREP : FILL;
            byte_count<=0;position<=0;round_index<=0;
            substep<=0;diagonal<=0;final_block<=message_length==0;
            // Parameter block: digest length 32, key length 0, fanout/depth 1.
            h[0]<=IV[0]^32'h01010020;
            for(int i=1;i<8;i++) h[i]<=IV[i];
            for(int i=0;i<16;i++) m[i]<=0;
        end else if(stream_error) begin
            state<=FAILED;
        end else begin
            case(state)
                FILL: if(byte_valid && byte_ready) begin
                    m[position[5:2]][8*position[1:0] +:8]<=byte_data;
                    byte_count<=byte_count+1'b1;
                    if(byte_last || position==63) begin
                        final_block<=byte_last;state<=PREP;position<=0;
                    end else position<=position+1'b1;
                end
                PREP: begin
                    for(int i=0;i<8;i++) v[i]<=h[i];
                    for(int i=0;i<4;i++) v[i+8]<=IV[i];
                    v[12]<=IV[4]^byte_count[31:0];v[13]<=IV[5]^byte_count[63:32];
                    v[14]<=final_block ? ~IV[6] : IV[6];v[15]<=IV[7];
                    round_index<=0;substep<=0;diagonal<=0;state<=RUN;
                end
                RUN: begin
                    for(int i=0;i<4;i++) begin
                        case(substep)
                            0,2: begin
                                v[i]<=mix_a[i];
                                v[12+(i+(diagonal ? 3:0))%4] <=
                                    ror32(v[12+(i+(diagonal ? 3:0))%4]^mix_a[i],substep==0 ? 16:8);
                            end
                            1,3: begin
                                v[8+(i+(diagonal ? 2:0))%4]<=mix_c[i];
                                v[4+(i+(diagonal ? 1:0))%4] <=
                                    ror32(v[4+(i+(diagonal ? 1:0))%4]^mix_c[i],substep==1 ? 12:7);
                            end
                        endcase
                    end
                    if(substep==3) begin
                        substep<=0;diagonal<=!diagonal;
                        if(diagonal) begin
                            if(round_index==9) state<=COMMIT;
                            else round_index<=round_index+1'b1;
                        end
                    end else substep<=substep+1'b1;
                end
                COMMIT: begin
                    for(int i=0;i<8;i++) h[i]<=h[i]^v[i]^v[i+8];
                    for(int i=0;i<16;i++) m[i]<=0;
                    state<=final_block ? HOLD : FILL;
                end
                HOLD: if(digest_ready) state<=IDLE;
                default: ;
            endcase
        end
    end
endmodule
