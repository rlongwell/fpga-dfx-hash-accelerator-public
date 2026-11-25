// SPDX-License-Identifier: MIT
#include "Vgem_ingress.h"
#include "verilated.h"
#include <array>
#include <cstdint>
#include <iostream>
#include <random>
#include <stdexcept>
#include <vector>

static void require(bool ok, const char *s) { if (!ok) throw std::runtime_error(s); }
struct Bench {
    Vgem_ingress d;
    std::array<uint32_t,65536> ram{};
    std::vector<uint8_t> output;
    std::mt19937 rng{8713};
    uint32_t prior = 0;
    uint64_t prior64 = 0;
    uint64_t clocks = 0;
    unsigned lasts = 0;
    bool held = false, aw_seen=false, w_seen=false, response=false;
    unsigned acks=0; bool stall_aw=false, stall_w=false;
    uint64_t held_data = 0;
    unsigned held_keep = 0, held_last = 0;
    void tick() {
        d.clk=0; d.rdata=prior; d.ram64=prior64; d.tready=(rng()%5)!=0;
        d.awready=!stall_aw && (rng()%3)!=0;d.wready=!stall_w && (rng()%3)!=0;d.bvalid=response;d.bresp=0;d.eval();
        if (response && d.bready) response=false;
        if (d.awvalid && d.awready) { require(d.awaddr==0xe000b000,"wrong GEM address");aw_seen=true; }
        if (d.wvalid && d.wready) { require(d.tx_wdata==0x21c,"wrong GEM start");w_seen=true; }
        if (aw_seen && w_seen) {
            aw_seen=w_seen=false; response=true;
            require(ram[0x204/4]==0x40008040,"TX descriptor ordering");
            require(ram[0x80c/4]==0x0201b588 && ram[0x810/4]==0x12345678,"ACK header");
            require(ram[0x814/4]<=output.size(),"ACK for unaccepted data");
            ram[0x204/4]|=0x80000000;acks++;
        }
        if (held) require(d.tvalid && d.tdata==held_data && d.tkeep==held_keep && d.tlast==held_last,"unstable stalled stream");
        held=d.tvalid && !d.tready;
        held_data=d.tdata; held_keep=d.tkeep; held_last=d.tlast;
        if (d.tvalid && d.tready) {
            require(d.tkeep!=0 && (unsigned(d.tkeep)&(unsigned(d.tkeep)+1))==0,"bad keep");
            for (unsigned b=0;b<8;b++) if(d.tkeep&(1u<<b)) output.push_back(uint8_t(d.tdata>>(8*b)));
            lasts+=d.tlast;
        }
        uint32_t next=prior;
        if(d.en) {
            require((d.addr&3)==0 && d.addr<0x40000,"RAM address out of bounds");
            auto &word=ram[d.addr/4]; next=word;
            prior64=uint64_t(ram[(d.addr/4)&~1u])|(uint64_t(ram[(d.addr/4)|1u])<<32);
            for(unsigned b=0;b<4;b++) if(d.we&(1<<b)) word=(word&~(0xffu<<(8*b)))|((d.wdata>>(8*b)&255u)<<(8*b));
        }
        d.clk=1; d.eval(); prior=next; clocks++;
    }
    void reset(uint64_t size) {
        d.resetn=0; d.axi_resetn=0; d.digest_valid=0; d.core_error=0; held=false; aw_seen=w_seen=response=false; for(int i=0;i<4;i++)tick();
        ram.fill(0); output.clear(); lasts=0;
        for(unsigned i=0;i<32;i++)ram[i*2]=0x80001000+i*2048+(i==31?2:0);
        ram[0x200/4]=0x80000800;ram[0x204/4]=0xc0008040;
        ram[0x404/4]=0x12345678;ram[0x408/4]=uint32_t(size);ram[0x40c/4]=uint32_t(size>>32);
        ram[0x400/4]=0x314e4554; d.resetn=1; d.axi_resetn=1;
    }
    void frame(unsigned slot,uint64_t offset,const std::vector<uint8_t>& data,unsigned n,unsigned bad=0) {
        while(ram[slot*2]&1) tick();
        unsigned base=0x1000/4+slot*512;
        for(unsigned i=0;i<512;i++)ram[base+i]=0;
        ram[base+3]=bad==1?0x0201b588:0x0101b588;
        ram[base+4]=bad==2?0xabcdefab:0x12345678;
        ram[base+5]=uint32_t(offset);ram[base+6]=uint32_t(offset>>32);ram[base+7]=n;
        for(unsigned i=0;i<n;i++) ram[base+16+i/4]|=uint32_t(data.at((offset+i)%data.size()))<<(8*(i%4));
        ram[slot*2+1]=(bad==3?0x4000:0xc000)|(n+64+(bad==4?1:0));
        ram[slot*2]|=1;
    }
};
int main(int argc,char**argv) {
    Verilated::commandArgs(argc,argv);
    try {
        Bench b;
        for(unsigned size:{1u,7u,8u,9u,135u,136u,137u,1440u,1441u,100003u}) {
            std::vector<uint8_t> data(size); for(auto &x:data)x=uint8_t(b.rng());
            b.reset(size); unsigned slot=0,offset=0;
            // Header/version/session, incomplete descriptor, length mismatch, reordered packet.
            for(unsigned bad=1;bad<=4;bad++) { b.frame(slot++,0,data,1,bad); }
            b.frame(slot++,size+7,data,1);
            while(offset<size) {
                unsigned n=std::min(size-offset,1+unsigned(b.rng()%1440u));
                b.frame(slot++%32,offset,data,n);
                if(offset!=0 && (b.rng()%4)==0)b.frame(slot++%32,0,data,1); // Duplicate.
                offset+=n;
            }
            uint64_t limit=b.clocks+size*12+20000;
            while(b.output.size()<size && b.clocks<limit)b.tick();
            for(unsigned i=0;i<8;i++) b.d.digest[i]=0x12340000+i;
            b.d.digest_valid=1;b.tick();b.d.digest_valid=0;
            for(unsigned i=0;i<6000;i++)b.tick();
            require(b.ram[0x81c/4]==1 && b.ram[0x820/4]==0x12340000,"final digest ACK");
            require(b.output==data,"payload bytes mismatch / timeout");require(b.lasts==1,"incorrect final framing");
            require(b.ram[0x500/4]==size,"published byte count mismatch");
            b.ram[0x400/4]=0;for(int i=0;i<30;i++)b.tick();require(!b.d.enabled,"disable failed");
            std::cout<<"PASS length="<<size<<"\n";
        }
        // A reset in the middle of a blocked transfer must clear the stream/ring state.
        b.reset(1024);std::vector<uint8_t> data(1024,0xa7);b.frame(0,0,data,1024);
        for(int i=0;i<100;i++)b.tick();b.reset(1);b.frame(0,0,data,1);
        for(int i=0;i<200;i++)b.tick();require(b.output==std::vector<uint8_t>{0xa7},"reset recovery failed");
        for(unsigned pattern:{8u,136u,131072u,258048u}) {
            for(unsigned size:{0u,1u,7u,8u,137u,270123u}) {
                b.reset(size);b.ram[0x400/4]=0x31504c52;b.ram[0x404/4]=pattern;
                std::vector<uint8_t> expected;
                for(unsigned i=0;i<pattern;i++) {
                    uint8_t v=uint8_t(i*131u+(i>>8));
                    unsigned &word=b.ram[0x1000/4+i/4];
                    word=(word&~(255u<<(8*(i%4))))|(unsigned(v)<<(8*(i%4)));
                }
                for(unsigned i=0;i<size;i++) {
                    unsigned j=i%pattern;expected.push_back(uint8_t(j*131u+(j>>8)));
                }
                uint64_t limit=b.clocks+size*5+1000;
                while(b.output.size()<size && b.clocks<limit)b.tick();
                for(int i=0;i<100;i++)b.tick();
                require(b.output==expected,"replay bytes / wrap mismatch");
                require(b.lasts==(size?1u:0u),"replay last mismatch");
                require(b.ram[0x500/4]==size,"replay count mismatch");
            }
            std::cout<<"PASS replay pattern="<<pattern<<"\n";
        }
        b.reset(0);b.stall_w=true;
        for(unsigned i=0;i<10000 && !b.aw_seen;i++)b.tick();
        require(b.aw_seen && b.d.wvalid,"failed to hold half a write");
        b.d.resetn=0;b.held=false;
        for(unsigned i=0;i<8;i++)b.tick();
        require(b.d.wvalid,"hash reset withdrew pending AXI data");
        b.stall_w=false;for(unsigned i=0;i<100;i++)b.tick();
        require(!b.d.wvalid && !b.d.awvalid && !b.aw_seen && !b.w_seen,"AXI abort completion failed");
        std::cout<<"PASS independent AXI completion after hash abort\n";
        std::cout<<"PASS reset recovery; direct GEM ingress simulation\n";
    } catch(const std::exception&e) { std::cerr<<e.what()<<"\n";return 1; }
}
