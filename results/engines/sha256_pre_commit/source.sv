// SPDX-License-Identifier: MIT
// Original SHA-256 RTL, FIPS 180-4. One compression round per cycle.
module hash_sha256 (
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
    typedef enum logic [3:0] {IDLE,FILL,PAD_MARK,PAD_ZERO,PREP,RUN,HOLD,FAILED} state_t;
    state_t state, resume_state;
    logic [31:0] h [0:7], w [0:15];
    logic [31:0] a,b,c,d,e,f,g,z;
    logic [31:0] t1,t2,next_word;
    logic [63:0] bit_length;
    logic [5:0] position, round_index;
    logic final_block, accepted_start, byte_valid, byte_ready, byte_last;
    logic stream_error, buffer_ready, stream_enabled;
    logic [7:0] byte_data;

    localparam logic [31:0] IV [0:7] = '{
        32'h6a09e667,32'hbb67ae85,32'h3c6ef372,32'ha54ff53a,
        32'h510e527f,32'h9b05688c,32'h1f83d9ab,32'h5be0cd19
    };
    localparam logic [31:0] K [0:63] = '{
        32'h428a2f98,32'h71374491,32'hb5c0fbcf,32'he9b5dba5,
        32'h3956c25b,32'h59f111f1,32'h923f82a4,32'hab1c5ed5,
        32'hd807aa98,32'h12835b01,32'h243185be,32'h550c7dc3,
        32'h72be5d74,32'h80deb1fe,32'h9bdc06a7,32'hc19bf174,
        32'he49b69c1,32'hefbe4786,32'h0fc19dc6,32'h240ca1cc,
        32'h2de92c6f,32'h4a7484aa,32'h5cb0a9dc,32'h76f988da,
        32'h983e5152,32'ha831c66d,32'hb00327c8,32'hbf597fc7,
        32'hc6e00bf3,32'hd5a79147,32'h06ca6351,32'h14292967,
        32'h27b70a85,32'h2e1b2138,32'h4d2c6dfc,32'h53380d13,
        32'h650a7354,32'h766a0abb,32'h81c2c92e,32'h92722c85,
        32'ha2bfe8a1,32'ha81a664b,32'hc24b8b70,32'hc76c51a3,
        32'hd192e819,32'hd6990624,32'hf40e3585,32'h106aa070,
        32'h19a4c116,32'h1e376c08,32'h2748774c,32'h34b0bcb5,
        32'h391c0cb3,32'h4ed8aa4a,32'h5b9cca4f,32'h682e6ff3,
        32'h748f82ee,32'h78a5636f,32'h84c87814,32'h8cc70208,
        32'h90befffa,32'ha4506ceb,32'hbef9a3f7,32'hc67178f2
    };
    function automatic logic [31:0] ror32(input logic [31:0] v,input int n);
        return (v >> n) | (v << (32-n));
    endfunction
    always_comb begin
        t1 = z + (ror32(e,6)^ror32(e,11)^ror32(e,25)) +
             ((e&f)^((~e)&g)) + K[round_index] + w[0];
        t2 = (ror32(a,2)^ror32(a,13)^ror32(a,22)) + ((a&b)^(a&c)^(b&c));
        next_word = (ror32(w[14],17)^ror32(w[14],19)^(w[14]>>10)) +
                    w[9] + (ror32(w[1],7)^ror32(w[1],18)^(w[1]>>3)) + w[0];
    end

    assign accepted_start = aresetn && start && (state==IDLE || state==FAILED);
    assign stream_enabled = aresetn && state!=IDLE && state!=HOLD && state!=FAILED;
    assign s_axis_tready = buffer_ready && stream_enabled;
    assign byte_ready = aresetn && state==FILL && !stream_error;
    assign algorithm_id = 32'd2;
    assign error = stream_error || state==FAILED;
    assign busy = state!=IDLE && state!=HOLD && state!=FAILED;
    assign digest_valid = aresetn && state==HOLD;
    for (genvar i=0;i<8;i++) begin : digest_words
        assign digest[32*i +:32] = {h[i][7:0],h[i][15:8],h[i][23:16],h[i][31:24]};
    end
    axis_bytes input_buffer (
        .aclk,.aresetn,.start(accepted_start),.message_length,
        .s_axis_tdata,.s_axis_tkeep,.s_axis_tvalid(s_axis_tvalid && stream_enabled),
        .s_axis_tlast,.s_axis_tready(buffer_ready),
        .byte_data,.byte_valid,.byte_last,.byte_ready,.error(stream_error)
    );

    always_ff @(posedge aclk) begin
        if (!aresetn) begin
            state<=IDLE;resume_state<=FILL;position<=0;round_index<=0;
            bit_length<=0;final_block<=0;
            a<=0;b<=0;c<=0;d<=0;e<=0;f<=0;g<=0;z<=0;
            for(int i=0;i<8;i++) h[i]<=0;
            for(int i=0;i<16;i++) w[i]<=0;
        end else if (accepted_start) begin
            state <= (message_length[63:61]!=0) ? FAILED :
                     (message_length==0 ? PAD_MARK : FILL);
            resume_state<=FILL;position<=0;round_index<=0;
            bit_length<=message_length<<3;final_block<=0;
            for(int i=0;i<8;i++) h[i]<=IV[i];
            for(int i=0;i<16;i++) w[i]<=0;
        end else if (stream_error) begin
            state<=FAILED;
        end else begin
            case(state)
                FILL: if(byte_valid && byte_ready) begin
                    w[position[5:2]][8*(3-int'(position[1:0])) +:8] <= byte_data;
                    if(position==63) begin
                        position<=0;final_block<=0;state<=PREP;
                        resume_state<=byte_last ? PAD_MARK : FILL;
                    end else begin
                        position<=position+1'b1;
                        if(byte_last) state<=PAD_MARK;
                    end
                end
                PAD_MARK: begin
                    w[position[5:2]][8*(3-int'(position[1:0])) +:8] <= 8'h80;
                    if(position==63) begin
                        position<=0;final_block<=0;resume_state<=PAD_ZERO;state<=PREP;
                    end else begin position<=position+1'b1;state<=PAD_ZERO;end
                end
                PAD_ZERO: begin
                    if(position==56) begin
                        w[14]<=bit_length[63:32];w[15]<=bit_length[31:0];
                        final_block<=1;position<=0;state<=PREP;
                    end else begin
                        w[position[5:2]][8*(3-int'(position[1:0])) +:8] <= 0;
                        if(position==63) begin
                            position<=0;final_block<=0;resume_state<=PAD_ZERO;state<=PREP;
                        end else position<=position+1'b1;
                    end
                end
                PREP: begin
                    a<=h[0];b<=h[1];c<=h[2];d<=h[3];e<=h[4];f<=h[5];g<=h[6];z<=h[7];
                    round_index<=0;state<=RUN;
                end
                RUN: begin
                    a<=t1+t2;b<=a;c<=b;d<=c;e<=d+t1;f<=e;g<=f;z<=g;
                    for(int i=0;i<15;i++) w[i]<=w[i+1];
                    w[15]<=next_word;
                    if(round_index==63) begin
                        h[0]<=h[0]+t1+t2;h[1]<=h[1]+a;h[2]<=h[2]+b;h[3]<=h[3]+c;
                        h[4]<=h[4]+d+t1;h[5]<=h[5]+e;h[6]<=h[6]+f;h[7]<=h[7]+g;
                        state<=final_block ? HOLD : resume_state;
                    end else round_index<=round_index+1'b1;
                end
                HOLD: if(digest_ready) state<=IDLE;
                default: ;
            endcase
        end
    end
endmodule
