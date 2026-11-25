// SPDX-License-Identifier: MIT
// Reliable bounded-window raw Ethernet sender. No timing includes software hashing.
#define _GNU_SOURCE
#define _FILE_OFFSET_BITS 64
#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <linux/if_packet.h>
#include <net/if.h>
#include <poll.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

#define PAYLOAD 1440
#define MAX_WINDOW 32
#define DEFAULT_WINDOW 12
static uint64_t ns(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return(uint64_t)t.tv_sec*1000000000+t.tv_nsec;}
static void die(const char*s){perror(s);exit(1);}
static void put32(unsigned char*p,uint32_t x){for(unsigned i=0;i<4;i++)p[i]=(unsigned char)(x>>(i*8));}
static uint32_t get32(const unsigned char*p){return(uint32_t)p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
static void put64(unsigned char*p,uint64_t x){put32(p,(uint32_t)x);put32(p+4,(uint32_t)(x>>32));}
int main(int argc,char**argv){
    if(argc!=6 && argc!=7){fprintf(stderr,"usage: gem_send INTERFACE BOARD_MAC SESSION FILE REPORT.json [WINDOW]\n");return 2;}
    char *end=NULL;unsigned long requested=argc==7?strtoul(argv[6],&end,10):DEFAULT_WINDOW;
    if(requested<1 || requested>MAX_WINDOW || (argc==7 && (!argv[6][0] || *end))){fprintf(stderr,"window must be 1..32 frames\n");return 2;}
    unsigned window=(unsigned)requested;
    unsigned mac[6];unsigned char target[6];
    if(sscanf(argv[2],"%x:%x:%x:%x:%x:%x",mac,mac+1,mac+2,mac+3,mac+4,mac+5)!=6)return 2;
    for(unsigned i=0;i<6;i++){if(mac[i]>255)return 2;target[i]=(unsigned char)mac[i];}
    uint32_t session=(uint32_t)strtoul(argv[3],NULL,0);if(!session)return 2;
    int file=open(argv[4],O_RDONLY);if(file<0)die("input file");struct stat st;if(fstat(file,&st))die("fstat");
    uint64_t length=(uint64_t)st.st_size;if(length>((UINT64_C(1)<<61)-1))return 2;
    unsigned char*data=length?mmap(NULL,(size_t)length,PROT_READ,MAP_PRIVATE,file,0):NULL;
    if(length && data==MAP_FAILED)die("mmap input");
    int sock=socket(AF_PACKET,SOCK_RAW,htons(0x88b5));if(sock<0)die("raw Ethernet socket");
    struct ifreq req={0};snprintf(req.ifr_name,sizeof(req.ifr_name),"%s",argv[1]);
    if(ioctl(sock,SIOCGIFHWADDR,&req))die("local MAC");
    unsigned char local[6];memcpy(local,req.ifr_hwaddr.sa_data,6);
    struct sockaddr_ll address={.sll_family=AF_PACKET,.sll_protocol=htons(0x88b5),.sll_ifindex=(int)if_nametoindex(argv[1]),.sll_halen=6};
    memcpy(address.sll_addr,target,6);if(!address.sll_ifindex || bind(sock,(struct sockaddr*)&address,sizeof(address)))die("bind");
    int rcvbuf=1<<20;setsockopt(sock,SOL_SOCKET,SO_RCVBUF,&rcvbuf,sizeof(rcvbuf));
    unsigned char frames[MAX_WINDOW][64+PAYLOAD];struct mmsghdr messages[MAX_WINDOW];struct iovec vectors[MAX_WINDOW];
    memset(messages,0,sizeof(messages));
    for(unsigned i=0;i<window;i++){
        memset(frames[i],0,sizeof(frames[i]));memcpy(frames[i],target,6);memcpy(frames[i]+6,local,6);
        put32(frames[i]+12,0x0101b588);put32(frames[i]+16,session);
        vectors[i].iov_base=frames[i];messages[i].msg_hdr.msg_iov=vectors+i;messages[i].msg_hdr.msg_iovlen=1;
        messages[i].msg_hdr.msg_name=&address;messages[i].msg_hdr.msg_namelen=sizeof(address);
    }
    uint64_t acknowledged=0,sent=0,started=0,last_progress=ns(),retries=0,packets=0,acks=0;
    uint64_t deadline=ns()+UINT64_C(180000000000);int ready=0,done=0;unsigned char digest[32]={0};
    while(ns()<deadline){
        if(ready && sent<length && sent-acknowledged<window*PAYLOAD){
            unsigned count=0;
            while(count<window && sent<length && sent-acknowledged<window*PAYLOAD){
                size_t n=length-sent>PAYLOAD?PAYLOAD:(size_t)(length-sent);
                put64(frames[count]+20,sent);put32(frames[count]+28,(uint32_t)n);
                memcpy(frames[count]+64,data+sent,n);vectors[count].iov_len=64+n;sent+=n;count++;
            }
            if(!started)started=ns();
            unsigned off=0;while(off<count){int n=sendmmsg(sock,messages+off,count-off,0);if(n<0){if(errno==EINTR)continue;die("sendmmsg");}off+=(unsigned)n;}
            packets+=count;
        }
        struct pollfd p={.fd=sock,.events=POLLIN};int available=poll(&p,1,10);
        if(available<0){if(errno==EINTR)continue;die("poll");}
        if(available){
            unsigned char response[2048];ssize_t n=recv(sock,response,sizeof(response),0);if(n<0)die("recv");
            if(n<64 || memcmp(response,local,6) || memcmp(response+6,target,6) || get32(response+12)!=0x0201b588 || get32(response+16)!=session)continue;
            uint64_t next=(uint64_t)get32(response+20)|((uint64_t)get32(response+24)<<32);unsigned status=get32(response+28);
            if(next>length || next>sent || status>2){fprintf(stderr,"invalid hardware ACK\n");return 1;}
            if(status==2){fprintf(stderr,"FPGA reported an error\n");return 1;}
            acks++;
            // The peer may need time to initialize the link. That wait is not
            // a lost data window: start its retry timer at the first ready ACK.
            if(!ready){ready=1;last_progress=ns();}
            if(next>acknowledged){acknowledged=next;last_progress=ns();}
            if(status==1){if(next!=length){fprintf(stderr,"premature digest\n");return 1;}memcpy(digest,response+32,32);done=1;break;}
        }
        if(ready && sent>acknowledged && ns()-last_progress>UINT64_C(20000000)){
            sent=acknowledged;last_progress=ns();retries++;
            if(retries>1000){fprintf(stderr,"retransmission limit\n");return 1;}
        }
    }
    uint64_t elapsed=started?ns()-started:0;
    if(!done){fprintf(stderr,"bounded receive timeout\n");return 1;}
    FILE*out=fopen(argv[5],"wx");if(!out)die("new report file");
    fprintf(out,"{\"status\":\"ok\",\"mode\":\"gem-to-pl\",\"session\":%u,\"length\":%"PRIu64",\"transfer_ns\":%"PRIu64",\"MB_per_second\":%.9f,\"packets_sent\":%"PRIu64",\"acks\":%"PRIu64",\"retries\":%"PRIu64",\"digest\":\"",session,length,elapsed,elapsed?(double)length*1000.0/(double)elapsed:0,packets,acks,retries);
    for(unsigned i=0;i<32;i++)fprintf(out,"%02x",digest[i]);
    fprintf(out,"\",\"window_frames\":%u}\n",window);fclose(out);
    printf("%"PRIu64" bytes, %.6f seconds, %.3f MB/s, retries=%"PRIu64"\n",length,(double)elapsed/1e9,elapsed?(double)length*1000.0/(double)elapsed:0,retries);
    if(length)munmap(data,(size_t)length);
    close(file);close(sock);return 0;
}
