// SPDX-License-Identifier: MIT
// Exercise the GENERATED memory netlist, including every byte-write enable.
// The ingress-only RAM model cannot detect a disconnected IP byte lane.
`timescale 1ns/1ps
module bram_lane_test;
`ifdef LEGACY_BRAM_A32
    localparam A_WIDTH=32;
`else
    localparam A_WIDTH=64;
`endif
    reg clk=0;
    always #5 clk=~clk;
    reg rst=1, ena=0, enb=0;
    reg [A_WIDTH/8-1:0] wea=0;
    reg [7:0] web=0;
    reg [31:0] addra=0, addrb=0;
    reg [A_WIDTH-1:0] dina=0;
    reg [63:0] dinb=0;
    wire [A_WIDTH-1:0] douta;
    wire [63:0] doutb;
    ps_dma_net_memory_0 memory (
        .clka(clk),.rsta(rst),.ena(ena),.wea(wea),.addra(addra),.dina(dina),.douta(douta),
        .clkb(clk),.rstb(rst),.enb(enb),.web(web),.addrb(addrb),.dinb(dinb),.doutb(doutb),
        .rsta_busy(),.rstb_busy()
    );
    task write_a(input [31:0] address, value);
        @(negedge clk); ena=1;addra=address;
        wea=(A_WIDTH==64 && address[2]) ? 'hf0 : 'h0f;
        dina=(A_WIDTH==64 && address[2]) ? {value,32'b0} : {32'b0,value};
        @(negedge clk); ena=0;wea=0;
    endtask
    task check_a(input [31:0] address, value);
        @(negedge clk); ena=1;addra=address;
        @(posedge clk); #1;
        if((A_WIDTH==64 && address[2] ? (douta>>32) : (douta&'hffffffff)) !== A_WIDTH'(value))
            $fatal(1,"A address %h expected %h got %h",address,value,douta);
        @(negedge clk); ena=0;
    endtask
    task check_b(input [31:0] address,input [63:0] value);
        @(negedge clk); enb=1;addrb=address;
        @(posedge clk); #1;
        if(doutb !== value) $fatal(1,"B address %h expected %h got %h",address,value,doutb);
        @(negedge clk); enb=0;
    endtask
    task write_b(input [31:0] address,input [7:0] mask,input [63:0] value);
        @(negedge clk); enb=1;addrb=address;web=mask;dinb=value;
        @(negedge clk); enb=0;web=0;
    endtask
    reg [31:0] base;
    reg [63:0] expected;
    initial begin
        #150; @(negedge clk);rst=0;
        repeat(8) @(negedge clk);
        for(integer sample=0;sample<5;sample=sample+1) begin
            case(sample)
                0:base=0; 1:base='h200; 2:base='h800; 3:base='h1000; 4:base='h3fff8;
            endcase
            expected=64'h8877665544332211;
            write_a(base,expected[31:0]);write_a(base+4,expected[63:32]);
            check_b(base,expected);
            for(integer lane=0;lane<8;lane=lane+1) begin
                expected[lane*8+:8]=8'ha0+lane;
                // Same address/lane selection as net_system_top: bit 2 picks
                // the high word, while the RAM addresses whole 64-bit rows.
                write_b(base+(lane>=4?4:0),8'b1<<lane,expected);
                check_a(base,expected[31:0]);check_a(base+4,expected[63:32]);
            end
            write_b(base,8'hff,64'h0123456789abcdef);
            check_a(base,32'h89abcdef);check_a(base+4,32'h01234567);
        end
        $display("GENERATED_BRAM_LANES_PASS all eight lanes, cross-port readback, full memory bounds");
        $finish;
    end
    initial begin #100000; $fatal(1,"BRAM lane test timeout"); end
endmodule
