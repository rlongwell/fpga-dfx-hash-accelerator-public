// SPDX-License-Identifier: MIT
// Bounded bring-up utility. Run only with hash_accel unloaded and, for GEM mode,
// macb administratively DOWN with runtime power/control=on. Payload movement,
// descriptor recycling and response generation are entirely in FPGA hardware.
#define _GNU_SOURCE
#define _FILE_OFFSET_BITS 64
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>

#define RAM_BASE UINT32_C(0x80000000)
#define RAM_SIZE 0x40000
static volatile uint32_t *ram,*hash,*gem;
static volatile sig_atomic_t stop;
static void signal_stop(int sig) { (void)sig; stop=1; }
static uint64_t ns(void) { struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return (uint64_t)t.tv_sec*1000000000+t.tv_nsec; }
static void barrier(void) { __sync_synchronize(); }
static void die(const char *s) { perror(s);exit(1); }
static void *map(int fd,uint64_t address,size_t size) {
    void *p=mmap(NULL,size,PROT_READ|PROT_WRITE,MAP_SHARED,fd,(off_t)address);
    if(p==MAP_FAILED)die("mmap");
    return p;
}
static uint64_t read64(volatile uint32_t *p) {
    uint32_t hi,lo,again;do {hi=p[1];lo=p[0];again=p[1];}while(hi!=again);
    return ((uint64_t)hi<<32)|lo;
}
static unsigned mdio(unsigned phy,unsigned reg,unsigned value,int write) {
    uint64_t until=ns()+100000000;
    while(!(gem[8/4]&4))if(ns()>until)die("MDIO idle timeout");
    gem[0x34/4]=UINT32_C(0x40020000)|(write?UINT32_C(0x10000000):UINT32_C(0x20000000))|(phy<<23)|(reg<<18)|(value&65535);
    barrier();
    while(!(gem[8/4]&4))if(ns()>until)die("MDIO completion timeout");
    return gem[0x34/4]&65535;
}
static void mac_words(const char *s,unsigned offset) {
    unsigned x[6];if(sscanf(s,"%x:%x:%x:%x:%x:%x",x,x+1,x+2,x+3,x+4,x+5)!=6)die("MAC address");
    for(int i=0;i<6;i++)if(x[i]>255)die("MAC byte");
    ram[offset/4]=x[0]|x[1]<<8|x[2]<<16|x[3]<<24;ram[offset/4+1]=x[4]|x[5]<<8;
}
int main(int argc,char **argv) {
    if (access("/proc/device-tree/axi/hash-ingress@80000000/compatible",R_OK)) {
        fprintf(stderr,"matching direct-GEM device tree is required\n");return 2;
    }
    int reset_only=argc==2 && (!strcmp(argv[1],"reset-replay") || !strcmp(argv[1],"reset-ethernet"));
    if(argc!=8 && !reset_only) {
        fprintf(stderr,"usage: gem_board replay|ethernet LENGTH SESSION PATTERN|- PEER_MAC LOCAL_MAC PHY_ADDR\n       gem_board reset-replay|reset-ethernet\n");return 2;
    }
    int replay=!strcmp(argv[1],"replay") || !strcmp(argv[1],"reset-replay");
    if(!reset_only && !replay && strcmp(argv[1],"ethernet"))return 2;
    uint64_t length=reset_only?0:strtoull(argv[2],NULL,0);
    uint32_t session=reset_only?1:(uint32_t)strtoul(argv[3],NULL,0);
    if(length>((UINT64_C(1)<<61)-1) || !session)return 2;
    if(access("/sys/module/hash_accel",F_OK)==0) {fprintf(stderr,"hash_accel must be unloaded\n");return 2;}
    signal(SIGTERM,signal_stop);signal(SIGINT,signal_stop);
    int fd=open("/dev/mem",O_RDWR|O_SYNC);if(fd<0)die("/dev/mem");
    hash=map(fd,0x43c00000,4096);ram=map(fd,RAM_BASE,RAM_SIZE);
    if(hash[0xc/4]!=65536) {fprintf(stderr,"wrong hash ABI: 0x%08x\n",hash[0xc/4]);return 2;}
    if(reset_only) {
        // Keep all MMIO in C: volatile aligned words, never byte-wise Python
        // packing into the AXI-Lite register bank.
        hash[0]=6;barrier();usleep(1000);ram[0x400/4]=0;barrier();
        if(!replay){gem=map(fd,0xe000b000,4096);gem[0]=0x10;gem[0x2c/4]=UINT32_MAX;barrier();}
        hash[0]=8;barrier();
        munmap((void*)ram,RAM_SIZE);munmap((void*)hash,4096);
        if(gem)munmap((void*)gem,4096);
        close(fd);return 0;
    }
    // Driver removal deliberately leaves the RP isolated (ID reads as zero).
    // Release that isolation before checking the already selected personality.
    hash[0]=8;barrier();usleep(20);
    if(hash[8/4]<1 || hash[8/4]>3) {
        fprintf(stderr,"wrong hash algorithm ID: %u\n",hash[8/4]);hash[0]=4;barrier();return 2;
    }
    unsigned algorithm=hash[8/4];
    hash[0]=6;barrier();usleep(20); // Abort/isolate resets ingress and the hash RM.
    for(unsigned i=0;i<0x1000/4;i++)ram[i]=0;
    size_t pattern_size=0;
    if(replay) {
        FILE *f=fopen(argv[4],"rb");if(!f)die("pattern");
        unsigned char *pattern=malloc(0x3f001);if(!pattern)die("pattern allocation");
        pattern_size=fread(pattern,1,0x3f001,f);int bad=ferror(f);fclose(f);
        if(bad || !pattern_size || pattern_size>0x3f000 || pattern_size%8) {
            fprintf(stderr,"pattern must be 8..258048 bytes, a multiple of 8\n");return 2;
        }
        for(size_t i=0;i<pattern_size/4;i++){uint32_t v;memcpy(&v,pattern+4*i,4);ram[0x1000/4+i]=v;}
        barrier();
        for(size_t i=0;i<pattern_size/4;i++){
            uint32_t v;memcpy(&v,pattern+4*i,4);
            if(ram[0x1000/4+i]!=v){fprintf(stderr,"FPGA pattern readback failed\n");return 1;}
        }
        free(pattern);ram[0x404/4]=(uint32_t)pattern_size;
    } else {
        // Keep the Linux MAC driver down for the entire bounded run.
        FILE *flags=fopen("/sys/class/net/eth0/flags","r");unsigned flag=1;
        if(!flags || fscanf(flags,"%x",&flag)!=1 || (flag&1)) {fprintf(stderr,"eth0 must be DOWN\n");return 2;}
        fclose(flags);gem=map(fd,0xe000b000,4096);
        gem[0x2c/4]=UINT32_MAX;gem[0]=0x10;barrier();
        // Preserve MDC clock divisor; force full-duplex 1G, aligned RX, FCS stripped.
        gem[4/4]=(gem[4/4]&(7u<<18))|(1u<<10)|(1u<<1)|(1u<<17)|(1u<<5);
        gem[0x10/4]=(32u<<16)|(3u<<8)|(1u<<10)|16u;
        gem[0x88/4]=0;gem[0x8c/4]=0;
        mac_words(argv[6],0x418);gem[0x88/4]=ram[0x418/4];gem[0x8c/4]=ram[0x41c/4];
        unsigned phy=(unsigned)strtoul(argv[7],NULL,0);if(phy>31)return 2;
        unsigned bmcr=mdio(phy,0,0,0);mdio(phy,0,bmcr&~0x800u,1);
        uint64_t deadline=ns()+UINT64_C(10000000000);
        while(!stop) {mdio(phy,1,0,0);if(mdio(phy,1,0,0)&4)break;if(ns()>deadline)break;usleep(10000);}
        if(stop || !(mdio(phy,1,0,0)&4)) {fprintf(stderr,"PHY link did not return\n");return 1;}
        for(unsigned i=0;i<32;i++){ram[2*i]=RAM_BASE+0x1000+i*2048+(i==31?2:0);ram[2*i+1]=0;}
        ram[0x200/4]=RAM_BASE+0x800;ram[0x204/4]=UINT32_C(0xc0008040);
        ram[0x404/4]=session;mac_words(argv[5],0x410);
        gem[0x18/4]=RAM_BASE;gem[0x1c/4]=RAM_BASE+0x200;
        gem[0x14/4]=UINT32_MAX;gem[0x20/4]=UINT32_MAX;
    }
    ram[0x408/4]=(uint32_t)length;ram[0x40c/4]=(uint32_t)(length>>32);
    ram[0x400/4]=replay?UINT32_C(0x31504c52):UINT32_C(0x314e4554);barrier();
    hash[0]=8;barrier();usleep(20);
    hash[0x10/4]=(uint32_t)length;hash[0x14/4]=(uint32_t)(length>>32);barrier();
    uint64_t started=ns();hash[0]=1;barrier();
    if(!replay){gem[0]=0x1c;barrier();}
    printf("{\"event\":\"ready\",\"mode\":\"%s\",\"session\":%u,\"length\":%"PRIu64",\"algorithm_id\":%u}\n",argv[1],session,length,algorithm);fflush(stdout);
    uint64_t deadline=started+UINT64_C(180000000000);
    while(!stop && !(hash[1]&6) && ns()<deadline)usleep(100);
    uint64_t ended=ns(),cycles=read64(hash+0x40/4),accepted=read64(hash+0x18/4);
    uint32_t status=hash[1],error=hash[0x48/4],ingress_status=ram[0x510/4];
    unsigned char digest[32];for(unsigned i=0;i<8;i++){uint32_t v=hash[0x20/4+i];memcpy(digest+4*i,&v,4);}
    int ok=!stop && (status&2) && !(status&4) && !error && !(ingress_status&2) && accepted==length;
    printf("{\"event\":\"result\",\"ok\":%s,\"status\":%u,\"error\":%u,\"ingress_status\":%u,\"accepted\":%"PRIu64",\"core_cycles\":%"PRIu64",\"board_ns\":%"PRIu64",\"pattern_bytes\":%zu,\"digest\":\"",ok?"true":"false",status,error,ingress_status,accepted,cycles,ended-started,pattern_size);
    for(unsigned i=0;i<32;i++)printf("%02x",digest[i]);
    printf("\"}");
    if(gem)printf("\n{\"event\":\"gem\",\"rx_frames\":%u,\"tx_frames\":%u,\"rx_fcs_errors\":%u,\"rx_overruns\":%u,\"rsr\":%u,\"tsr\":%u}",gem[0x158/4],gem[0x108/4],gem[0x190/4],gem[0x1a4/4],gem[0x20/4],gem[0x14/4]);
    if(gem)printf("\n{\"event\":\"dma_addresses\",\"rx_pointer\":%u,\"tx_pointer\":%u,\"dma_config\":%u,\"fpga_ram_base\":%u}",gem[0x18/4],gem[0x1c/4],gem[0x10/4],RAM_BASE);
    printf("\n");fflush(stdout);
    // FPGA keeps repeating final result ACKs briefly, allowing a lost reply.
    if(gem && ok)usleep(300000);
    if(gem){gem[0]=0x10;gem[0x2c/4]=UINT32_MAX;barrier();}
    hash[0]=6;barrier();usleep(20);ram[0x400/4]=0;barrier();hash[0]=8;barrier();
    munmap((void*)ram,RAM_SIZE);munmap((void*)hash,4096);if(gem)munmap((void*)gem,4096);close(fd);
    return ok?0:1;
}
