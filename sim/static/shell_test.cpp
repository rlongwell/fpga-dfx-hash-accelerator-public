// SPDX-License-Identifier: MIT
#ifdef REAL_ENGINE
#include "Vhash_integration.h"
using Device = Vhash_integration;
#else
#include "Vhash_shell.h"
using Device = Vhash_shell;
#endif
#include "verilated.h"
#include <cstdint>
#include <iostream>
#include <fstream>
#include <random>
#include <stdexcept>
#include <vector>

static void require(bool ok, const char *why) { if (!ok) throw std::runtime_error(why); }

struct Simulation {
    Device d;
    std::mt19937 rng{0x6817};
    bool model_busy=false, model_valid=false, hostile=false;
    uint64_t model_length=0, cycles=0;
    unsigned delay=0;
    std::vector<uint8_t> received;
    struct Edges { bool aw,w,b,ar,r,stream; } edge{};

    void tick() {
        d.aclk=0;
#ifndef REAL_ENGINE
        d.rp_tready=hostile || (model_busy && !model_valid && (rng()%4 != 0));
        d.rp_busy=hostile || model_busy;
        d.rp_digest_valid=hostile || model_valid;
        d.rp_error=hostile;
        d.rp_algorithm_id=hostile ? 0xffffffff : 1;
        for (int i=0;i<8;i++) d.rp_digest[i]=0x98765400U+i;
#endif
        d.eval();
        edge={bool(d.s_axi_awvalid&&d.s_axi_awready),bool(d.s_axi_wvalid&&d.s_axi_wready),
              bool(d.s_axi_bvalid&&d.s_axi_bready),bool(d.s_axi_arvalid&&d.s_axi_arready),
              bool(d.s_axi_rvalid&&d.s_axi_rready),bool(d.s_axis_tvalid&&d.s_axis_tready)};
        const bool reset=!d.rp_resetn, start=d.rp_start;
        const bool take=d.rp_tvalid&&d.rp_tready, consume=d.rp_digest_valid&&d.rp_digest_ready;
        const auto data=d.rp_tdata; const auto keep=d.rp_tkeep;
        const bool last=d.rp_tlast; const auto length=d.rp_message_length;
        if (reset) {
            require(!d.rp_start && !d.rp_tvalid && !d.rp_digest_ready && !d.s_axis_tready,
                    "isolation handshake leakage");
            require(d.rp_tdata==0 && d.rp_tkeep==0 && d.rp_message_length==0,
                    "isolation data leakage");
        }
        d.aclk=1; d.eval(); ++cycles;
        if (reset) { model_busy=false; model_valid=false; delay=0; }
        else if (start) {
            require(!model_busy&&!model_valid,"start while engine occupied");
            received.clear(); model_length=length; model_busy=true;
            delay=length==0 ? 3 : 0;
        } else {
            if (take) {
                for (int i=0;i<8;i++) if (keep&(1U<<i)) received.push_back((data>>(i*8))&255);
                require(last==(received.size()==model_length),"RP TLAST did not match file end");
                if (last) delay=3;
            }
            if (delay && --delay==0) model_valid=true;
            if (consume) { model_busy=false; model_valid=false; }
        }
        require(cycles<50000000,"watchdog");
    }
    void wait(unsigned n=1) { while(n--) tick(); }
    void reset() {
        d.aresetn=0; d.s_axi_awvalid=0; d.s_axi_wvalid=0; d.s_axi_bready=0;
        d.s_axi_arvalid=0; d.s_axi_rready=0; d.s_axis_tvalid=0;
        wait(5); d.aresetn=1; wait(3);
    }
    void write(uint32_t address,uint32_t value,uint8_t strobes=15,uint8_t expect=0) {
        d.s_axi_awaddr=address; d.s_axi_wdata=value; d.s_axi_wstrb=strobes;
        unsigned awdelay=rng()%5,wdelay=rng()%5;
        bool aw=false,w=false;
        for(unsigned t=0; !(aw&&w); t++) {
            require(t<100,"AXIL write handshake timeout");
            d.s_axi_awvalid=!aw && t>=awdelay; d.s_axi_wvalid=!w && t>=wdelay;
            tick(); aw|=edge.aw; w|=edge.w;
        }
        d.s_axi_awvalid=0; d.s_axi_wvalid=0;
        for(int n=0;!d.s_axi_bvalid;n++) {require(n<100,"AXIL response timeout");tick();}
        require(d.s_axi_bresp==expect,"unexpected AXIL write response");
        wait(3); require(d.s_axi_bvalid&&d.s_axi_bresp==expect,"write response not held");
        d.s_axi_bready=1; tick(); d.s_axi_bready=0;
    }
    uint32_t read(uint32_t address,uint8_t expect=0) {
        d.s_axi_araddr=address; d.s_axi_arvalid=1;
        for(int n=0;;n++) {require(n<100,"AXIL read timeout");tick(); if(edge.ar) break;}
        d.s_axi_arvalid=0;
        for(int n=0;!d.s_axi_rvalid;n++) {require(n<100,"AXIL read response timeout");tick();}
        const uint32_t value=d.s_axi_rdata;
        require(d.s_axi_rresp==expect,"unexpected AXIL read response");
        wait(3);
        require(d.s_axi_rvalid&&d.s_axi_rdata==value&&d.s_axi_rresp==expect,"read response not held");
        d.s_axi_rready=1; tick(); d.s_axi_rready=0;
        return value;
    }
    void start(uint64_t length) {
        write(0x10,uint32_t(length)); write(0x14,uint32_t(length>>32)); write(0,1);
    }
    void beat(uint64_t data,uint8_t keep,bool chunk_last) {
        d.s_axis_tdata=data; d.s_axis_tkeep=keep; d.s_axis_tlast=chunk_last;
        wait(rng()%3); d.s_axis_tvalid=1;
        for(int n=0;;n++) {require(n<1000,"stream timeout");tick();if(edge.stream) break;}
        d.s_axis_tvalid=0;
    }
    void send(const std::vector<uint8_t>& bytes) {
        size_t offset=0;
        while(offset<bytes.size()) {
            size_t chunk=std::min<size_t>(1+rng()%29,bytes.size()-offset);
            while(chunk) {
                unsigned count=std::min<size_t>(8,chunk); uint64_t word=0;
                for(unsigned b=0;b<count;b++) word|=uint64_t(bytes[offset+b])<<(8*b);
                beat(word,(1U<<count)-1,count==chunk); offset+=count; chunk-=count;
            }
        }
    }
    void check_done(const std::vector<uint8_t>& bytes, const std::string& expected="") {
        for(int n=0;!(read(4)&2);n++) require(n<100,"hash result timeout");
        require(!(read(4)&5),"unexpected busy or error after result");
        require(received==bytes,"dropped, duplicated or reordered byte");
        require(read(0x18)==bytes.size(),"incorrect accepted byte count");
        for(int i=0;i<8;i++) {
            uint32_t word=0x98765400U+unsigned(i);
            if (!expected.empty()) {
                word=0;
                for(int j=0;j<4;j++) word|=uint32_t(std::stoul(expected.substr((i*4+j)*2,2),nullptr,16))<<(8*j);
            }
            require(read(0x20+4*i)==word,"digest readback mismatch");
        }
        require(read(0x40)>0,"cycle counter did not run");
        require(d.irq,"completion did not assert IRQ");
    }
};

int main(int argc,char** argv) {
    Verilated::commandArgs(argc,argv);
    try {
        Simulation s; s.reset();
        s.hostile=true; s.wait(10);
        require(s.read(4)==8 && s.read(8)==0,"RP status leaked through isolation");
        require(!s.d.irq,"isolated hostile RP set interrupt");
        s.hostile=false; s.write(0,0); s.wait(8);
        require(s.read(4)&16,"engine did not become ready");
        const uint32_t algorithm_id=s.read(8);
        require(algorithm_id!=0,"ready engine has no algorithm ID");
        require(s.read(0xc)==0x10000,"ABI version mismatch");
        s.write(0x10,0x11223344); s.write(0x10,0xffaaffbb,5);
        require(s.read(0x10)==0x11aa33bb,"WSTRB ignored");
        s.read(3,2); s.read(0x80,2); s.write(0x20,123,15,2);
        unsigned cases=0, recovery_cases=0;
        std::vector<uint8_t> recovery_data(257,42);
        std::string recovery_digest;
#ifdef REAL_ENGINE
        require(argc==2,"expected hashlib vector file argument");
        std::ifstream vectors(argv[1]); require(bool(vectors),"cannot open vectors");
        std::string name,hex,expected; unsigned length;
        while(vectors>>name>>length>>hex>>expected) {
            std::vector<uint8_t> data(length);
            for(unsigned i=0;i<length;i++) data[i]=std::stoul(hex.substr(i*2,2),nullptr,16);
            s.start(length); s.send(data); s.check_done(data,expected); ++cases;
            if(name=="random_257") { recovery_data=data; recovery_digest=expected; }
        }
        require(cases>=40,"missing test vectors");
        require(recovery_digest.size()==64,"missing hashlib recovery vector");
#else
        for(unsigned n:{0,1,7,8,9,63,64,65,135,136,137,4096,65536}) {
            std::vector<uint8_t> data(n); for(auto& x:data) x=s.rng();
            s.start(n); s.send(data); s.check_done(data); ++cases;
        }
#endif
        // Every recovery hashes the same independently verified multi-block file.
        // Run these cases with the real RMs as well as the hostile shell model.
        auto recover = [&]() {
            require(s.read(4)&16,"engine not ready after cancellation");
            require(s.read(8)==algorithm_id,"algorithm ID changed during recovery");
            s.start(recovery_data.size()); s.send(recovery_data);
            s.check_done(recovery_data,recovery_digest);
            require(s.read(0x48)==0,"recovery retained a stale error code");
            ++recovery_cases;
        };
        // Abort resets the engine, preserves a sticky reason, and permits restart.
        s.start(513); s.send(recovery_data); s.write(0,2); s.wait(8);
        require((s.read(4)&7)==4&&s.read(0x48)==5,"abort state mismatch");
        recover();
        // Illegal keep and overlength beats are consumed by static error handling,
        // never forwarded into the RP.
        s.start(10); s.beat(0x11223344,5,false); s.wait(8);
        require(s.read(0x48)==1&&s.read(0x18)==0,"bad keep was not rejected");
        require(s.received.empty(),"bad keep reached the engine");
        recover();
        s.start(1); s.beat(0xabcd,3,true); s.wait(8);
        require(s.read(0x48)==2&&s.read(0x18)==0,"overlength was not rejected");
        require(s.received.empty(),"overlength beat reached the engine");
        recover();
        s.start(513); s.send(recovery_data);
        s.write(0x10,3,15,2); s.write(0,1,15,2);
        require(s.read(0x10)==513&&s.read(0x48)==4,"busy control guard failed");
        s.write(0,4); s.hostile=true; s.wait(10);
        require((s.read(4)&9)==8 && s.read(8)==0,"isolate did not abort/quiesce");
        require(s.read(0x48)==6,"isolation abort reason missing");
        s.hostile=false; s.write(0,8); s.wait(8);
        recover();
        // Global reset during a transfer clears both static and partition state.
        s.start(513); s.send(recovery_data); s.reset();
        require(s.read(4)==8&&s.read(0x18)==0,"reset did not clear state");
        require(s.read(0x48)==0&&!s.d.irq,"reset retained an error or interrupt");
        s.write(0,0); s.wait(8); recover();
#ifdef REAL_ENGINE
        std::cout<<"PASS integrated shell + real RM: "<<cases<<" hashlib vectors, "<<recovery_cases
                 <<" hashlib-checked recoveries (abort, invalid keep, overlength, isolation, global reset), random DMA splits, AXIL skew/backpressure, byte-order and file TLAST monitoring\n";
#else
        std::cout<<"PASS static shell: "<<cases<<" file sizes, "<<recovery_cases
                 <<" recoveries, arbitrary DMA splits, AXIL skew/backpressure, WSTRB, invalid access, abort, reset, isolation\n";
#endif
        return 0;
    } catch(const std::exception& e) { std::cerr<<"FAIL: "<<e.what()<<"\n"; return 1; }
}
